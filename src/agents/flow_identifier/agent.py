"""Flow Identifier Agent - Extracts critical user flows with maximum metadata."""

from __future__ import annotations

import json
from typing import Optional, Tuple, List

import anthropic

from src.common.config import config
from src.common.logger import get_logger
from .prompts import (
    FLOW_IDENTIFIER_SYSTEM_PROMPT,
    format_flow_identification_prompt,
    format_metadata_validation_prompt,
    format_metadata_refinement_prompt,
)
from .types import FlowIdentificationResult, MetadataGap

logger = get_logger(__name__)


class FlowIdentifierAgent:
    """
    Standalone agent for identifying critical user flows with rich metadata.
    
    This agent analyzes frontend codebases and extracts user flows with maximum
    element metadata for Playwright automation. It can detect missing metadata
    and request clarification through followup queries.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Flow Identifier Agent.
        
        Args:
            api_key: Optional Anthropic API key (uses config if not provided)
        """
        self._client = anthropic.Anthropic(api_key=api_key or config.CLAUDE_API_KEY)
        self._model = "claude-sonnet-4-5"
        logger.info("FlowIdentifierAgent initialized with model: %s", self._model)

    def identify_flows(
        self,
        codebase_summary: str,
        request_missing_metadata: bool = True
    ) -> FlowIdentificationResult:
        """
        Main entry point: Extract flows from codebase summary.
        
        Args:
            codebase_summary: Natural language description of the codebase
            request_missing_metadata: If True, validates metadata and generates followup queries
            
        Returns:
            FlowIdentificationResult with flows markdown and optional followup queries
        """
        logger.info("Starting flow identification (request_missing_metadata=%s)", request_missing_metadata)
        
        # Step 1: Extract flows from codebase summary
        flows_markdown = self._extract_flows(codebase_summary)
        logger.info("Extracted flows (length: %d chars)", len(flows_markdown))
        
        # Step 2: Optionally validate metadata and generate followup queries
        if request_missing_metadata:
            metadata_gaps = self._validate_metadata(flows_markdown)
            
            if metadata_gaps:
                logger.info("Found %d metadata gaps", len(metadata_gaps))
                followup_queries = self._generate_followup_queries(metadata_gaps)
                
                return FlowIdentificationResult(
                    flows_markdown=flows_markdown,
                    followup_queries=followup_queries,
                    metadata_gaps=metadata_gaps,
                    is_complete=False
                )
            else:
                logger.info("All metadata is complete")
        
        return FlowIdentificationResult(
            flows_markdown=flows_markdown,
            followup_queries=None,
            metadata_gaps=[],
            is_complete=True
        )

    def refine_with_additional_context(
        self,
        initial_flows: str,
        additional_context: str
    ) -> str:
        """
        Refine flows by filling in [UNKNOWN] fields with additional metadata.
        
        Args:
            initial_flows: Original flows markdown with [UNKNOWN] markers
            additional_context: Additional metadata from followup queries
            
        Returns:
            Updated flows markdown with filled metadata
        """
        logger.info("Refining flows with additional context")
        
        prompt = format_metadata_refinement_prompt(initial_flows, additional_context)
        
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=8192,
                temperature=0.0,
                system=FLOW_IDENTIFIER_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            
            refined_flows = response.content[0].text
            logger.info("Successfully refined flows (length: %d chars)", len(refined_flows))
            return refined_flows
            
        except Exception as e:
            logger.error("Error refining flows: %s", str(e), exc_info=True)
            raise

    def _extract_flows(self, codebase_summary: str) -> str:
        """
        Extract flows from codebase summary using Claude.
        
        Args:
            codebase_summary: Natural language codebase description
            
        Returns:
            Structured markdown with flows and metadata
        """
        prompt = format_flow_identification_prompt(codebase_summary)
        
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=8192,
                temperature=0.0,
                system=FLOW_IDENTIFIER_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            
            flows_markdown = response.content[0].text
            return flows_markdown
            
        except Exception as e:
            logger.error("Error extracting flows: %s", str(e), exc_info=True)
            raise

    def _validate_metadata(self, flows_markdown: str) -> List[MetadataGap]:
        """
        Validate flows for missing metadata and identify gaps.
        
        Args:
            flows_markdown: Extracted flows in markdown format
            
        Returns:
            List of MetadataGap objects representing missing metadata
        """
        prompt = format_metadata_validation_prompt(flows_markdown)
        
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                temperature=0.0,
                system="You are a metadata validation expert. Analyze flows and identify missing metadata that would be extractable from code.",
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )
            
            validation_result = response.content[0].text
            
            # Parse JSON response
            # Extract JSON from markdown code blocks if present
            if "```json" in validation_result:
                json_start = validation_result.find("```json") + 7
                json_end = validation_result.find("```", json_start)
                json_str = validation_result[json_start:json_end].strip()
            elif "```" in validation_result:
                json_start = validation_result.find("```") + 3
                json_end = validation_result.find("```", json_start)
                json_str = validation_result[json_start:json_end].strip()
            else:
                json_str = validation_result.strip()
            
            gaps_data = json.loads(json_str)
            
            # Convert to MetadataGap objects
            metadata_gaps = [
                MetadataGap(
                    flow_name=gap["flow_name"],
                    step_index=gap["step_index"],
                    element_description=gap["element_description"],
                    missing_fields=gap["missing_fields"],
                    suggested_query=gap["suggested_query"],
                    context=gap.get("context")
                )
                for gap in gaps_data
            ]
            
            return metadata_gaps
            
        except Exception as e:
            logger.error("Error validating metadata: %s", str(e), exc_info=True)
            # Return empty list on error - don't block flow identification
            return []

    def _generate_followup_queries(self, metadata_gaps: List[MetadataGap]) -> List[str]:
        """
        Generate followup queries from metadata gaps.
        
        Args:
            metadata_gaps: List of identified metadata gaps
            
        Returns:
            List of natural language queries for codebase tool
        """
        # Extract suggested queries from gaps and deduplicate
        queries = list(set(gap.suggested_query for gap in metadata_gaps))
        
        logger.info("Generated %d unique followup queries", len(queries))
        return queries


# Convenience function for direct usage
def identify_flows(
    codebase_summary: str,
    request_missing_metadata: bool = True
) -> FlowIdentificationResult:
    """
    Convenience function to identify flows without instantiating agent.
    
    Args:
        codebase_summary: Natural language description of the codebase
        request_missing_metadata: If True, validates metadata and generates followup queries
        
    Returns:
        FlowIdentificationResult with flows markdown and optional followup queries
    """
    agent = FlowIdentifierAgent()
    return agent.identify_flows(codebase_summary, request_missing_metadata)
