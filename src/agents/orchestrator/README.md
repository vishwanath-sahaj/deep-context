# Orchestrator Agent

A React-style agent that orchestrates all sub-agents as tools for codebase analysis and UI automation.

## Overview

The Orchestrator Agent acts as an intelligent coordinator that manages the entire pipeline:

1. **Discovery** - Explores the codebase to understand structure and components
2. **Flow Identification** - Extracts critical user flows with detailed metadata
3. **Action Execution** - Runs flows in a real browser via Playwright
4. **Documentation** - Generates developer docs with screenshots

The key differentiator is its **intelligent error handling** - when actions fail, it automatically re-routes through discovery and flow identification to recover.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    OrchestratorAgent                            │
│                   (Claude LLM Brain)                            │
│                                                                 │
│  System Prompt: Defines tools, pipeline, error recovery rules   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ tool calls
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  discovery    │   │    flow_      │   │   action      │
│   _agent      │   │ identifier    │   │   _agent      │
│               │   │   _agent      │   │               │
└───────┬───────┘   └───────┬───────┘   └───────┬───────┘
        │                   │                   │
        │                   │           ┌───────┴───────┐
        │                   │           │   SUCCESS?    │
        │                   │           └───────┬───────┘
        │                   │              yes/ \no
        │                   │                /   \
        │                   ▼               ▼     ▼
        │           ┌───────────────┐   ┌───────────────┐
        │           │  scribe       │   │ analyze_error │
        │           │   _agent      │   │               │
        │           └───────────────┘   └───────┬───────┘
        │                                       │
        └──────────── RE-ROUTE ◄────────────────┘
                  (retry with refined flows)
```

## Tools

The orchestrator exposes these tools to Claude:

| Tool | Description | When to Use |
|------|-------------|-------------|
| `discovery_agent` | Explores codebase structure, UI components, selectors | Initial exploration, re-checking after errors |
| `flow_identifier_agent` | Extracts user flows with element metadata | After discovery, or to refine flows after errors |
| `action_agent` | Executes flows in browser via Playwright MCP | For each identified flow |
| `scribe_agent` | Generates markdown documentation | After successful action execution |
| `analyze_error` | Analyzes failures and recommends recovery | When action_agent fails |

## Error Handling

### Error Types

| Error Type | Description | Recovery Strategy |
|------------|-------------|-------------------|
| `ELEMENT_NOT_FOUND` | UI element couldn't be located | Re-run discovery with focus on the element |
| `NAVIGATION_FAILED` | Page navigation failed | Verify routes in codebase |
| `TIMEOUT` | Action timed out | Add wait steps to flow |
| `PERMISSION_DENIED` | Access denied (403, auth required) | **NOT recoverable** - skip flow |
| `SELECTOR_INVALID` | Invalid element selector | Re-discover with element focus |
| `MCP_CONNECTION_FAILED` | Playwright MCP not available | **NOT recoverable** |

### Recovery Flow

```
ActionAgent fails with error
         │
         ▼
┌─────────────────────────────┐
│      analyze_error          │
│  Classify error type        │
│  Determine if recoverable   │
└─────────────┬───────────────┘
              │
    ┌─────────┴─────────┐
    │                   │
    ▼                   ▼
Recoverable?        Not Recoverable
    │                   │
    ▼                   ▼
┌─────────────┐    Log & Skip Flow
│ discovery   │    Continue to next
│   _agent    │
│ (focused)   │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ flow_identifier │
│    _agent       │
│ (with context)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  action_agent   │
│    (retry)      │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
 Success    Fail (retry < 3)
    │         │
    ▼         └──► Go back to analyze_error
┌─────────────┐
│   scribe    │
│   _agent    │
└─────────────┘
```

## Usage

### Programmatic API

```python
import asyncio
from src.agents.orchestrator import OrchestratorAgent, orchestrate

# Option 1: Using the class directly
async def run_with_class():
    agent = OrchestratorAgent()
    result = await agent.run(
        repo_path="/path/to/your/repo",
        target_url="https://your-app.com",
        initial_query="Focus on the login and checkout flows",
        max_iterations=20
    )
    
    print(f"Success: {result.success}")
    print(f"Flows discovered: {result.total_flows_discovered}")
    print(f"Flows executed: {result.flows_executed_successfully}")
    print(f"Flows failed: {result.flows_failed}")
    
    # Access generated documentation
    for output in result.scribe_outputs:
        print(f"Documentation for {output.flow_name}:")
        print(output.documentation_markdown)

asyncio.run(run_with_class())

# Option 2: Using convenience function
async def run_simple():
    result = await orchestrate(
        repo_path=".",
        target_url="https://your-app.com"
    )
    return result

asyncio.run(run_simple())
```

### Command Line

```bash
# Basic usage
python -m src.agents.orchestrator.run \
    --repo /path/to/repo \
    --url https://your-app.com

# With custom query
python -m src.agents.orchestrator.run \
    --repo . \
    --url https://localhost:3000 \
    --query "Focus on user registration and profile editing"

# With custom iteration limit
python -m src.agents.orchestrator.run \
    --repo . \
    --url https://your-app.com \
    --max-iterations 30
```

### CLI Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--repo` | No | `.` | Path to repository to analyze |
| `--url` | **Yes** | - | Target URL to execute flows against |
| `--query` | No | None | Initial query to focus discovery |
| `--max-iterations` | No | 20 | Maximum LLM iterations |

## State Management

The orchestrator maintains state throughout execution:

```python
@dataclass
class OrchestratorState:
    phase: OrchestratorPhase  # Current phase (DISCOVERY, ACTION, etc.)
    
    # Inputs
    repo_path: str
    target_url: str
    initial_query: Optional[str]
    
    # Intermediate results
    discovery_result: DiscoveryResult
    flows_markdown: str
    parsed_flows: List[ParsedFlow]
    current_flow_index: int
    
    # Error tracking
    errors: List[AgentError]
    retry_count: int
    max_retries: int = 3
    
    # Outputs
    scribe_outputs: List[ScribeOutput]
    
    # Timing
    started_at: datetime
    finished_at: datetime
```

### Phases

| Phase | Description |
|-------|-------------|
| `IDLE` | Initial state |
| `DISCOVERY` | Running discovery agent |
| `FLOW_IDENTIFICATION` | Extracting flows |
| `ACTION_EXECUTION` | Executing flows in browser |
| `DOCUMENTATION` | Generating documentation |
| `ERROR_RECOVERY` | Handling failures |
| `COMPLETED` | Successfully finished |
| `FAILED` | Failed after retries |

## Result Structure

```python
@dataclass
class OrchestratorResult:
    success: bool                    # Overall success
    state: OrchestratorState         # Final state
    scribe_outputs: List[ScribeOutput]  # Generated docs
    
    # Statistics
    total_flows_discovered: int
    flows_executed_successfully: int
    flows_failed: int
    
    # Error tracking
    errors: List[AgentError]
    recovery_attempts: int
```

## Example Output

```
╭──────────────────── Orchestrator Agent ────────────────────╮
│ Starting Orchestrator                                       │
│                                                             │
│ Repository: /Users/dev/my-app                               │
│ Target URL: https://localhost:3000                          │
│ Initial Query: None                                         │
╰─────────────────────────────────────────────────────────────╯

╭─────────────── Discovery ───────────────╮
│ Running Discovery Agent                 │
│ Repository: /Users/dev/my-app           │
│ Custom Query: None                      │
╰─────────────────────────────────────────╯

✓ Discovery completed in 12.3s

╭─────────────── Flow Identification ───────────────╮
│ Running Flow Identifier Agent                      │
│ Refining: No                                       │
│ Additional Context: No                             │
╰────────────────────────────────────────────────────╯

✓ Identified 3 flows in 5.2s

╭─────────────── Action Execution ───────────────╮
│ Running Action Agent                            │
│ URL: https://localhost:3000                     │
│ Flow: ## Flow 1: User Login...                  │
╰─────────────────────────────────────────────────╯

✓ Action completed successfully in 8.7s

╭─────────────── Documentation Generation ───────────────╮
│ Running Scribe Agent                                    │
│ Flow: User Login                                        │
╰─────────────────────────────────────────────────────────╯

✓ Documentation generated in 4.1s

✓ Orchestration Complete!

            Orchestration Summary
┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Metric                  ┃ Value      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Status                  │ Success    │
│ Total Flows Discovered  │ 3          │
│ Flows Executed          │ 3          │
│ Flows Failed            │ 0          │
│ Recovery Attempts       │ 0          │
│ Total Errors            │ 0          │
│ Duration                │ 45.2s      │
└─────────────────────────┴────────────┘
```

## Configuration

The orchestrator uses configuration from `src/common/config.py`:

| Variable | Description |
|----------|-------------|
| `CLAUDE_API_KEY` | Anthropic API key (required) |
| `CLAUDE_CHAT_MODEL` | Model for sub-agents (default: `claude-haiku-4-5`) |

The orchestrator itself uses `claude-sonnet-4-5` for better reasoning.

## File Structure

```
src/agents/orchestrator/
├── __init__.py      # Module exports
├── types.py         # Type definitions
│   ├── AgentType          # Enum of agent types
│   ├── OrchestratorPhase  # Execution phases
│   ├── ErrorType          # Error classification
│   ├── AgentError         # Error representation
│   ├── RecoveryAction     # Recovery recommendations
│   ├── OrchestratorState  # Runtime state
│   ├── OrchestratorResult # Final result
│   └── ToolResult         # Tool execution result
├── agent.py         # Main OrchestratorAgent class
│   ├── ORCHESTRATOR_TOOLS        # Tool definitions for Claude
│   ├── ORCHESTRATOR_SYSTEM_PROMPT # System prompt
│   ├── OrchestratorAgent         # Main class
│   └── orchestrate()             # Convenience function
├── run.py           # CLI entry point
└── README.md        # This file
```

## Extending the Orchestrator

### Adding a New Tool

1. Define the tool schema in `ORCHESTRATOR_TOOLS`:

```python
{
    "name": "my_new_tool",
    "description": "What this tool does...",
    "input_schema": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
        },
        "required": ["param1"]
    }
}
```

2. Add a handler method:

```python
async def _handle_my_new_tool(self, param1: str) -> ToolResult:
    # Implementation
    return ToolResult(
        tool_name="my_new_tool",
        success=True,
        output={"result": "..."}
    )
```

3. Register in `_execute_tool`:

```python
elif tool_name == "my_new_tool":
    return await self._handle_my_new_tool(
        param1=tool_input["param1"]
    )
```

4. Update the system prompt to explain when to use the new tool.

### Custom Error Recovery

Extend `_handle_analyze_error` to add custom recovery logic:

```python
elif "my_custom_error" in error_lower:
    recovery = RecoveryAction(
        action="Description of what to do",
        target_agent=AgentType.DISCOVERY,
        refinement_query="Specific query to run"
    )
```

## Troubleshooting

### Common Issues

1. **"CLAUDE_API_KEY is not set"**
   - Ensure `.env` file exists with `CLAUDE_API_KEY=your-key`

2. **"MCP connection failed"**
   - Ensure Playwright MCP extension is installed in Chrome
   - Check `PLAYWRIGHT_MCP_EXTENSION_TOKEN` is set

3. **"Max iterations reached"**
   - Increase `--max-iterations` for complex pipelines
   - Check if there's an infinite loop in error recovery

4. **Flows not being discovered**
   - Try a more specific `--query` to guide discovery
   - Ensure the repository has frontend code

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger("src.agents.orchestrator").setLevel(logging.DEBUG)
```


