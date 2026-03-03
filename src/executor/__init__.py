"""
Executor — runs the correct tool based on QueryType.

Tools:
  METADATA  -> scan file-system stats without embedding search
  SEARCH    -> FAISS nearest-neighbour lookup
  REASONING -> RAG: retrieve relevant chunks then call GPT
  TOOL      -> side-effect commands (clone / reindex)
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from openai import OpenAI

from src.common.config import config
from src.common.logger import get_logger
from src.indexer import collect_files, index_repository
from src.planner import QueryType
from src.retrieval import build_context_string, retrieve

logger = get_logger(__name__)

_client = OpenAI(api_key=config.OPENAI_API_KEY)

# ---------------------------------------------------------------------------
# System prompt for the reasoning / search LLM calls
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are RepoPilot, an expert AI agent that helps developers understand large codebases.

You are given:
1. A USER QUERY about a codebase.
2. RELEVANT CODE CONTEXT retrieved from a FAISS vector index of the repository.

Your job:
- Answer the query accurately using the provided context.
- Cite the source file(s) when relevant (e.g. "in `src/foo/bar.py`").
- If the context is insufficient, say so honestly — do NOT hallucinate.
- Keep answers concise but complete.
- Use markdown formatting (code blocks, bullet lists) where it aids clarity.
"""


# ---------------------------------------------------------------------------
# Individual tool handlers
# ---------------------------------------------------------------------------

def _execute_metadata(query: str, repo_path: Path) -> str:
    """Answer simple metadata questions by scanning the file system."""
    files = collect_files(repo_path)
    by_ext: dict[str, int] = {}
    for fpath, _ in files:
        ext = fpath.suffix.lower() or "(no ext)"
        by_ext[ext] = by_ext.get(ext, 0) + 1

    lines = [
        f"**Repository:** `{repo_path}`",
        f"**Total indexed files:** {len(files)}",
        "",
        "**Files by extension:**",
    ]
    for ext, count in sorted(by_ext.items(), key=lambda x: -x[1]):
        lines.append(f"  - `{ext}`: {count}")

    stats_text = "\n".join(lines)

    # Let the LLM answer the specific metadata question with these stats
    response = _client.chat.completions.create(
        model=config.OPENAI_CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that answers questions about "
                    "repository statistics. Answer using ONLY the data provided."
                ),
            },
            {
                "role": "user",
                "content": f"User query: {query}\n\nRepository stats:\n{stats_text}",
            },
        ],
        temperature=0,
    )
    return response.choices[0].message.content


def _execute_search(query: str, vector_store: Any) -> str:
    """Find where something is defined using similarity search."""
    retrieved = retrieve(vector_store, query, top_k=8)
    context = build_context_string(retrieved, max_chars=6000)

    response = _client.chat.completions.create(
        model=config.OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"USER QUERY: {query}\n\n"
                    f"RELEVANT CODE CONTEXT:\n{context}"
                ),
            },
        ],
        temperature=0.1,
    )
    answer = response.choices[0].message.content

    # Append source citations
    sources = sorted(
        {meta.get("source", "?") for _, meta, _ in retrieved}
    )
    if sources:
        answer += "\n\n---\n**Sources searched:**\n" + "\n".join(
            f"- `{s}`" for s in sources
        )
    return answer


def _execute_reasoning(query: str, vector_store: Any) -> str:
    """Deep reasoning: RAG + GPT answer."""
    retrieved = retrieve(vector_store, query, top_k=6)
    context = build_context_string(retrieved, max_chars=8000)

    response = _client.chat.completions.create(
        model=config.OPENAI_CHAT_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"USER QUERY: {query}\n\n"
                    f"RELEVANT CODE CONTEXT:\n{context}"
                ),
            },
        ],
        temperature=0.3,
    )
    answer = response.choices[0].message.content

    sources = sorted(
        {meta.get("source", "?") for _, meta, _ in retrieved}
    )
    if sources:
        answer += "\n\n---\n**Referenced files:**\n" + "\n".join(
            f"- `{s}`" for s in sources
        )
    return answer


def _execute_tool(query: str, repo_path: Path, vector_store_ref: list) -> str:
    """Handle side-effect commands like reindex."""
    q = query.lower()

    if any(kw in q for kw in ("reindex", "index again", "refresh index", "rebuild")):
        logger.info("reindexing", repo=str(repo_path))
        new_store = index_repository(repo_path, force=True)
        vector_store_ref[0] = new_store
        return "✅ Repository re-indexed successfully."

    if "clone" in q:
        # Extract URL (simple heuristic)
        words = query.split()
        url = next((w for w in words if w.startswith("http")), None)
        if url:
            dest = Path("./cloned_repo")
            logger.info("cloning", url=url, dest=str(dest))
            result = subprocess.run(
                ["git", "clone", "--depth", "1", url, str(dest)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                new_store = index_repository(dest, force=True)
                vector_store_ref[0] = new_store
                return f"✅ Cloned `{url}` and indexed successfully."
            return f"❌ Clone failed:\n```\n{result.stderr}\n```"
        return "❌ Please provide a valid git URL to clone."

    return "❓ Unknown tool command. Try: 'reindex' or 'clone <url>'."


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

class Executor:
    """Routes a classified query to the right tool handler."""

    def __init__(self, repo_path: Path, vector_store: Any):
        self.repo_path = repo_path
        # Wrap in a list so _execute_tool can mutate it
        self._vs_ref: list = [vector_store]

    @property
    def vector_store(self) -> Any:
        return self._vs_ref[0]

    def run(self, query: str, query_type: QueryType) -> str:
        logger.info("executing", query_type=query_type.name, query=query[:80])
        try:
            if query_type == QueryType.METADATA:
                return _execute_metadata(query, self.repo_path)
            elif query_type == QueryType.SEARCH:
                return _execute_search(query, self.vector_store)
            elif query_type == QueryType.REASONING:
                return _execute_reasoning(query, self.vector_store)
            elif query_type == QueryType.TOOL:
                return _execute_tool(query, self.repo_path, self._vs_ref)
            else:
                return "❓ Unknown query type."
        except Exception as exc:  # noqa: BLE001
            logger.error("executor_error", error=str(exc))
            return f"❌ An error occurred: {exc}"
