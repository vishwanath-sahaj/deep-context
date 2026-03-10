"""Type definitions for Scribe Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class StepRecord:
    """A single recorded step from action agent execution."""

    step_number: int
    action: str  # "navigate", "fill", "click", "select", "hover", "wait", "auto_fill"
    target_element: str  # What the step tried to interact with
    matched_element: Optional[str] = None  # What actually matched (ref + snapshot line)
    match_type: str = "none"  # "exact", "fuzzy", "not_found"
    value: Optional[str] = None  # Value typed/selected
    accessibility_snapshot: str = ""  # Page state before action
    screenshot_path: Optional[str] = None  # Screenshot after action
    result: str = ""  # Success/failure message
    url: str = ""  # Current page URL
    error: Optional[str] = None  # Error message if step failed


@dataclass
class FlowExecutionRecord:
    """Complete record of a single flow's execution."""

    flow_name: str
    flow_markdown: str  # Original flow definition from flow identifier
    start_url: str
    steps: List[StepRecord] = field(default_factory=list)
    screenshot_dir: str = ""
    success: bool = True
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    @property
    def screenshot_paths(self) -> List[str]:
        return [s.screenshot_path for s in self.steps if s.screenshot_path]


@dataclass
class ScribeOutput:
    """Final output from the scribe agent."""

    flow_name: str
    documentation_markdown: str  # The developer-facing documentation
    flow_execution: FlowExecutionRecord
    codebase_summary: str
    generated_at: datetime = field(default_factory=datetime.now)
