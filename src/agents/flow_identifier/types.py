"""Type definitions for Flow Identifier agent."""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class Priority(str, Enum):
    """Priority levels for user flows."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ActionType(str, Enum):
    """Types of actions in a flow step."""
    NAVIGATE = "NAVIGATE"
    CLICK = "CLICK"
    FILL = "FILL"
    SELECT = "SELECT"
    CHECK = "CHECK"
    UNCHECK = "UNCHECK"
    UPLOAD = "UPLOAD"
    WAIT = "WAIT"
    VERIFY = "VERIFY"


@dataclass
class ElementMetadata:
    """
    Metadata for a UI element that can be extracted from code.
    All fields follow Playwright best practices for element selection.
    """
    # REQUIRED for all elements
    role: Optional[str] = None  # HTML tag (button, input, a) or ARIA role
    accessible_name: Optional[str] = None  # Visible text, aria-label, label text, title
    
    # Input-specific metadata
    type: Optional[str] = None  # For inputs: text, email, password, checkbox, etc.
    placeholder: Optional[str] = None  # Placeholder text
    label: Optional[str] = None  # Associated label text
    name: Optional[str] = None  # Name attribute
    
    # Test identifiers
    test_id: Optional[str] = None  # data-testid, data-test, data-cy
    
    # Context for disambiguation
    context: Optional[str] = None  # Parent component/container
    page_location: Optional[str] = None  # Page or route where element appears
    
    # State attributes
    aria_attributes: dict = field(default_factory=dict)  # aria-expanded, aria-checked, etc.
    html_attributes: dict = field(default_factory=dict)  # disabled, required, etc.
    
    # Additional metadata
    additional_info: Optional[str] = None  # Any other relevant information


@dataclass
class FlowStep:
    """A single step in a user flow."""
    step_number: int
    action: ActionType
    description: str
    
    # Element metadata (None for NAVIGATE actions)
    element_metadata: Optional[ElementMetadata] = None
    
    # Action-specific data
    value: Optional[str] = None  # Value to fill/select
    url: Optional[str] = None  # For NAVIGATE actions
    
    # Expected outcome
    expected_outcome: str = ""
    
    # Source location
    source_files: List[str] = field(default_factory=list)


@dataclass
class Flow:
    """A complete user flow with multiple steps."""
    name: str
    priority: Priority
    description: str
    steps: List[FlowStep] = field(default_factory=list)
    source_files: List[str] = field(default_factory=list)
    
    # Metadata about the flow
    estimated_duration: Optional[str] = None  # e.g., "2-3 seconds"
    prerequisites: List[str] = field(default_factory=list)  # Required state/data
    

@dataclass
class MetadataGap:
    """Represents missing metadata that needs clarification."""
    flow_name: str
    step_index: int
    element_description: str
    missing_fields: List[str]
    suggested_query: str
    
    # Context for better query generation
    context: Optional[str] = None


@dataclass
class FlowIdentificationResult:
    """Result of flow identification process."""
    flows_markdown: str
    followup_queries: Optional[List[str]] = None
    metadata_gaps: List[MetadataGap] = field(default_factory=list)
    is_complete: bool = True  # False if there are metadata gaps
