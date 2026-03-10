"""Parse flows_markdown into individual flow blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass
class ParsedFlow:
    """A single flow extracted from the combined flows markdown."""

    name: str
    priority: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    markdown: str  # The full markdown block for this flow


def parse_flows_markdown(flows_markdown: str) -> List[ParsedFlow]:
    """
    Split the combined flows markdown into individual flow blocks.

    Expects formats like:
        ## Flow 1: User Login (CRITICAL)
        ## Flow 2: Contact Management - Add Contact (HIGH)
        ### Flow 3: ...
    """
    # Split on flow headers (## Flow N: or ### Flow N:)
    flow_pattern = re.compile(
        r'^(#{2,3})\s+Flow\s+\d+:\s*(.+)$',
        re.MULTILINE,
    )

    matches = list(flow_pattern.finditer(flows_markdown))

    if not matches:
        # Fallback: treat the entire markdown as a single flow
        return [ParsedFlow(name="Flow 1", priority="CRITICAL", markdown=flows_markdown)]

    flows: List[ParsedFlow] = []

    for i, match in enumerate(matches):
        # Extract flow content from this header to the next header (or end)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(flows_markdown)
        block = flows_markdown[start:end].strip()

        # Parse name and priority from the header
        raw_title = match.group(2).strip()

        # Extract priority from parentheses, e.g., "User Login (CRITICAL)"
        priority_match = re.search(r'\((\w+)\)\s*$', raw_title)
        if priority_match:
            priority = priority_match.group(1).upper()
            name = raw_title[:priority_match.start()].strip().rstrip('-').strip()
        else:
            priority = "MEDIUM"
            name = raw_title

        flows.append(ParsedFlow(name=name, priority=priority, markdown=block))

    return flows
