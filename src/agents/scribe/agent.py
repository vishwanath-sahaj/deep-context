"""Scribe Agent: Generates developer documentation from flow executions."""

from __future__ import annotations

import json
import base64
from pathlib import Path
from typing import List, Optional

import anthropic

from src.common.config import config
from src.common.logger import get_logger
from .types import FlowExecutionRecord, ScribeOutput, StepRecord
from .prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    DOCUMENTATION_SYSTEM_PROMPT,
    format_analysis_prompt,
    format_documentation_prompt,
)

logger = get_logger(__name__)


class ScribeAgent:
    """
    Generates rich developer documentation from flow execution records.

    Two-pass approach:
    1. Analysis pass: Structured breakdown of what happened and why
    2. Documentation pass: Human-quality markdown with screenshots
    """

    def __init__(self, api_key: Optional[str] = None):
        self._client = anthropic.Anthropic(api_key=api_key or config.CLAUDE_API_KEY)
        self._model = "claude-sonnet-4-5"
        logger.info("ScribeAgent initialized with model: %s", self._model)

    def generate_documentation(
        self,
        execution_record: FlowExecutionRecord,
        codebase_summary: str,
    ) -> ScribeOutput:
        """
        Main entry point: Generate developer documentation for an executed flow.

        Args:
            execution_record: Complete record of the flow execution with step records
            codebase_summary: Codebase knowledge from discovery agent

        Returns:
            ScribeOutput with the final markdown documentation
        """
        logger.info(
            "Generating documentation for flow: %s (%d steps)",
            execution_record.flow_name,
            len(execution_record.steps),
        )

        # Pass 1: Structured analysis
        execution_summary = self._build_execution_summary(execution_record)
        analysis_json = self._analyze_flow(
            codebase_summary=codebase_summary,
            flow_markdown=execution_record.flow_markdown,
            execution_summary=execution_summary,
        )
        logger.info("Analysis pass complete (%d chars)", len(analysis_json))

        # Pass 2: Documentation generation with screenshots
        screenshot_list = self._build_screenshot_list(execution_record)
        documentation = self._generate_docs(
            analysis_json=analysis_json,
            screenshot_list=screenshot_list,
            codebase_summary=codebase_summary,
            screenshot_paths=execution_record.screenshot_paths,
        )
        logger.info("Documentation pass complete (%d chars)", len(documentation))

        return ScribeOutput(
            flow_name=execution_record.flow_name,
            documentation_markdown=documentation,
            flow_execution=execution_record,
            codebase_summary=codebase_summary,
        )

    def _build_execution_summary(self, record: FlowExecutionRecord) -> str:
        """Build a text summary of the execution record for the analysis prompt."""
        lines = [
            f"**Flow**: {record.flow_name}",
            f"**URL**: {record.start_url}",
            f"**Success**: {record.success}",
        ]
        if record.duration_seconds is not None:
            lines.append(f"**Duration**: {record.duration_seconds:.1f}s")

        lines.append(f"**Screenshot Directory**: {record.screenshot_dir}")
        lines.append("")
        lines.append("### Executed Steps")

        for step in record.steps:
            lines.append(f"\n**Step {step.step_number}: {step.action.upper()}**")
            lines.append(f"- Target: {step.target_element}")
            if step.matched_element:
                lines.append(f"- Matched: {step.matched_element} ({step.match_type})")
            if step.value:
                lines.append(f"- Value: {step.value}")
            lines.append(f"- Result: {step.result}")
            if step.error:
                lines.append(f"- ERROR: {step.error}")
            if step.screenshot_path:
                lines.append(f"- Screenshot: {Path(step.screenshot_path).name}")

            # Include a trimmed accessibility snapshot for context
            if step.accessibility_snapshot:
                snapshot_lines = step.accessibility_snapshot.strip().split("\n")
                # Keep first 30 lines to avoid bloating the prompt
                trimmed = snapshot_lines[:30]
                if len(snapshot_lines) > 30:
                    trimmed.append(f"... ({len(snapshot_lines) - 30} more lines)")
                lines.append("- Page snapshot (trimmed):")
                for sl in trimmed:
                    lines.append(f"  {sl}")

        return "\n".join(lines)

    def _build_screenshot_list(self, record: FlowExecutionRecord) -> str:
        """Build a formatted list of screenshots with step context."""
        lines = []
        for step in record.steps:
            if step.screenshot_path:
                name = Path(step.screenshot_path).name
                lines.append(
                    f"- `{name}` — Step {step.step_number}: "
                    f"{step.action} {step.target_element}"
                )
        return "\n".join(lines) if lines else "No screenshots captured."

    def _analyze_flow(
        self,
        codebase_summary: str,
        flow_markdown: str,
        execution_summary: str,
    ) -> str:
        """Pass 1: Produce structured analysis JSON."""
        prompt = format_analysis_prompt(
            codebase_summary=codebase_summary,
            flow_markdown=flow_markdown,
            execution_summary=execution_summary,
        )

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                temperature=0.0,
                system=ANALYSIS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text

        except Exception as e:
            logger.error("Analysis pass failed: %s", str(e), exc_info=True)
            raise

    def _generate_docs(
        self,
        analysis_json: str,
        screenshot_list: str,
        codebase_summary: str,
        screenshot_paths: List[str],
    ) -> str:
        """Pass 2: Generate final documentation with screenshots as visual context."""
        prompt_text = format_documentation_prompt(
            analysis_json=analysis_json,
            screenshot_list=screenshot_list,
        )

        # Build message content: text prompt + screenshot images
        content: list = [{"type": "text", "text": prompt_text}]

        for spath in screenshot_paths:
            image_data = self._load_screenshot(spath)
            if image_data:
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data,
                        },
                    }
                )
                content.append(
                    {
                        "type": "text",
                        "text": f"[Screenshot: {Path(spath).name}]",
                    }
                )

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=8192,
                temperature=0.0,
                system=DOCUMENTATION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}],
            )
            return response.content[0].text

        except Exception as e:
            logger.error("Documentation pass failed: %s", str(e), exc_info=True)
            raise

    def _load_screenshot(self, path: str) -> Optional[str]:
        """Load a screenshot file and return base64-encoded data."""
        try:
            filepath = Path(path)
            if filepath.exists() and filepath.stat().st_size > 0:
                with open(filepath, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.warning("Could not load screenshot %s: %s", path, e)
        return None
