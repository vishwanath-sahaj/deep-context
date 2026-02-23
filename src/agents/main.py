import asyncio
import sys

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from src.agents.discovery_agent import create_discovery_agent, create_playwright_toolset
from src.common.logger import get_logger, setup_logging
from src.config import TARGET_URL

setup_logging()
logger = get_logger(__name__)

APP_NAME = "deep_context"
USER_ID = "test_user"


async def run_discovery(target_url: str):
    """Run the Discovery Agent against a target URL."""
    logger.info("starting_discovery", target_url=target_url)

    playwright_toolset = create_playwright_toolset()

    try:
        agent = create_discovery_agent(playwright_toolset=playwright_toolset)

        session_service = InMemorySessionService()
        runner = Runner(
            app_name=APP_NAME,
            agent=agent,
            session_service=session_service,
        )

        session = await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID
        )

        message = types.Content(
            role="user",
            parts=[types.Part(text=f"Observe the application at: {target_url}")],
        )

        async for event in runner.run_async(
            user_id=USER_ID, session_id=session.id, new_message=message
        ):
            if event.is_final_response():
                response = event.content
                if response and response.parts:
                    logger.info("discovery_complete")
                    print("\n--- Discovery Agent Observation ---\n")
                    for part in response.parts:
                        if part.text:
                            print(part.text)
            elif event.content and event.content.parts:
                for part in event.content.parts:
                    if part.function_call:
                        logger.info(
                            "tool_call",
                            tool=part.function_call.name,
                        )
    finally:
        logger.info("closing_mcp_toolset")
        await playwright_toolset.close()


def main():
    target_url = sys.argv[1] if len(sys.argv) > 1 else TARGET_URL
    logger.info("agent_initialized", target_url=target_url)
    asyncio.run(run_discovery(target_url))


if __name__ == "__main__":
    main()
