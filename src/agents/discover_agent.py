import os
import json
import logging
import asyncio
from typing import TypedDict, List, Dict, Any
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from playwright.async_api import async_playwright, Page, ElementHandle
from google.adk import Agent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

# Load environment variables
load_dotenv(find_dotenv())

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Data Models ---
class Element(TypedDict):
    id: str
    text: str
    tag: str
    visible: bool
    disabled: bool
    score: int


class Observation(TypedDict):
    screenshot: str
    metadata: Dict[str, str]
    elements: List[Element]


# --- Tool Implementation ---
class DiscoveryTools:
    def __init__(self, url: str):
        self.url = url
        self.playwright = None
        self.browser = None
        self.page = None
        self._initialized = False

    async def _ensure_initialized(self):
        if self._initialized:
            return

        logger.info(f"Launching browser (async) and navigating to {self.url}...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page()
        try:
            await self.page.goto(self.url)
            # Wait for network idle to ensure page is mostly loaded
            try:
                await self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                logger.warning("Timeout waiting for specific load state, proceeding...")
        except Exception as e:
            logger.warning(f"Navigation failed: {e}")
        self._initialized = True

    async def take_screenshot(self) -> str:
        """Takes a screenshot of the current page and returns the absolute path."""
        await self._ensure_initialized()

        # Parse URL to get hostname for folder
        from urllib.parse import urlparse

        parsed_url = urlparse(self.page.url)
        hostname = parsed_url.hostname or "unknown_host"

        # Create assets directory structure
        # User requested "assest" but "assets" is standard; I'll use "assets"
        # and create a subfolder for the URL (hostname).
        base_dir = Path(os.getcwd()) / "assets" / hostname
        base_dir.mkdir(parents=True, exist_ok=True)

        filename = "screenshot.png"
        path = base_dir / filename

        await self.page.screenshot(path=str(path))
        logger.info(f"Screenshot saved to {path}")
        return str(path)

    async def get_interactable_elements(self) -> List[Element]:
        """Scans the page for interactable elements, scores them, and returns a list."""
        await self._ensure_initialized()
        logger.info("Scanning for interactable elements...")

        selectors = [
            "button",
            "a",
            "input",
            "select",
            "textarea",
            "[role='button']",
            "[role='link']",
            "[onclick]",
            "[tabindex]:not([tabindex='-1'])",
        ]
        combined_selector = ", ".join(selectors)

        js_script = """
        (selector) => {
            const elements = Array.from(document.querySelectorAll(selector));
            const results = [];
            let idCounter = 0;
            
            function isVisible(elem) {
                if (!elem) return false;
                const style = window.getComputedStyle(elem);
                return style.display !== 'none' && 
                       style.visibility !== 'hidden' && 
                       style.opacity !== '0' &&
                       elem.offsetWidth > 0 && 
                       elem.offsetHeight > 0;
            }

            for (const el of elements) {
                if (!isVisible(el)) continue;
                
                let score = 5;
                const tag = el.tagName.toLowerCase();
                const type = el.getAttribute('type') || '';
                
                if (tag === 'button' || tag === 'a' || type === 'submit') {
                    score = 10;
                } else if (tag === 'input' || tag === 'select' || tag === 'textarea') {
                    score = 8;
                }
                
                let text = el.innerText || el.value || el.getAttribute('aria-label') || '';
                text = text.slice(0, 50).replace(/\\n/g, ' ').trim();

                results.push({
                    id: String(idCounter++),
                    text: text,
                    tag: tag,
                    visible: true,
                    disabled: el.disabled || false,
                    score: score
                });
            }
            return results;
        }
        """

        try:
            elements = await self.page.evaluate(js_script, combined_selector)
            logger.info(f"Found {len(elements)} interactable elements.")
            return elements
        except Exception as e:
            logger.error(f"Error getting elements: {e}")
            return []

    async def get_page_metadata(self) -> dict:
        """Returns metadata about the current page (URL, Title)."""
        await self._ensure_initialized()
        # In async playwright, page.url is a property, but page.title() is awaitable
        return {"url": self.page.url, "title": await self.page.title()}

    async def cleanup(self):
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


# --- Main Entry Point ---


def main():
    website_url = os.getenv("WEBSITE_URL")
    if not website_url:
        print("Error: WEBSITE_URL environment variable not set.")
        return

    tools_instance = DiscoveryTools(website_url)

    # Define Agent
    system_instruction = (
        "You are a UI Discovery Agent. Your task is to observe the current web page using the provided tools. "
        "1. Take a screenshot.\n"
        "2. Get page metadata.\n"
        "3. Get interactable elements.\n"
        "4. Finally, OUTPUT the collected information as a valid JSON object. "
        "Do not include markdown formatting."
    )

    agent = Agent(
        name="discover_agent",
        model="gemini-2.5-flash-lite",
        instruction=system_instruction,
        tools=[
            tools_instance.take_screenshot,
            tools_instance.get_interactable_elements,
            tools_instance.get_page_metadata,
        ],
    )

    runner = Runner(
        agent=agent,
        app_name="discover_app",
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    user_input = "Start exploration."
    final_output = ""

    try:
        # Runner.run is synchronous iterator but runs async loop internally.
        # It should support async tools if mapped correctly.
        for event in runner.run(
            user_id="user_discover",
            session_id="session_discover",
            new_message=types.Content(role="user", parts=[types.Part(text=user_input)]),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_output += part.text

        print(final_output)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        # Note: calling async cleanup from sync context is hard if loop is closed.
        # Ideally we rely on process exit, but let's try.
        # setup was done inside loop, cleanup also needs loop.

    finally:
        # Since tools_instance._ensure_initialized was called inside the runner's loop,
        # the loop is likely closed now.
        # For a script, it's fine to just exit and let OS cleanup.
        pass


if __name__ == "__main__":
    main()
