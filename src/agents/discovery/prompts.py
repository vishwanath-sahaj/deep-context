"""Strategic queries for codebase exploration."""

from typing import List
from .types import ExplorationQuery


EXPLORATION_QUERIES: List[ExplorationQuery] = [
    ExplorationQuery(
        query="List all pages, routes, and their file paths in this frontend application. "
              "Include the routing configuration and component structure.",
        purpose="Understand application structure and navigation",
        priority=1
    ),
    
    ExplorationQuery(
        query="Identify all form components including their input fields. For each input, "
              "provide: HTML element type, name attribute, type attribute, placeholder text, "
              "label text, and any data-testid or data-test attributes.",
        purpose="Extract form metadata for fill actions",
        priority=1
    ),
    
    ExplorationQuery(
        query="Where is user authentication implemented? Include login, signup, and logout "
              "flows. Describe the form fields, buttons, and navigation after successful auth.",
        purpose="Identify critical authentication flows",
        priority=1
    ),
    
    ExplorationQuery(
        query="Find all button and link elements that trigger navigation or actions. "
              "Include: visible text, aria-label, data-testid, role attribute, and what "
              "action they trigger (navigation, form submission, API call).",
        purpose="Extract button/link metadata for click actions",
        priority=2
    ),
    
    ExplorationQuery(
        query="Identify critical user interactions such as: checkout process, payment flows, "
              "profile/settings management, search functionality, or any multi-step workflows.",
        purpose="Discover high-priority user flows",
        priority=2
    ),
]


def get_exploration_queries(max_queries: int = 5) -> List[str]:
    """Get prioritized exploration queries."""
    sorted_queries = sorted(EXPLORATION_QUERIES, key=lambda q: q.priority)
    return [q.query for q in sorted_queries[:max_queries]]
