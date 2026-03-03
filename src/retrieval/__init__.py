"""Vector similarity retrieval on top of the FAISS index."""
from __future__ import annotations

from typing import List, Tuple

from langchain_community.vectorstores import FAISS

from src.common.logger import get_logger

logger = get_logger(__name__)


def retrieve(
    vector_store: FAISS,
    query: str,
    top_k: int = 6,
) -> List[Tuple[str, dict, float]]:
    """
    Return the top-k most similar chunks for *query*.

    Each element is a (chunk_text, metadata, relevance_score) tuple.
    Scores are cosine-similarity based (higher = more relevant).
    """
    docs_and_scores = vector_store.similarity_search_with_relevance_scores(
        query, k=top_k
    )
    results = []
    for doc, score in docs_and_scores:
        results.append((doc.page_content, doc.metadata, score))
        logger.debug(
            "retrieved_chunk",
            source=doc.metadata.get("source", "?"),
            score=round(score, 4),
        )
    return results


def build_context_string(
    retrieved: List[Tuple[str, dict, float]],
    max_chars: int = 8000,
) -> str:
    """
    Format retrieved chunks into a single context string for the LLM.
    Truncates if the combined content is too long.
    """
    parts: List[str] = []
    total = 0
    for chunk, meta, score in retrieved:
        header = f"### [{meta.get('source', 'unknown')}] (score: {score:.3f})\n"
        block = header + chunk + "\n\n"
        if total + len(block) > max_chars:
            remaining = max_chars - total
            if remaining > len(header) + 50:
                parts.append(header + chunk[: remaining - len(header)] + "…\n\n")
            break
        parts.append(block)
        total += len(block)

    return "".join(parts)
