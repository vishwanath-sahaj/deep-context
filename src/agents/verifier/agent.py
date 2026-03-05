"""
Verifier — validates executor output before returning it to the user.

Checks performed:
1. Non-empty response.
2. The response doesn't contain hallucination markers ("I don't know" + made-up code).
3. Optionally asks Claude to self-critique when confidence is low.
"""
from __future__ import annotations

import re

import anthropic

from src.common.config import config
from src.common.logger import get_logger

logger = get_logger(__name__)

_client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

_UNCERTAIN_PATTERNS = re.compile(
    r"\b(I (don't|do not|cannot|can't) know|not sure|unclear|"
    r"cannot (be|find)|no (information|context)|hallucin)\b",
    re.IGNORECASE,
)


def verify(answer: str, original_query: str, auto_critique: bool = False) -> str:
    """
    Validate and optionally refine the executor's answer.

    Parameters
    ----------
    answer:         Raw answer from the executor.
    original_query: The user's original question.
    auto_critique:  If True, ask Claude to self-critique the answer.

    Returns the (possibly refined) answer with a verification footer.
    """
    if not answer or not answer.strip():
        return "⚠️ The agent returned an empty response. Please try rephrasing."

    uncertain = bool(_UNCERTAIN_PATTERNS.search(answer))

    if uncertain:
        logger.warning("low_confidence_response", query=original_query[:60])

    if auto_critique and uncertain:
        logger.info("running_self_critique")
        try:
            critique_response = _client.messages.create(
                model=config.CLAUDE_CHAT_MODEL,
                max_tokens=512,
                system=(
                    "You are a verification assistant. "
                    "Review the following answer to a codebase question. "
                    "If it contains uncertain or speculative content, "
                    "identify what is uncertain and suggest how the user "
                    "could rephrase their question for a better answer. "
                    "Keep your critique short (3–5 sentences)."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Original query: {original_query}\n\n"
                            f"Answer to review:\n{answer}"
                        ),
                    },
                ],
            )
            critique = critique_response.content[0].text
            answer += f"\n\n---\n> 🔍 **Verifier note:** {critique}"
        except Exception as exc:  # noqa: BLE001
            logger.error("critique_failed", error=str(exc))

    return answer
