from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from mcp import StdioServerParameters

from src.common.logger import get_logger
from src.config import MODEL_NAME

logger = get_logger(__name__)

DISCOVERY_INSTRUCTION = """\
You are the Discovery Agent — the sensory layer of an autonomous web application
analysis system.

Your ONLY job is to OBSERVE. You must NEVER take actions that modify application
state (no clicking buttons, no filling forms, no submitting anything).

Given a URL, you must:
1. Navigate to the URL
2. Take a full-page screenshot
3. Extract the accessibility tree (this gives you the DOM structure, roles, labels)
4. Identify all visible interactive elements (buttons, links, inputs, selectors)
5. Detect the current application state (URL, page title, any visible modals/toasts)

Return your observations as structured output with these sections:
- **Page Info**: URL, title, meta description
- **Screenshot**: confirmation that screenshot was captured
- **Interactive Elements**: list of all interactive elements with their:
  - Type (button, link, input, select, etc.)
  - Label/text content
  - ARIA role
  - Selector/identifier
  - Visibility and enabled state
- **Page Structure**: key structural sections/landmarks visible
- **State Indicators**: any modals, toasts, alerts, loading states detected
- **Navigation Options**: links and routes available from current page
"""


def create_playwright_toolset():
    """Create a Playwright MCP toolset for browser interaction."""
    return McpToolset(
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@anthropic-ai/mcp-server-playwright"],
        ),
    )


def create_discovery_agent(model=None, playwright_toolset=None):
    """Factory function to create a configured Discovery Agent.

    Args:
        model: LLM model name override. Defaults to config MODEL_NAME.
        playwright_toolset: Optional pre-configured McpToolset. Creates default if None.

    Returns:
        Configured LlmAgent instance.
    """
    if playwright_toolset is None:
        playwright_toolset = create_playwright_toolset()

    return LlmAgent(
        name="discovery_agent",
        model=model or MODEL_NAME,
        instruction=DISCOVERY_INSTRUCTION,
        tools=[playwright_toolset],
    )


discovery_agent = create_discovery_agent()
