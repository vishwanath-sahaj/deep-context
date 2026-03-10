"""Type definitions for Orchestrator Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentType(str, Enum):
    """Types of agents available in the orchestrator."""
    DISCOVERY = "discovery"
    FLOW_IDENTIFIER = "flow_identifier"
    ACTION = "action"
    SCRIBE = "scribe"


class OrchestratorPhase(str, Enum):
    """Current phase of orchestration."""
    IDLE = "idle"
    DISCOVERY = "discovery"
    FLOW_IDENTIFICATION = "flow_identification"
    ACTION_EXECUTION = "action_execution"
    DOCUMENTATION = "documentation"
    ERROR_RECOVERY = "error_recovery"
    COMPLETED = "completed"
    FAILED = "failed"


class ErrorType(str, Enum):
    """Types of errors that can occur during orchestration."""
    ELEMENT_NOT_FOUND = "element_not_found"
    NAVIGATION_FAILED = "navigation_failed"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    SELECTOR_INVALID = "selector_invalid"
    FLOW_INCOMPLETE = "flow_incomplete"
    MCP_CONNECTION_FAILED = "mcp_connection_failed"
    UNKNOWN = "unknown"


@dataclass
class AgentError:
    """Represents an error from an agent execution."""
    agent_type: AgentType
    error_type: ErrorType
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    recoverable: bool = True
    
    @classmethod
    def from_exception(cls, agent_type: AgentType, exc: Exception) -> "AgentError":
        """Create an AgentError from an exception."""
        error_str = str(exc).lower()
        
        # Classify error type based on message
        if "element" in error_str and ("not found" in error_str or "could not find" in error_str):
            error_type = ErrorType.ELEMENT_NOT_FOUND
        elif "navigation" in error_str or "navigate" in error_str:
            error_type = ErrorType.NAVIGATION_FAILED
        elif "timeout" in error_str or "timed out" in error_str:
            error_type = ErrorType.TIMEOUT
        elif "permission" in error_str or "access denied" in error_str or "403" in error_str:
            error_type = ErrorType.PERMISSION_DENIED
        elif "selector" in error_str or "ref" in error_str:
            error_type = ErrorType.SELECTOR_INVALID
        elif "mcp" in error_str or "playwright" in error_str:
            error_type = ErrorType.MCP_CONNECTION_FAILED
        else:
            error_type = ErrorType.UNKNOWN
        
        return cls(
            agent_type=agent_type,
            error_type=error_type,
            message=str(exc),
            recoverable=error_type not in [ErrorType.PERMISSION_DENIED, ErrorType.MCP_CONNECTION_FAILED],
        )


@dataclass
class RecoveryAction:
    """Describes a recovery action to take after an error."""
    action: str  # Description of what to do
    target_agent: AgentType  # Which agent to invoke
    additional_context: Optional[str] = None  # Extra info to pass
    refinement_query: Optional[str] = None  # Query to refine flows


@dataclass
class OrchestratorState:
    """Current state of the orchestrator."""
    phase: OrchestratorPhase = OrchestratorPhase.IDLE
    
    # Inputs
    repo_path: Optional[str] = None
    target_url: Optional[str] = None
    initial_query: Optional[str] = None
    
    # Intermediate results
    discovery_result: Optional[Any] = None  # DiscoveryResult
    flows_markdown: Optional[str] = None
    parsed_flows: List[Any] = field(default_factory=list)  # List[ParsedFlow]
    current_flow_index: int = 0
    
    # Error tracking
    errors: List[AgentError] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    
    # Outputs
    scribe_outputs: List[Any] = field(default_factory=list)  # List[ScribeOutput]
    
    # Timing
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None
    
    @property
    def has_recoverable_error(self) -> bool:
        """Check if the latest error is recoverable."""
        if not self.errors:
            return False
        return self.errors[-1].recoverable and self.retry_count < self.max_retries
    
    @property
    def last_error(self) -> Optional[AgentError]:
        """Get the last error if any."""
        return self.errors[-1] if self.errors else None


@dataclass
class OrchestratorResult:
    """Final result from orchestrator execution."""
    success: bool
    state: OrchestratorState
    scribe_outputs: List[Any]  # List[ScribeOutput]
    
    # Summary
    total_flows_discovered: int = 0
    flows_executed_successfully: int = 0
    flows_failed: int = 0
    
    # Error summary
    errors: List[AgentError] = field(default_factory=list)
    recovery_attempts: int = 0
    
    @property
    def documentation_paths(self) -> List[str]:
        """Get paths to generated documentation."""
        # This would be populated after saving docs
        return []


@dataclass 
class ToolResult:
    """Result from a tool invocation."""
    tool_name: str
    success: bool
    output: Any
    error: Optional[AgentError] = None
    duration_seconds: Optional[float] = None
