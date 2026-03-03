"""
Query Planner — classifies incoming queries into action types
following the ReAct (Reasoning + Acting) pattern from the article.
"""
from __future__ import annotations

from enum import Enum, auto
import re


class QueryType(Enum):
    METADATA = auto()   # "how many files", "list all modules"
    SEARCH = auto()     # "where is the X class defined"
    REASONING = auto()  # "explain the architecture", "how does X work"
    TOOL = auto()       # "clone this repo", "reindex"


# Simple keyword-based routing (fast, zero LLM calls)
_METADATA_PATTERNS = re.compile(
    r"\b(how many|count|list all|total number|number of|show all)\b",
    re.IGNORECASE,
)
_SEARCH_PATTERNS = re.compile(
    r"\b(where is|find|locate|which file|what file|defined in|implemented in)\b",
    re.IGNORECASE,
)
_TOOL_PATTERNS = re.compile(
    r"\b(clone|reindex|index again|refresh index|rebuild index)\b",
    re.IGNORECASE,
)


class QueryRouter:
    """Classify a natural-language query into a QueryType."""

    def classify(self, query: str) -> QueryType:
        if _TOOL_PATTERNS.search(query):
            return QueryType.TOOL
        if _METADATA_PATTERNS.search(query):
            return QueryType.METADATA
        if _SEARCH_PATTERNS.search(query):
            return QueryType.SEARCH
        return QueryType.REASONING
