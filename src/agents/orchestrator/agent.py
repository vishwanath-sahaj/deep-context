"""
Orchestrator Agent: A React-style agent that orchestrates all sub-agents as tools.

This agent manages the full pipeline:
1. Discovery Agent - Explores codebase and identifies flows
2. Flow Identifier Agent - Extracts detailed flow metadata
3. Action Agent - Executes flows in browser via Playwright
4. Scribe Agent - Generates documentation

Error Handling:
- If ActionAgent fails, re-routes to DiscoveryAgent to check permissions/selectors
- Then re-runs FlowIdentifier to refine flows
- Retries ActionAgent with refined flows
- Finally generates documentation with ScribeAgent
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.common.config import config
from src.common.logger import get_logger
from .types import (
    AgentError,
    AgentType,
    ErrorType,
    OrchestratorPhase,
    OrchestratorResult,
    OrchestratorState,
    RecoveryAction,
    ToolResult,
)

logger = get_logger(__name__)
console = Console()


# ---------------------------------------------------------------------------
# Tool Definitions for Claude
# ---------------------------------------------------------------------------

ORCHESTRATOR_TOOLS = [
    {
        "name": "discovery_agent",
        "description": """Explores a codebase to understand its structure, UI components, routes, and forms.
Use this tool to:
- Initial codebase exploration
- Find UI components and their selectors
- Identify routes and navigation patterns
- Re-check element selectors after action failures
- Verify permissions and access patterns

Input: repo_path (string), force_reindex (boolean, optional)
Output: DiscoveryResult with flows_markdown and codebase_summary""",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the repository to analyze"
                },
                "force_reindex": {
                    "type": "boolean",
                    "description": "Whether to force re-indexing of the repository",
                    "default": False
                },
                "custom_query": {
                    "type": "string",
                    "description": "Optional custom query to focus the exploration"
                }
            },
            "required": ["repo_path"]
        }
    },
    {
        "name": "flow_identifier_agent",
        "description": """Extracts critical user flows with detailed metadata for automation.
Use this tool to:
- Identify 2-3 critical user flows from codebase context
- Extract element metadata (selectors, roles, accessible names)
- Refine flows with additional context after errors

Input: codebase_summary (string), additional_context (string, optional)
Output: FlowIdentificationResult with flows_markdown""",
        "input_schema": {
            "type": "object",
            "properties": {
                "codebase_summary": {
                    "type": "string",
                    "description": "Summary of the codebase from discovery agent"
                },
                "existing_flows": {
                    "type": "string",
                    "description": "Existing flows markdown to refine (optional)"
                },
                "additional_context": {
                    "type": "string",
                    "description": "Additional context for refinement (e.g., error details)"
                },
                "focus_elements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific elements to focus on for better selectors"
                }
            },
            "required": ["codebase_summary"]
        }
    },
    {
        "name": "action_agent",
        "description": """Executes UI flows in a browser using Playwright MCP.
Use this tool to:
- Execute identified flows on a live application
- Interact with UI elements (click, fill, select, etc.)
- Take screenshots during execution

Returns detailed step-by-step execution results.
IMPORTANT: This tool may fail if selectors are wrong - in that case, use discovery_agent to investigate.

Input: flow_markdown (string), target_url (string)
Output: Execution result with screenshots""",
        "input_schema": {
            "type": "object",
            "properties": {
                "flow_markdown": {
                    "type": "string",
                    "description": "The flow definition in markdown format"
                },
                "target_url": {
                    "type": "string",
                    "description": "The URL to execute the flow against"
                }
            },
            "required": ["flow_markdown", "target_url"]
        }
    },
    {
        "name": "scribe_agent",
        "description": """Generates developer documentation from flow executions.
Use this tool ONLY after successful action execution.

Input: execution_record, codebase_summary
Output: ScribeOutput with documentation_markdown""",
        "input_schema": {
            "type": "object",
            "properties": {
                "flow_name": {
                    "type": "string",
                    "description": "Name of the flow"
                },
                "flow_markdown": {
                    "type": "string",
                    "description": "Original flow definition"
                },
                "execution_result": {
                    "type": "string",
                    "description": "Result from action agent execution"
                },
                "codebase_summary": {
                    "type": "string",
                    "description": "Codebase context from discovery"
                },
                "start_url": {
                    "type": "string",
                    "description": "URL where flow was executed"
                }
            },
            "required": ["flow_name", "flow_markdown", "execution_result", "codebase_summary", "start_url"]
        }
    },
    {
        "name": "analyze_error",
        "description": """Analyzes an error from action execution to determine recovery strategy.
Use this to understand why an action failed and what to do next.

Input: error_message, flow_context
Output: Recovery recommendation""",
        "input_schema": {
            "type": "object",
            "properties": {
                "error_message": {
                    "type": "string",
                    "description": "The error message from the failed action"
                },
                "flow_name": {
                    "type": "string",
                    "description": "Name of the flow that failed"
                },
                "failed_step": {
                    "type": "string",
                    "description": "The step that failed"
                },
                "element_description": {
                    "type": "string",
                    "description": "Description of the element that couldn't be found"
                }
            },
            "required": ["error_message"]
        }
    }
]


# ---------------------------------------------------------------------------
# System Prompt for the Orchestrator
# ---------------------------------------------------------------------------

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are an intelligent orchestrator agent that manages a pipeline of specialized agents for codebase analysis and UI automation.

## Your Agents (Tools)

1. **discovery_agent**: Explores codebases to understand structure, components, and selectors
2. **flow_identifier_agent**: Extracts user flows with detailed element metadata
3. **action_agent**: Executes flows in a browser via Playwright
4. **scribe_agent**: Generates documentation from successful executions
5. **analyze_error**: Analyzes failures to determine recovery strategy

## Standard Pipeline

1. Run `discovery_agent` to explore the codebase
2. Run `flow_identifier_agent` to extract flows
3. For each flow, run `action_agent` to execute it
4. If action succeeds, run `scribe_agent` to document it
5. If action fails, follow the error recovery protocol

## Error Recovery Protocol

When `action_agent` fails:

1. **Analyze the error** using `analyze_error` to understand what went wrong
2. **Check permissions/selectors**: Run `discovery_agent` with a focused query about the failing element
3. **Refine the flow**: Run `flow_identifier_agent` with the additional context and error details
4. **Retry the action**: Run `action_agent` with the refined flow
5. If still failing after 3 attempts, log the failure and move to the next flow

## Error Types and Recovery

- **ELEMENT_NOT_FOUND**: Re-run discovery to find correct selectors, then refine flow
- **NAVIGATION_FAILED**: Check if URL is correct, verify routes in codebase
- **TIMEOUT**: May indicate slow loading - add wait steps to flow
- **PERMISSION_DENIED**: This is NOT recoverable - skip the flow and report
- **SELECTOR_INVALID**: Re-run discovery with focus on the specific element

## Important Rules

1. Always start with discovery_agent for a new codebase
2. Never skip directly to action_agent without having flows
3. Always try to recover from failures before giving up
4. Document successful flows even if some flows failed
5. Provide clear status updates after each step
6. Maximum 3 retry attempts per flow
7. **CRITICAL**: Do NOT execute the same flow multiple times if it already succeeded
8. **CRITICAL**: Track which flows you've already executed to avoid duplicates

## When to Stop (Completion Criteria)

You are DONE and should stop when:

1. ✅ **All discovered flows have been executed once** (either successfully or after 3 retry attempts)
2. ✅ **Scribe documentation has been generated** for all successful flows
3. ✅ **Final summary has been provided** to the user

**DO NOT:**
- ❌ Re-execute flows that already succeeded
- ❌ Keep trying to "improve" or "refine" successful flows
- ❌ Run discovery again unless recovering from an error
- ❌ Keep iterating after all flows are complete

**After completing all flows, provide a final summary and STOP immediately.**

## Output Format

After completing all flows, provide a summary:
- Total flows discovered
- Flows executed successfully
- Flows failed (with reasons)
- Documentation generated

Then STOP. Do not continue executing tools after the summary.

Be concise but thorough. Focus on completing the task efficiently.
"""


class OrchestratorAgent:
    """
    React-style orchestrator that manages all sub-agents as tools.
    
    Features:
    - LLM-driven decision making using Claude
    - Automatic error recovery and re-routing
    - State tracking across the pipeline
    - Rich console output for progress
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the orchestrator agent."""
        self._api_key = api_key or config.CLAUDE_API_KEY
        self._client = anthropic.Anthropic(api_key=self._api_key)
        self._model = "claude-sonnet-4-5"
        
        # Sub-agents (lazy loaded)
        self._discovery_agent = None
        self._flow_identifier_agent = None
        self._action_agent = None
        self._scribe_agent = None
        
        # State
        self.state = OrchestratorState()
        
        logger.info("OrchestratorAgent initialized with model: %s", self._model)

    def _get_discovery_agent(self, repo_path: Path, force_reindex: bool = False):
        """Lazy load the discovery agent."""
        from src.agents.discovery import DiscoveryAgent
        
        if self._discovery_agent is None or force_reindex:
            self._discovery_agent = DiscoveryAgent(
                repo_path=repo_path,
                force_reindex=force_reindex
            )
        return self._discovery_agent

    def _get_flow_identifier_agent(self):
        """Lazy load the flow identifier agent."""
        from src.agents.flow_identifier import FlowIdentifierAgent
        
        if self._flow_identifier_agent is None:
            self._flow_identifier_agent = FlowIdentifierAgent(api_key=self._api_key)
        return self._flow_identifier_agent

    def _get_action_agent(self):
        """Lazy load the action agent."""
        from src.agents.action.agent import ActionAgent
        
        if self._action_agent is None:
            self._action_agent = ActionAgent()
        return self._action_agent

    def _get_scribe_agent(self):
        """Lazy load the scribe agent."""
        from src.agents.scribe import ScribeAgent
        
        if self._scribe_agent is None:
            if not self.state.repo_path:
                raise ValueError("repo_path must be set before creating ScribeAgent")
            self._scribe_agent = ScribeAgent(
                api_key=self._api_key,
                repo_path=Path(self.state.repo_path)
            )
        return self._scribe_agent

    # ---------------------------------------------------------------------------
    # Tool Handlers
    # ---------------------------------------------------------------------------

    async def _handle_discovery_agent(
        self,
        repo_path: str,
        force_reindex: bool = False,
        custom_query: Optional[str] = None
    ) -> ToolResult:
        """Execute the discovery agent."""
        start_time = datetime.now()
        try:
            console.print(Panel(
                f"[cyan]Running Discovery Agent[/cyan]\n"
                f"Repository: {repo_path}\n"
                f"Custom Query: {custom_query or 'None'}",
                title="Discovery"
            ))
            
            agent = self._get_discovery_agent(Path(repo_path), force_reindex)
            result = agent.discover_flows(initial_query=custom_query)
            
            # Update state
            self.state.discovery_result = result
            self.state.flows_markdown = result.flows_markdown
            self.state.phase = OrchestratorPhase.DISCOVERY
            
            duration = (datetime.now() - start_time).total_seconds()
            console.print(f"[green]Discovery completed in {duration:.1f}s[/green]")
            
            return ToolResult(
                tool_name="discovery_agent",
                success=True,
                output={
                    "flows_markdown": result.flows_markdown,
                    "codebase_summary": result.codebase_summary,
                    "num_flows": result.num_flows,
                    "sources": result.sources[:10],  # Limit for context
                },
                duration_seconds=duration
            )
        except Exception as e:
            logger.error("discovery_agent_failed", error=str(e))
            return ToolResult(
                tool_name="discovery_agent",
                success=False,
                output=None,
                error=AgentError.from_exception(AgentType.DISCOVERY, e)
            )

    async def _handle_flow_identifier_agent(
        self,
        codebase_summary: str,
        existing_flows: Optional[str] = None,
        additional_context: Optional[str] = None,
        focus_elements: Optional[List[str]] = None
    ) -> ToolResult:
        """Execute the flow identifier agent."""
        start_time = datetime.now()
        try:
            console.print(Panel(
                f"[cyan]Running Flow Identifier Agent[/cyan]\n"
                f"Refining: {'Yes' if existing_flows else 'No'}\n"
                f"Additional Context: {'Yes' if additional_context else 'No'}",
                title="Flow Identification"
            ))
            
            agent = self._get_flow_identifier_agent()
            
            if existing_flows and additional_context:
                # Refine existing flows
                flows_markdown = agent.refine_with_additional_context(
                    initial_flows=existing_flows,
                    additional_context=additional_context
                )
                result_data = {
                    "flows_markdown": flows_markdown,
                    "is_refinement": True,
                }
            else:
                # Initial flow identification
                result = agent.identify_flows(
                    codebase_summary=codebase_summary,
                    request_missing_metadata=False
                )
                flows_markdown = result.flows_markdown
                result_data = {
                    "flows_markdown": result.flows_markdown,
                    "followup_queries": result.followup_queries,
                    "is_complete": result.is_complete,
                }
            
            # Update state
            self.state.flows_markdown = flows_markdown
            self.state.phase = OrchestratorPhase.FLOW_IDENTIFICATION
            
            # Parse flows
            from src.agents.scribe.flow_parser import parse_flows_markdown
            self.state.parsed_flows = parse_flows_markdown(flows_markdown)
            
            duration = (datetime.now() - start_time).total_seconds()
            console.print(f"[green]Identified {len(self.state.parsed_flows)} flows in {duration:.1f}s[/green]")
            
            return ToolResult(
                tool_name="flow_identifier_agent",
                success=True,
                output=result_data,
                duration_seconds=duration
            )
        except Exception as e:
            logger.error("flow_identifier_agent_failed", error=str(e))
            return ToolResult(
                tool_name="flow_identifier_agent",
                success=False,
                output=None,
                error=AgentError.from_exception(AgentType.FLOW_IDENTIFIER, e)
            )

    async def _handle_action_agent(
        self,
        flow_markdown: str,
        target_url: str
    ) -> ToolResult:
        """Execute the action agent."""
        start_time = datetime.now()
        try:
            console.print(Panel(
                f"[cyan]Running Action Agent[/cyan]\n"
                f"URL: {target_url}\n"
                f"Flow: {flow_markdown[:100]}...",
                title="Action Execution"
            ))
            
            agent = self._get_action_agent()
            self.state.phase = OrchestratorPhase.ACTION_EXECUTION
            
            result = await agent.run(instruction=flow_markdown, url=target_url)
            
            # Normalize result
            if isinstance(result, list):
                result_text = "\n".join(
                    block.get("text", str(block)) if isinstance(block, dict) else str(block)
                    for block in result
                )
            else:
                result_text = str(result)
            
            # Check for errors in result
            is_error = "error" in result_text.lower()[:200] or "failed" in result_text.lower()[:200]
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if is_error:
                console.print(f"[yellow]Action completed with errors in {duration:.1f}s[/yellow]")
                return ToolResult(
                    tool_name="action_agent",
                    success=False,
                    output={"result": result_text, "has_errors": True},
                    error=AgentError(
                        agent_type=AgentType.ACTION,
                        error_type=ErrorType.FLOW_INCOMPLETE,
                        message=result_text[:500],
                        recoverable=True
                    ),
                    duration_seconds=duration
                )
            else:
                console.print(f"[green]Action completed successfully in {duration:.1f}s[/green]")
                return ToolResult(
                    tool_name="action_agent",
                    success=True,
                    output={"result": result_text, "has_errors": False},
                    duration_seconds=duration
                )
                
        except Exception as e:
            logger.error("action_agent_failed", error=str(e))
            return ToolResult(
                tool_name="action_agent",
                success=False,
                output=None,
                error=AgentError.from_exception(AgentType.ACTION, e)
            )

    async def _handle_scribe_agent(
        self,
        flow_name: str,
        flow_markdown: str,
        execution_result: str,
        codebase_summary: str,
        start_url: str
    ) -> ToolResult:
        """Execute the scribe agent."""
        start_time = datetime.now()
        try:
            console.print(Panel(
                f"[cyan]Running Scribe Agent[/cyan]\n"
                f"Flow: {flow_name}",
                title="Documentation Generation"
            ))
            
            from src.agents.scribe.types import FlowExecutionRecord, StepRecord
            
            agent = self._get_scribe_agent()
            self.state.phase = OrchestratorPhase.DOCUMENTATION
            
            # Create a minimal execution record
            execution_record = FlowExecutionRecord(
                flow_name=flow_name,
                flow_markdown=flow_markdown,
                start_url=start_url,
                steps=[],  # Steps would be populated from actual execution
                success=True,
                started_at=datetime.now(),
                finished_at=datetime.now()
            )
            
            result = agent.generate_documentation(
                execution_record=execution_record,
                codebase_summary=codebase_summary
            )
            
            self.state.scribe_outputs.append(result)
            
            duration = (datetime.now() - start_time).total_seconds()
            console.print(f"[green]Documentation generated in {duration:.1f}s[/green]")
            
            return ToolResult(
                tool_name="scribe_agent",
                success=True,
                output={
                    "flow_name": result.flow_name,
                    "documentation_length": len(result.documentation_markdown),
                },
                duration_seconds=duration
            )
        except Exception as e:
            logger.error("scribe_agent_failed", error=str(e))
            return ToolResult(
                tool_name="scribe_agent",
                success=False,
                output=None,
                error=AgentError.from_exception(AgentType.SCRIBE, e)
            )

    async def _handle_analyze_error(
        self,
        error_message: str,
        flow_name: Optional[str] = None,
        failed_step: Optional[str] = None,
        element_description: Optional[str] = None
    ) -> ToolResult:
        """Analyze an error and provide recovery recommendations."""
        error_lower = error_message.lower()
        
        # Determine error type and recovery strategy
        if "element" in error_lower and "not found" in error_lower:
            recovery = RecoveryAction(
                action="Re-run discovery with focus on finding correct selectors for the element",
                target_agent=AgentType.DISCOVERY,
                additional_context=f"Focus on element: {element_description or failed_step}",
                refinement_query=f"What are the exact selectors, test-ids, and aria-labels for '{element_description or failed_step}'?"
            )
        elif "navigation" in error_lower:
            recovery = RecoveryAction(
                action="Verify routes and navigation patterns in the codebase",
                target_agent=AgentType.DISCOVERY,
                refinement_query="What are all the routes and navigation endpoints in this application?"
            )
        elif "timeout" in error_lower:
            recovery = RecoveryAction(
                action="Add explicit wait steps to the flow",
                target_agent=AgentType.FLOW_IDENTIFIER,
                additional_context="The page is loading slowly. Add wait steps after navigation and form submissions."
            )
        elif "permission" in error_lower or "403" in error_lower:
            recovery = RecoveryAction(
                action="This error is NOT recoverable - the action requires authentication or special permissions",
                target_agent=AgentType.DISCOVERY,  # Just for logging
                additional_context="SKIP this flow - permission denied"
            )
        else:
            recovery = RecoveryAction(
                action="Re-examine the codebase for better element identification",
                target_agent=AgentType.DISCOVERY,
                refinement_query=f"How does the element '{element_description or 'unknown'}' work and what are its attributes?"
            )
        
        return ToolResult(
            tool_name="analyze_error",
            success=True,
            output={
                "error_type": recovery.target_agent.value,
                "recommended_action": recovery.action,
                "recovery_query": recovery.refinement_query,
                "additional_context": recovery.additional_context,
                "is_recoverable": "permission" not in error_lower.lower()
            }
        )

    # ---------------------------------------------------------------------------
    # Tool Router
    # ---------------------------------------------------------------------------

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> ToolResult:
        """Route tool calls to appropriate handlers."""
        logger.info("executing_tool", tool=tool_name, input_keys=list(tool_input.keys()))
        
        if tool_name == "discovery_agent":
            return await self._handle_discovery_agent(
                repo_path=tool_input["repo_path"],
                force_reindex=tool_input.get("force_reindex", False),
                custom_query=tool_input.get("custom_query")
            )
        elif tool_name == "flow_identifier_agent":
            return await self._handle_flow_identifier_agent(
                codebase_summary=tool_input["codebase_summary"],
                existing_flows=tool_input.get("existing_flows"),
                additional_context=tool_input.get("additional_context"),
                focus_elements=tool_input.get("focus_elements")
            )
        elif tool_name == "action_agent":
            return await self._handle_action_agent(
                flow_markdown=tool_input["flow_markdown"],
                target_url=tool_input["target_url"]
            )
        elif tool_name == "scribe_agent":
            return await self._handle_scribe_agent(
                flow_name=tool_input["flow_name"],
                flow_markdown=tool_input["flow_markdown"],
                execution_result=tool_input["execution_result"],
                codebase_summary=tool_input["codebase_summary"],
                start_url=tool_input["start_url"]
            )
        elif tool_name == "analyze_error":
            return await self._handle_analyze_error(
                error_message=tool_input["error_message"],
                flow_name=tool_input.get("flow_name"),
                failed_step=tool_input.get("failed_step"),
                element_description=tool_input.get("element_description")
            )
        else:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=AgentError(
                    agent_type=AgentType.DISCOVERY,
                    error_type=ErrorType.UNKNOWN,
                    message=f"Unknown tool: {tool_name}"
                )
            )

    # ---------------------------------------------------------------------------
    # Main Orchestration Loop
    # ---------------------------------------------------------------------------

    async def run(
        self,
        repo_path: str,
        target_url: str,
        initial_query: Optional[str] = None,
        max_iterations: int = 20
    ) -> OrchestratorResult:
        """
        Run the full orchestration pipeline.
        
        Args:
            repo_path: Path to the repository to analyze
            target_url: URL to execute flows against
            initial_query: Optional starting query for discovery
            max_iterations: Maximum LLM iterations (safety limit)
            
        Returns:
            OrchestratorResult with all outputs and status
        """
        # Initialize state
        self.state = OrchestratorState(
            repo_path=repo_path,
            target_url=target_url,
            initial_query=initial_query,
            started_at=datetime.now()
        )
        
        console.print(Panel(
            f"[bold cyan]Starting Orchestrator[/bold cyan]\n\n"
            f"Repository: {repo_path}\n"
            f"Target URL: {target_url}\n"
            f"Initial Query: {initial_query or 'None'}",
            title="Orchestrator Agent",
            border_style="cyan"
        ))
        
        # Build initial message
        initial_message = f"""Execute the complete automation pipeline:

1. **Repository**: `{repo_path}`
2. **Target URL**: `{target_url}`
3. **Initial Query**: {initial_query or "Explore the codebase and identify critical user flows"}

Please:
1. Run discovery_agent to explore the codebase
2. Run flow_identifier_agent to extract flows
3. For each flow, execute it with action_agent
4. If any action fails, follow the error recovery protocol
5. Generate documentation with scribe_agent for successful flows
6. Provide a final summary

Begin now."""

        messages = [{"role": "user", "content": initial_message}]
        
        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            logger.info("orchestrator_iteration", iteration=iteration)
            
            try:
                # Call Claude with tools
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    system=ORCHESTRATOR_SYSTEM_PROMPT,
                    tools=ORCHESTRATOR_TOOLS,
                    messages=messages
                )
                
                # Process response
                assistant_content = []
                tool_results = []
                
                for block in response.content:
                    if block.type == "text":
                        assistant_content.append({"type": "text", "text": block.text})
                        console.print(f"\n[bold]Orchestrator:[/bold] {block.text}\n")
                    
                    elif block.type == "tool_use":
                        assistant_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input
                        })
                        
                        # Execute the tool
                        result = await self._execute_tool(block.name, block.input)
                        
                        # Format result for Claude
                        if result.success:
                            result_content = json.dumps(result.output, indent=2, default=str)
                        else:
                            result_content = json.dumps({
                                "error": True,
                                "error_message": result.error.message if result.error else "Unknown error",
                                "error_type": result.error.error_type.value if result.error else "unknown",
                                "recoverable": result.error.recoverable if result.error else False
                            }, indent=2)
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_content
                        })
                        
                        # Track errors
                        if result.error:
                            self.state.errors.append(result.error)
                
                # Add assistant message
                messages.append({"role": "assistant", "content": assistant_content})
                
                # Add tool results if any
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
                
                # Check if we're done (no more tool calls)
                if response.stop_reason == "end_turn" and not any(
                    block.type == "tool_use" for block in response.content
                ):
                    console.print("\n[bold green]Orchestration Complete![/bold green]")
                    break
                    
            except Exception as e:
                logger.error("orchestrator_iteration_failed", error=str(e))
                console.print(f"[red]Orchestration error: {e}[/red]")
                self.state.errors.append(AgentError(
                    agent_type=AgentType.DISCOVERY,
                    error_type=ErrorType.UNKNOWN,
                    message=str(e)
                ))
                break
        
        # Finalize state
        self.state.finished_at = datetime.now()
        self.state.phase = OrchestratorPhase.COMPLETED if not self.state.errors else OrchestratorPhase.FAILED
        
        # Build result
        result = OrchestratorResult(
            success=len(self.state.scribe_outputs) > 0,
            state=self.state,
            scribe_outputs=self.state.scribe_outputs,
            total_flows_discovered=len(self.state.parsed_flows),
            flows_executed_successfully=len(self.state.scribe_outputs),
            flows_failed=len(self.state.parsed_flows) - len(self.state.scribe_outputs),
            errors=self.state.errors,
            recovery_attempts=self.state.retry_count
        )
        
        # Print summary
        self._print_summary(result)
        
        return result

    def _print_summary(self, result: OrchestratorResult) -> None:
        """Print a summary table of the orchestration results."""
        table = Table(title="Orchestration Summary", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Status", "Success" if result.success else "Failed")
        table.add_row("Total Flows Discovered", str(result.total_flows_discovered))
        table.add_row("Flows Executed", str(result.flows_executed_successfully))
        table.add_row("Flows Failed", str(result.flows_failed))
        table.add_row("Recovery Attempts", str(result.recovery_attempts))
        table.add_row("Total Errors", str(len(result.errors)))
        
        if self.state.duration_seconds:
            table.add_row("Duration", f"{self.state.duration_seconds:.1f}s")
        
        console.print("\n")
        console.print(table)
        
        if result.errors:
            console.print("\n[bold red]Errors:[/bold red]")
            for err in result.errors[:5]:  # Show first 5 errors
                console.print(f"  - [{err.error_type.value}] {err.message[:100]}...")


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

async def orchestrate(
    repo_path: str,
    target_url: str,
    initial_query: Optional[str] = None
) -> OrchestratorResult:
    """
    Convenience function to run the full orchestration pipeline.
    
    Args:
        repo_path: Path to repository
        target_url: URL to execute flows against
        initial_query: Optional starting query
        
    Returns:
        OrchestratorResult
    """
    agent = OrchestratorAgent()
    return await agent.run(repo_path, target_url, initial_query)
