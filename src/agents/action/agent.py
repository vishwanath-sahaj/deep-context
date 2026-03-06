import json
import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from agents.action.tools import task_executor


# Build a name -> callable lookup for the tools
_TOOLS_BY_NAME = {task_executor.name: task_executor}


class ActionAgent:
    """Action Agent using Claude that can call the Playwright TaskExecutor tool to process UI flows."""

    def __init__(self):
        # Ensure Anthropic key is available
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("ANTHROPIC_API_KEY must be set in environment variables.")
            raise ValueError("ANTHROPIC_API_KEY must be set in environment variables.")

        self.llm = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            temperature=0,
            anthropic_api_key=api_key,
        ).bind_tools([task_executor])

    async def run(self, instruction: str, url: str) -> str:
        """
        Takes a natural language instruction and a URL, and runs an Agent loop.
        The Agent has access to the task_executor tool to control the Playwright browser.
        """
        # Load instructions from prompt.md
        prompt_path = os.path.join(os.path.dirname(__file__), "prompt.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_prompt = f.read()

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Instruction: {instruction}\nTarget URL: {url}"),
        ]

        print(f"[ActionAgent] Running | instruction={instruction} | url={url}")
        max_iterations = 3

        try:
            for _ in range(max_iterations):
                response = await self.llm.ainvoke(messages)
                messages.append(response)

                # If the model didn't request any tool calls, we're done
                if not response.tool_calls:
                    print("[ActionAgent] Completed")
                    return response.content or "Agent completed without output."

                # Execute each requested tool call and feed results back
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_fn = _TOOLS_BY_NAME.get(tool_name)

                    if tool_fn is None:
                        tool_result = f"Unknown tool: {tool_name}"
                    else:
                        try:
                            tool_result = await tool_fn.ainvoke(tool_args)
                        except Exception as tool_err:
                            tool_result = f"Tool error: {tool_err}"

                    messages.append(
                        ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call["id"],
                        )
                    )

            # Exhausted iterations — return the last content we have
            print("[ActionAgent] WARNING: Max iterations reached")
            return response.content or "Agent reached maximum iterations without a final answer."

        except Exception as e:
            print(f"[ActionAgent] ERROR: {e}")
            return f"Agent failed with error: {str(e)}"
