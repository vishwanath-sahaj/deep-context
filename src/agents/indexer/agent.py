"""Repository scanner and FAISS indexer."""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

from src.common.config import config
from src.common.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper: collect source files from a local directory
# ---------------------------------------------------------------------------

def _should_skip_dir(name: str) -> bool:
    return name in config.SKIP_DIRS or name.endswith(".egg-info")


def _should_skip_file(path: Path) -> bool:
    if path.suffix.lower() in config.SKIP_EXTENSIONS:
        return True
    try:
        if path.stat().st_size > config.MAX_FILE_SIZE_BYTES:
            logger.debug("skipping_large_file", path=str(path))
            return True
    except OSError:
        return True
    return False


def collect_files(root: Path) -> List[Tuple[Path, str]]:
    """
    Walk *root* and return (path, content) tuples for every text file.
    Binary files, build artefacts, and excessively large files are skipped.
    """
    results: List[Tuple[Path, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skip-dirs in-place so os.walk doesn't descend into them
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if _should_skip_file(fpath):
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
                results.append((fpath, content))
            except Exception as exc:  # noqa: BLE001
                logger.warning("read_error", path=str(fpath), error=str(exc))
    logger.info("files_collected", count=len(results), root=str(root))
    return results


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=config.CHUNK_SIZE,
    chunk_overlap=config.CHUNK_OVERLAP,
    separators=["\n\nclass ", "\n\ndef ", "\n\n", "\n", " ", ""],
)


def chunk_files(
    files: List[Tuple[Path, str]], repo_root: Path
) -> Tuple[List[str], List[dict]]:
    """
    Split file contents into overlapping chunks.
    Returns (chunks, metadatas) where each metadata dict contains the
    relative file path so we can cite sources.
    """
    chunks: List[str] = []
    metadatas: List[dict] = []

    for fpath, content in files:
        try:
            rel = fpath.relative_to(repo_root)
        except ValueError:
            rel = fpath

        file_chunks = _SPLITTER.split_text(content)
        for i, chunk in enumerate(file_chunks):
            chunks.append(chunk)
            metadatas.append(
                {
                    "source": str(rel),
                    "chunk_index": i,
                    "total_chunks": len(file_chunks),
                }
            )

    logger.info("chunks_created", count=len(chunks))
    return chunks, metadatas


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def index_repository(repo_path: str | Path, force: bool = False) -> FAISS:
    """
    Build (or reload) a FAISS vector store for *repo_path*.

    If an index already exists in ``config.INDEX_DIR`` and *force* is False,
    the existing index is loaded instead of rebuilding.

    Returns the FAISS vector store.
    """
    repo_path = Path(repo_path).expanduser().resolve()
    # Store the index inside the target repo so each repo has its own index.
    # Falls back to config.INDEX_DIR only if explicitly set via env var.
    default_index = repo_path / ".deep-context-index"
    env_index = os.getenv("INDEX_DIR")
    index_path = Path(env_index).expanduser().resolve() if env_index else default_index

    embeddings = HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
    )

    faiss_index_file = index_path / "index.faiss"
    if faiss_index_file.exists() and not force:
        logger.info("loading_existing_index", path=str(index_path))
        return FAISS.load_local(
            str(index_path),
            embeddings,
            allow_dangerous_deserialization=True,
        )

    logger.info("indexing_repository", path=str(repo_path))
    files = collect_files(repo_path)
    if not files:
        raise ValueError(f"No readable source files found in {repo_path}")

    chunks, metadatas = chunk_files(files, repo_path)

    # Build in batches to keep memory usage manageable
    BATCH = 500
    vector_store: FAISS | None = None
    for start in range(0, len(chunks), BATCH):
        batch_texts = chunks[start : start + BATCH]
        batch_meta = metadatas[start : start + BATCH]
        logger.info(
            "embedding_batch",
            start=start,
            end=min(start + BATCH, len(chunks)),
            total=len(chunks),
        )
        if vector_store is None:
            vector_store = FAISS.from_texts(
                texts=batch_texts,
                embedding=embeddings,
                metadatas=batch_meta,
            )
        else:
            batch_store = FAISS.from_texts(
                texts=batch_texts,
                embedding=embeddings,
                metadatas=batch_meta,
            )
            vector_store.merge_from(batch_store)

    index_path.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(index_path))
    logger.info("index_saved", path=str(index_path))
    return vector_store
