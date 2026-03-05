"""Metadata Validator - Validates completeness of extracted flow metadata."""

from __future__ import annotations

import re
from typing import List, Dict, Any, Optional

from src.common.logger import get_logger
from .types import MetadataGap

logger = get_logger(__name__)


class MetadataValidator:
    """
    Validates extracted flows for metadata completeness.
    
    Checks for:
    - [UNKNOWN] markers in metadata fields
    - Required fields (role, accessible_name)
    - Input-specific requirements (type, label/placeholder)
    - Missing test identifiers
    """

    # Required fields for all elements
    REQUIRED_FIELDS = ["role", "accessible_name"]
    
    # Additional required fields for input elements
    INPUT_REQUIRED_FIELDS = ["type"]
    
    # At least one of these should be present for inputs
    INPUT_RECOMMENDED_FIELDS = ["label", "placeholder"]

    def identify_gaps(self, flows_markdown: str) -> List[MetadataGap]:
        """
        Identify metadata gaps in extracted flows.
        
        Args:
            flows_markdown: Flows in markdown format
            
        Returns:
            List of MetadataGap objects
        """
        logger.info("Validating metadata completeness")
        
        gaps: List[MetadataGap] = []
        
        # Parse flows from markdown
        flows = self._parse_flows(flows_markdown)
        
        for flow in flows:
            flow_name = flow["name"]
            
            for step in flow["steps"]:
                step_index = step["step_number"]
                element_desc = step["description"]
                
                # Check for missing metadata
                missing_fields = self._check_missing_metadata(step)
                
                if missing_fields:
                    suggested_query = self._generate_query(
                        flow_name, step_index, element_desc, missing_fields, step.get("source_file")
                    )
                    
                    gap = MetadataGap(
                        flow_name=flow_name,
                        step_index=step_index,
                        element_description=element_desc,
                        missing_fields=missing_fields,
                        suggested_query=suggested_query,
                        context=step.get("source_file")
                    )
                    gaps.append(gap)
        
        logger.info("Found %d metadata gaps", len(gaps))
        return gaps

    def _parse_flows(self, markdown: str) -> List[Dict[str, Any]]:
        """
        Parse markdown into structured flow data.
        
        Args:
            markdown: Flows in markdown format
            
        Returns:
            List of flow dictionaries
        """
        flows = []
        
        # Split by flow headers (## Flow X:)
        flow_pattern = r"## Flow \d+: (.+?)(?=\n## Flow |\Z)"
        flow_matches = re.finditer(flow_pattern, markdown, re.DOTALL)
        
        for flow_match in flow_matches:
            flow_name = flow_match.group(1).split("(")[0].strip()
            flow_content = flow_match.group(0)
            
            # Extract steps
            steps = self._parse_steps(flow_content)
            
            flows.append({
                "name": flow_name,
                "steps": steps
            })
        
        return flows

    def _parse_steps(self, flow_content: str) -> List[Dict[str, Any]]:
        """
        Parse steps from flow content.
        
        Args:
            flow_content: Content of a single flow
            
        Returns:
            List of step dictionaries
        """
        steps = []
        
        # Split by step headers (### Step X:)
        step_pattern = r"### Step (\d+): (\w+) (.+?)(?=\n### Step |\n## Flow |\Z)"
        step_matches = re.finditer(step_pattern, flow_content, re.DOTALL)
        
        for step_match in step_matches:
            step_num = int(step_match.group(1))
            action_type = step_match.group(2).upper()
            description = step_match.group(3).split("\n")[0].strip()
            step_content = step_match.group(0)
            
            # Extract metadata from step
            metadata = self._extract_metadata(step_content)
            
            # Extract source file
            source_match = re.search(r"\*\*Source\*\*:?\s*`?([^`\n]+)`?", step_content)
            source_file = source_match.group(1) if source_match else None
            
            steps.append({
                "step_number": step_num,
                "action": action_type,
                "description": description,
                "metadata": metadata,
                "source_file": source_file
            })
        
        return steps

    def _extract_metadata(self, step_content: str) -> Dict[str, str]:
        """
        Extract metadata fields from step content.
        
        Args:
            step_content: Content of a single step
            
        Returns:
            Dictionary of metadata field -> value
        """
        metadata = {}
        
        # Common patterns for metadata fields
        patterns = {
            "role": r"\*\*Role\*\*:?\s*`?([^`\n]+)`?",
            "accessible_name": r"\*\*Accessible Name\*\*:?\s*[\"']?([^\"'\n]+)[\"']?",
            "type": r"\*\*Type\*\*:?\s*`?([^`\n]+)`?",
            "placeholder": r"\*\*Placeholder\*\*:?\s*[\"']?([^\"'\n]+)[\"']?",
            "label": r"\*\*Label\*\*:?\s*[\"']?([^\"'\n]+)[\"']?",
            "name": r"\*\*Name\*\*:?\s*[\"']?([^\"'\n]+)[\"']?",
            "test_id": r"\*\*Test ID\*\*:?\s*`?([^`\n]+)`?",
            "context": r"\*\*Context\*\*:?\s*([^\n]+)",
        }
        
        for field, pattern in patterns.items():
            match = re.search(pattern, step_content, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                metadata[field] = value
        
        return metadata

    def _check_missing_metadata(self, step: Dict[str, Any]) -> List[str]:
        """
        Check if step has missing or incomplete metadata.
        
        Args:
            step: Step dictionary with metadata
            
        Returns:
            List of missing field names
        """
        missing = []
        metadata = step.get("metadata", {})
        action = step.get("action", "")
        
        # Skip NAVIGATE actions (no element metadata needed)
        if action == "NAVIGATE":
            return []
        
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            value = metadata.get(field, "")
            if not value or "[UNKNOWN]" in value.upper():
                missing.append(field)
        
        # Check input-specific requirements
        if action in ["FILL", "SELECT"] or "input" in step["description"].lower():
            # Check input required fields
            for field in self.INPUT_REQUIRED_FIELDS:
                value = metadata.get(field, "")
                if not value or "[UNKNOWN]" in value.upper():
                    missing.append(field)
            
            # Check if at least one of label/placeholder exists
            has_label_or_placeholder = any(
                metadata.get(field) and "[UNKNOWN]" not in metadata.get(field, "").upper()
                for field in self.INPUT_RECOMMENDED_FIELDS
            )
            if not has_label_or_placeholder:
                missing.extend([f for f in self.INPUT_RECOMMENDED_FIELDS if f not in missing])
        
        # Check for test_id (recommended but not required)
        test_id = metadata.get("test_id", "")
        if not test_id or "[UNKNOWN]" in test_id.upper():
            missing.append("test_id")
        
        return missing

    def _generate_query(
        self,
        flow_name: str,
        step_index: int,
        element_desc: str,
        missing_fields: List[str],
        source_file: Optional[str]
    ) -> str:
        """
        Generate a specific query for missing metadata.
        
        Args:
            flow_name: Name of the flow
            step_index: Step number
            element_desc: Description of the element
            missing_fields: List of missing field names
            source_file: Source file reference
            
        Returns:
            Natural language query string
        """
        # Create human-readable field names
        field_names = {
            "role": "HTML element type or ARIA role",
            "accessible_name": "visible text or aria-label",
            "type": "input type attribute",
            "placeholder": "placeholder text",
            "label": "label text",
            "name": "name attribute",
            "test_id": "data-testid or test identifier attribute",
            "context": "parent component or container"
        }
        
        readable_fields = [field_names.get(f, f) for f in missing_fields]
        fields_str = ", ".join(readable_fields)
        
        # Build query
        query_parts = [
            f"In the '{flow_name}' flow (Step {step_index}),",
            f"for the '{element_desc}',",
            f"what is the {fields_str}?"
        ]
        
        if source_file:
            query_parts.append(f"(Located in {source_file})")
        
        return " ".join(query_parts)


# Convenience function
def validate_metadata(flows_markdown: str) -> List[MetadataGap]:
    """
    Convenience function to validate metadata without instantiating validator.
    
    Args:
        flows_markdown: Flows in markdown format
        
    Returns:
        List of MetadataGap objects
    """
    validator = MetadataValidator()
    return validator.identify_gaps(flows_markdown)
