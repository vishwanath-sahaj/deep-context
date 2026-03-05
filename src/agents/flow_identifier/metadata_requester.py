"""Metadata Requester - Generates followup queries for missing metadata."""

from __future__ import annotations

from typing import List, Set
from collections import defaultdict

from src.common.logger import get_logger
from .types import MetadataGap

logger = get_logger(__name__)


class MetadataRequester:
    """
    Generates followup queries for missing metadata.
    
    Takes MetadataGap objects and constructs specific, targeted queries
    that can be used with the codebase tool to extract missing metadata.
    """

    def generate_queries(self, gaps: List[MetadataGap]) -> List[str]:
        """
        Generate followup queries from metadata gaps.
        
        Args:
            gaps: List of MetadataGap objects
            
        Returns:
            List of unique, specific natural language queries
        """
        if not gaps:
            logger.info("No metadata gaps, no queries to generate")
            return []
        
        logger.info("Generating queries for %d metadata gaps", len(gaps))
        
        queries = []
        
        # Group gaps by flow and element to avoid duplicate queries
        grouped_gaps = self._group_gaps(gaps)
        
        for key, gap_list in grouped_gaps.items():
            query = self._build_combined_query(gap_list)
            queries.append(query)
        
        # Deduplicate queries
        unique_queries = list(set(queries))
        
        logger.info("Generated %d unique queries", len(unique_queries))
        return unique_queries

    def _group_gaps(self, gaps: List[MetadataGap]) -> dict:
        """
        Group gaps by flow and element to combine similar queries.
        
        Args:
            gaps: List of MetadataGap objects
            
        Returns:
            Dictionary mapping (flow_name, step_index) -> list of gaps
        """
        grouped = defaultdict(list)
        
        for gap in gaps:
            key = (gap.flow_name, gap.step_index, gap.element_description)
            grouped[key].append(gap)
        
        return grouped

    def _build_combined_query(self, gaps: List[MetadataGap]) -> str:
        """
        Build a combined query for multiple gaps on the same element.
        
        Args:
            gaps: List of gaps for the same element
            
        Returns:
            Combined natural language query
        """
        # All gaps should be for the same element
        first_gap = gaps[0]
        
        # Collect all missing fields
        all_missing_fields: Set[str] = set()
        for gap in gaps:
            all_missing_fields.update(gap.missing_fields)
        
        # Build query using the helper
        return self._build_query(
            first_gap.flow_name,
            first_gap.step_index,
            first_gap.element_description,
            list(all_missing_fields),
            first_gap.context
        )

    def _build_query(
        self,
        flow_name: str,
        step_index: int,
        element_description: str,
        missing_fields: List[str],
        context: str | None
    ) -> str:
        """
        Build a specific query for missing metadata.
        
        Args:
            flow_name: Name of the flow
            step_index: Step number
            element_description: Description of the element
            missing_fields: List of missing field names
            context: Source file or context
            
        Returns:
            Natural language query string
        """
        # Create human-readable field descriptions
        field_descriptions = {
            "role": "the HTML element type (e.g., button, input, div) or ARIA role",
            "accessible_name": "the visible text, aria-label, or accessible name",
            "type": "the input type attribute (e.g., text, email, password)",
            "placeholder": "the placeholder text",
            "label": "the associated label text",
            "name": "the name attribute",
            "test_id": "the data-testid, data-test, or data-cy attribute",
            "context": "the parent component or container name"
        }
        
        # Build readable list of what we're looking for
        field_queries = []
        for field in missing_fields:
            desc = field_descriptions.get(field, field)
            field_queries.append(desc)
        
        # Format the list nicely
        if len(field_queries) == 1:
            fields_text = field_queries[0]
        elif len(field_queries) == 2:
            fields_text = f"{field_queries[0]} and {field_queries[1]}"
        else:
            fields_text = ", ".join(field_queries[:-1]) + f", and {field_queries[-1]}"
        
        # Build the query
        query_parts = [
            f"In the '{flow_name}' flow",
        ]
        
        # Add step info if relevant
        if step_index > 0:
            query_parts.append(f"(Step {step_index})")
        
        query_parts.extend([
            f"for the '{element_description}',",
            f"what is {fields_text}?"
        ])
        
        # Add context/source file if available
        if context:
            query_parts.append(f"Check in {context}.")
        
        query = " ".join(query_parts)
        
        return query


# Convenience function
def generate_followup_queries(gaps: List[MetadataGap]) -> List[str]:
    """
    Convenience function to generate queries without instantiating requester.
    
    Args:
        gaps: List of MetadataGap objects
        
    Returns:
        List of unique natural language queries
    """
    requester = MetadataRequester()
    return requester.generate_queries(gaps)
