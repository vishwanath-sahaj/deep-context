"""Type definitions for Discovery Agent."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class DiscoveryResult:
    """Result of flow discovery process."""
    
    # Primary output
    flows_markdown: str
    """Structured markdown with critical flows and metadata."""
    
    # Supporting context
    codebase_summary: str
    """Combined summary from codebase queries."""
    
    sources: List[str]
    """List of source files analyzed."""
    
    # Metadata
    followup_queries_used: List[str] = field(default_factory=list)
    """Queries used to refine metadata."""
    
    is_complete: bool = True
    """Whether all metadata was successfully extracted."""
    
    timestamp: datetime = field(default_factory=datetime.now)
    """When discovery was performed."""
    
    # Statistics
    num_flows: int = 0
    """Number of flows identified."""
    
    num_refinement_iterations: int = 0
    """Number of metadata refinement passes."""


@dataclass
class ExplorationQuery:
    """A strategic query for codebase exploration."""
    
    query: str
    """Natural language query."""
    
    purpose: str
    """What this query aims to discover."""
    
    priority: int = 1
    """Execution priority (1=highest)."""
