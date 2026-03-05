"""Flow Identifier Agent - Extract critical user flows with maximum metadata."""

from .agent import FlowIdentifierAgent, identify_flows
from .types import (
    FlowIdentificationResult,
    MetadataGap,
    Flow,
    FlowStep,
    ElementMetadata,
    Priority,
    ActionType,
)
from .metadata_validator import MetadataValidator, validate_metadata
from .metadata_requester import MetadataRequester, generate_followup_queries

__all__ = [
    # Main agent
    "FlowIdentifierAgent",
    "identify_flows",
    # Types
    "FlowIdentificationResult",
    "MetadataGap",
    "Flow",
    "FlowStep",
    "ElementMetadata",
    "Priority",
    "ActionType",
    # Validators and requesters
    "MetadataValidator",
    "validate_metadata",
    "MetadataRequester",
    "generate_followup_queries",
]
