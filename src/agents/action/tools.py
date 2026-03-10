import asyncio
import base64
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from langchain_core.tools import tool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.agents.scribe.types import StepRecord


# Base directory for screenshots (src/agents/action/screenshots/)
SCREENSHOTS_BASE_DIR = Path(__file__).parent / "screenshots"

# Module-level callback that the pipeline sets before invoking the tool.
# This avoids changing the @tool signature (LangChain tools can't have extra params).
_step_callback: Optional[Callable[[StepRecord], None]] = None


def set_step_callback(callback: Optional[Callable[[StepRecord], None]]) -> None:
    """Set (or clear) the global step-record callback used by task_executor."""
    global _step_callback
    _step_callback = callback


def _emit_step(record: StepRecord) -> None:
    """Emit a step record to the registered callback, if any."""
    if _step_callback is not None:
        try:
            _step_callback(record)
        except Exception:
            pass  # Never let callback errors break execution


def _create_screenshot_dir() -> Path:
    """Create a timestamped screenshot directory for this run."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    screenshot_dir = SCREENSHOTS_BASE_DIR / timestamp
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    print(f"[TaskExecutor] Screenshot directory: {screenshot_dir}")
    return screenshot_dir


async def _take_screenshot(session: ClientSession, screenshot_dir: Path, step_index: int, step_name: str) -> str:
    """
    Take a screenshot after an action and save it to the run's screenshot directory.
    Returns the saved file path or an error message.
    """
    # Sanitize step name for filename
    safe_name = re.sub(r'[^\w\s-]', '', step_name).strip().replace(' ', '_')[:50]
    filename = f"{step_index:02d}_{safe_name}.png"
    filepath = screenshot_dir / filename

    try:
        res = await session.call_tool("browser_take_screenshot", {
            "filename": str(filepath)
        })

        # Handle response — might return image data or save to file directly
        for block in res.content:
            block_type = getattr(block, "type", None)
            if block_type == "image":
                # Server returned image data directly — save it
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(block.data))

        if filepath.exists():
            print(f"[TaskExecutor] Screenshot saved: {filepath.name}")
            return str(filepath)
        else:
            print(f"[TaskExecutor] WARNING: Screenshot file not created: {filepath}")
            return ""
    except Exception as e:
        print(f"[TaskExecutor] WARNING: Screenshot failed for step '{step_name}': {e}")
        return ""


def _find_ref_in_snapshot(snapshot_text: str, element_description: str) -> Optional[str]:
    """
    Search the accessibility snapshot text for an element matching the description
    and extract its ref value.

    The snapshot contains lines like:
      - textbox "Search" [ref=s1e3]
      - button "Google Search" [ref=s1e5]

    We do a case-insensitive search.
    """
    element_lower = element_description.lower()

    # Try to find lines containing [ref=...] and matching the description
    ref_pattern = re.compile(r'\[ref=([\w\d]+)\]')

    # Generic element names we want to avoid matching *only* on
    generic_terms = {"button", "input", "textbox", "textarea", "link", "checkbox", "radio", "select"}

    best_match = None
    for line in snapshot_text.split('\n'):
        line_lower = line.lower().strip()
        if not line_lower:
            continue

        ref_match = ref_pattern.search(line)
        if not ref_match:
            continue

        ref_value = ref_match.group(1)

        # Check for exact substring match first (highest priority)
        # Remove quotes for cleaner matching
        clean_desc = element_lower.replace('"', '').replace("'", "")
        if clean_desc and clean_desc in line_lower:
            print(f"[TaskExecutor] Matched element (exact): '{element_description}' -> ref={ref_value}")
            return ref_value

        # Check if description keywords appear in this line
        # Strip quotes and brackets
        clean_desc_words = re.sub(r'[^\w\s]', ' ', element_lower).split()
        keywords = [w for w in clean_desc_words if len(w) > 2]

        if not keywords:
            continue

        matches = sum(1 for kw in keywords if kw in line_lower)

        # If the *only* matched words are generic (like "button"), don't blindly click it
        matched_words = [kw for kw in keywords if kw in line_lower]
        all_generic = all(mw in generic_terms for mw in matched_words)

        if matches > 0 and not all_generic:
            if best_match is None or matches > best_match[1]:
                best_match = (ref_value, matches, line.strip())

    if best_match:
        print(f"[TaskExecutor] Matched element (fuzzy): '{element_description}' -> ref={best_match[0]} (line: {best_match[2]})")
        return best_match[0]

    return None


def _parse_fill_step(step: str) -> Optional[tuple[str, str]]:
    """
    Parse a fill/type step and extract (element_description, value).

    Supports formats:
      - fill "Client Name" with "TEST-HACK-AcmeCorp"
      - fill "Client Name" with TEST-HACK-AcmeCorp
      - fill id="clientName" with TEST-HACK-AcmeCorp
      - fill id="clientName" with "TEST-HACK-AcmeCorp"
      - type 'hello world'
      - fill 'hello world'

    Returns (element_description, value) or None if not a fill/type step.
    """
    # Pattern 1: fill "<element>" with "<value>"  or  fill "<element>" with <value>
    m = re.search(
        r'(?:fill|type)\s+["\']([^"\']+)["\']\s+with\s+["\']?(.+?)["\'\s]*$',
        step, re.IGNORECASE
    )
    if m:
        return (m.group(1).strip(), m.group(2).strip().strip("\"'"))

    # Pattern 2: fill id="<id>" with "<value>"  or  fill id="<id>" with <value>
    m = re.search(
        r'(?:fill|type)\s+(?:id|name|aria-label)\s*=\s*["\']?([^"\'\s]+)["\']?\s+with\s+["\']?(.+?)["\'\s]*$',
        step, re.IGNORECASE
    )
    if m:
        return (m.group(1).strip(), m.group(2).strip().strip("\"'"))

    # Pattern 3: type '<value>' / fill '<value>' (original format — no element desc)
    m = re.search(r'(?:type|fill)\s+["\'](.+?)["\']', step, re.IGNORECASE)
    if m:
        # No explicit element description — return empty so caller uses step context
        return ("", m.group(1).strip())

    # Pattern 4: type(<value>) / fill(<value>)
    m = re.search(r'(?:type|fill)\s*\((.+?)\)', step, re.IGNORECASE)
    if m:
        return ("", m.group(1).strip())

    return None


def _find_textbox_ref(snapshot_text: str, element_desc: str) -> Optional[str]:
    """
    Find a textbox/input element in the snapshot matching the given description.
    Prioritises exact label matches over fuzzy ones.
    """
    ref_pattern = re.compile(r'\[ref=([\w\d]+)\]')
    textbox_roles = {'textbox', 'input', 'textarea', 'searchbox'}
    desc_lower = element_desc.lower().strip()

    candidates = []  # (priority, ref, line)

    for line in snapshot_text.split('\n'):
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        if not line_lower:
            continue

        ref_match = ref_pattern.search(line_stripped)
        if not ref_match:
            continue

        ref_value = ref_match.group(1)

        # Only consider textbox-like roles
        is_textbox = any(role in line_lower for role in textbox_roles)
        if not is_textbox:
            continue

        if not desc_lower:
            # No description — return the first textbox found
            candidates.append((2, ref_value, line_stripped))
            continue

        # Exact label match (e.g. textbox "Client Name")
        if desc_lower in line_lower:
            candidates.append((0, ref_value, line_stripped))
            continue

        # Keyword match
        keywords = [w for w in re.sub(r'[^\w\s]', ' ', desc_lower).split() if len(w) > 2]
        if keywords:
            match_count = sum(1 for kw in keywords if kw in line_lower)
            if match_count > 0:
                candidates.append((1, ref_value, line_stripped))

    if candidates:
        candidates.sort(key=lambda c: c[0])
        best = candidates[0]
        print(f"[TaskExecutor] Matched textbox: '{element_desc}' -> ref={best[1]} (line: {best[2]})")
        return best[1]

    return None


def _parse_select_step(step: str) -> Optional[tuple[str, str]]:
    """
    Parse a select step and extract (element_description, value).

    Supports formats:
      - select "Sales Region" with "North"
      - select "Sales Region"   (no value = pick first option)

    Returns (element_description, value) or None.
    """
    # select "<element>" with "<value>"
    m = re.search(
        r'select\s+["\']([^"\']+)["\']\s+with\s+["\']?(.+?)["\'\s]*$',
        step, re.IGNORECASE
    )
    if m:
        return (m.group(1).strip(), m.group(2).strip().strip("\"'"))

    # select "<element>" (no value)
    m = re.search(r'select\s+["\']([^"\']+)["\']', step, re.IGNORECASE)
    if m:
        return (m.group(1).strip(), "")

    return None


async def _handle_select_action(
    session: ClientSession,
    snapshot_text: str,
    element_desc: str,
    desired_value: str,
) -> tuple[bool, str]:
    """
    Handle a combobox/dropdown select action.
    1. Find the combobox in the snapshot.
    2. Click it to open the dropdown.
    3. Take a new snapshot to see the options.
    4. Click the desired option (or the first non-empty one).
    5. If no options exist, look for an "Add/Create/New" button to create one.
    Returns (success, message).
    """
    # Find the combobox element
    ref = _find_ref_in_snapshot(snapshot_text, element_desc)
    if not ref:
        return (False, f"Could not find dropdown for: {element_desc}")

    # Click to open the dropdown
    print(f"[TaskExecutor] Opening dropdown | ref={ref} | desc={element_desc}")
    await session.call_tool("browser_click", {"ref": ref, "element": f"Open {element_desc} dropdown"})
    await asyncio.sleep(1)  # Wait for dropdown to render

    # Take a new snapshot to see the dropdown options
    snapshot_res = await session.call_tool("browser_snapshot", {})
    options_snapshot = ""
    for block in snapshot_res.content:
        if getattr(block, "type", None) == "text":
            options_snapshot = block.text
            break

    if not options_snapshot:
        return (False, f"Empty snapshot after opening dropdown {element_desc}")

    # Find option elements in the snapshot
    ref_pattern = re.compile(r'\[ref=([\w\d]+)\]')
    option_roles = {'option', 'menuitem', 'listitem', 'treeitem'}
    desired_lower = desired_value.lower().strip()

    best_option_ref = None
    first_option_ref = None

    for line in options_snapshot.split('\n'):
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        if not line_lower:
            continue

        ref_match = ref_pattern.search(line_stripped)
        if not ref_match:
            continue

        is_option = any(role in line_lower for role in option_roles)
        if not is_option:
            continue

        opt_ref = ref_match.group(1)

        # Skip placeholder/empty options
        if any(skip in line_lower for skip in ['select a', 'choose', '--', 'placeholder']):
            continue

        if first_option_ref is None:
            first_option_ref = (opt_ref, line_stripped)

        if desired_lower and desired_lower in line_lower:
            best_option_ref = (opt_ref, line_stripped)
            break

    target = best_option_ref or first_option_ref
    if target:
        print(f"[TaskExecutor] Selecting option | ref={target[0]} | line={target[1]}")
        await session.call_tool("browser_click", {"ref": target[0], "element": f"Select option: {target[1]}"})
        return (True, f"Selected '{target[1]}' in {element_desc}")

    # -------------------------------------------------------------------
    # NO OPTIONS FOUND — look for an "Add" / "Create" / "New" button
    # -------------------------------------------------------------------
    print(f"[TaskExecutor] Dropdown '{element_desc}' has no options. Looking for a create/add button...")

    # Close the dropdown first by pressing Escape
    try:
        await session.call_tool("browser_press_key", {"key": "Escape"})
        await asyncio.sleep(0.5)
    except Exception:
        pass

    # Take a fresh snapshot to find create/add buttons
    snapshot_res = await session.call_tool("browser_snapshot", {})
    page_snapshot = ""
    for block in snapshot_res.content:
        if getattr(block, "type", None) == "text":
            page_snapshot = block.text
            break

    # Search for add/create/new buttons or links
    create_keywords = ['add', 'create', 'new']
    desc_keywords = [w.lower() for w in re.sub(r'[^\w\s]', ' ', element_desc).split() if len(w) > 2]
    create_btn_ref = None

    for line in page_snapshot.split('\n'):
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        if not line_lower:
            continue

        ref_match = ref_pattern.search(line_stripped)
        if not ref_match:
            continue

        # Look for button/link with "add"/"create"/"new" + related keyword
        is_actionable = any(role in line_lower for role in ['button', 'link'])
        if not is_actionable:
            continue

        has_create_keyword = any(kw in line_lower for kw in create_keywords)
        if not has_create_keyword:
            continue

        # Prefer buttons that also mention the field context (e.g. "Add Contact")
        has_context = any(kw in line_lower for kw in desc_keywords) if desc_keywords else True
        if has_context or create_btn_ref is None:
            create_btn_ref = (ref_match.group(1), line_stripped)
            if has_context:
                break  # Perfect match, stop searching

    if not create_btn_ref:
        return (False, f"Dropdown '{element_desc}' is empty and no Add/Create button found")

    # Click the create/add button
    print(f"[TaskExecutor] Clicking create button | ref={create_btn_ref[0]} | line={create_btn_ref[1]}")
    await session.call_tool("browser_click", {
        "ref": create_btn_ref[0],
        "element": f"Create new item for {element_desc}"
    })
    await asyncio.sleep(2)  # Wait for sub-form / new page to load

    # Take snapshot of the sub-form and fill all its fields
    snapshot_res = await session.call_tool("browser_snapshot", {})
    subform_snapshot = ""
    for block in snapshot_res.content:
        if getattr(block, "type", None) == "text":
            subform_snapshot = block.text
            break

    if subform_snapshot:
        print("[TaskExecutor] Filling sub-form fields...")
        # Find and fill all textboxes in the sub-form
        textbox_roles = {'textbox', 'input', 'textarea', 'searchbox'}
        for line in subform_snapshot.split('\n'):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            ref_match = ref_pattern.search(line_stripped)
            if not ref_match:
                continue

            is_textbox = any(role in line_lower for role in textbox_roles)
            if not is_textbox:
                continue

            # Check if field already has content (text after the ref bracket)
            after_ref = line_stripped[ref_match.end():].strip().strip(':')
            if after_ref and after_ref not in ['', '""']:
                continue

            sub_ref = ref_match.group(1)
            label_match = re.search(r'["\']([^"\']+)["\']', line_stripped)
            sub_label = label_match.group(1) if label_match else "field"
            clean_label = re.sub(r'[\*\s]+$', '', sub_label).strip()
            mock_value = f"TEST-HACK-{clean_label.replace(' ', '-')}"

            print(f"[TaskExecutor] Sub-form fill | ref={sub_ref} | label={sub_label} | value={mock_value}")
            try:
                await session.call_tool("browser_type", {
                    "ref": sub_ref,
                    "text": mock_value,
                    "slowly": True
                })
            except Exception as e:
                print(f"[TaskExecutor] WARNING: Sub-form fill failed for '{sub_label}': {e}")

        # Look for a save/submit/create button in the sub-form
        save_keywords = ['save', 'submit', 'create', 'add', 'ok', 'confirm']
        save_btn_ref = None
        for line in subform_snapshot.split('\n'):
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            ref_match = ref_pattern.search(line_stripped)
            if not ref_match:
                continue
            if 'button' in line_lower and any(kw in line_lower for kw in save_keywords):
                save_btn_ref = (ref_match.group(1), line_stripped)
                break

        if save_btn_ref:
            print(f"[TaskExecutor] Clicking sub-form save | ref={save_btn_ref[0]}")
            await session.call_tool("browser_click", {
                "ref": save_btn_ref[0],
                "element": f"Save sub-form for {element_desc}"
            })
            await asyncio.sleep(2)  # Wait for save and redirect back

            # Now retry the original dropdown
            print(f"[TaskExecutor] Retrying dropdown '{element_desc}' after creating new item...")
            # Take a fresh snapshot
            retry_snapshot_res = await session.call_tool("browser_snapshot", {})
            retry_snapshot = ""
            for block in retry_snapshot_res.content:
                if getattr(block, "type", None) == "text":
                    retry_snapshot = block.text
                    break

            if retry_snapshot:
                # Recursive call — but only one level deep
                return await _handle_select_action(session, retry_snapshot, element_desc, desired_value)

    return (False, f"Created item for '{element_desc}' but could not complete selection")


async def _auto_fill_remaining_fields(
    session: ClientSession,
    snapshot_text: str,
    screenshot_dir,
    step_counter: int,
    results: list,
    screenshot_paths: list,
    start_url: str,
) -> int:
    """
    Take a FRESH snapshot, scan for unfilled form fields, and auto-fill them.
    Detects already-filled fields by checking for content after the ref bracket.
    Returns updated step_counter.
    """
    # Take a FRESH snapshot to see the current state of the page
    print("[TaskExecutor] Taking fresh snapshot for auto-fill scan...")
    snapshot_res = await session.call_tool("browser_snapshot", {})
    fresh_snapshot = ""
    for block in snapshot_res.content:
        if getattr(block, "type", None) == "text":
            fresh_snapshot = block.text
            break

    if not fresh_snapshot:
        print("[TaskExecutor] WARNING: Empty snapshot for auto-fill")
        return step_counter

    ref_pattern = re.compile(r'\[ref=([\w\d]+)\]')
    textbox_roles = {'textbox', 'input', 'textarea', 'searchbox'}
    dropdown_roles = {'combobox', 'listbox', 'select'}

    for line in fresh_snapshot.split('\n'):
        line_stripped = line.strip()
        line_lower = line_stripped.lower()
        if not line_lower:
            continue

        ref_match = ref_pattern.search(line_stripped)
        if not ref_match:
            continue
        ref_value = ref_match.group(1)

        # Extract the label from the snapshot line (e.g., textbox "Client Name *")
        label_match = re.search(r'["\']([^"\']+)["\']', line_stripped)
        label = label_match.group(1) if label_match else "field"

        is_textbox = any(role in line_lower for role in textbox_roles)
        is_dropdown = any(role in line_lower for role in dropdown_roles)

        if is_textbox:
            after_ref = line_stripped[ref_match.end():].strip()
            after_ref_clean = after_ref.lstrip(':').strip()
            if after_ref_clean:
                print(f"[TaskExecutor] Skipping already-filled textbox: '{label}' (value: {after_ref_clean[:30]}...)")
                continue

            clean_label = re.sub(r'[\*\s]+$', '', label).strip()
            mock_value = f"TEST-HACK-{clean_label.replace(' ', '-')}"
            print(f"[TaskExecutor] Auto-filling textbox | ref={ref_value} | label={label} | value={mock_value}")
            try:
                await session.call_tool("browser_type", {
                    "ref": ref_value,
                    "text": mock_value,
                    "slowly": True
                })
                result_msg = f"Auto-filled '{mock_value}' into '{label}'"
                results.append(result_msg)
                step_counter += 1
                path = await _take_screenshot(session, screenshot_dir, step_counter, f"auto_fill_{clean_label}")
                if path:
                    screenshot_paths.append(path)

                _emit_step(StepRecord(
                    step_number=step_counter,
                    action="auto_fill",
                    target_element=label,
                    matched_element=f"ref={ref_value} | {line_stripped}",
                    match_type="exact",
                    value=mock_value,
                    accessibility_snapshot=fresh_snapshot,
                    screenshot_path=path or None,
                    result=result_msg,
                    url=start_url,
                ))
            except Exception as e:
                print(f"[TaskExecutor] WARNING: Auto-fill failed for '{label}': {e}")

        elif is_dropdown:
            after_ref = line_stripped[ref_match.end():].strip()
            after_ref_clean = after_ref.lstrip(':').strip()
            if after_ref_clean and not any(skip in after_ref_clean.lower() for skip in ['select a', 'choose', '--', 'placeholder']):
                print(f"[TaskExecutor] Skipping already-selected dropdown: '{label}' (value: {after_ref_clean[:30]}...)")
                continue

            clean_label = re.sub(r'[\*\s]+$', '', label).strip()
            print(f"[TaskExecutor] Auto-selecting dropdown | ref={ref_value} | label={label}")
            try:
                success, msg = await _handle_select_action(session, fresh_snapshot, clean_label, "")
                result_msg = f"Auto-select {clean_label}: {msg}"
                results.append(result_msg)
                step_counter += 1
                path = await _take_screenshot(session, screenshot_dir, step_counter, f"auto_select_{clean_label}")
                if path:
                    screenshot_paths.append(path)

                _emit_step(StepRecord(
                    step_number=step_counter,
                    action="auto_select",
                    target_element=clean_label,
                    matched_element=f"ref={ref_value} | {line_stripped}",
                    match_type="exact" if success else "not_found",
                    accessibility_snapshot=fresh_snapshot,
                    screenshot_path=path or None,
                    result=result_msg,
                    url=start_url,
                ))
            except Exception as e:
                print(f"[TaskExecutor] WARNING: Auto-select failed for '{label}': {e}")

    return step_counter


@tool
async def task_executor(flow_string: str, start_url: str) -> str:
    """
    Executes a sequence of UI actions iteratively on the specified start_url using Playwright MCP.
    flow_string: A sequence of UI interactions indicated by arrows or steps (e.g., "search box -> type 'hello world' -> click Search").
    start_url: The URL to navigate to before performing the steps.

    Takes a screenshot after each action and saves them in a timestamped folder
    under src/agents/action/screenshots/.
    """
    # Connect to your existing open Chrome using the Playwright MCP Bridge extension!
    # Make sure you have the extension installed in your Chrome browser.

    # The environment variable is loaded by dotenv in run_action_agent.py.
    # Pass it specifically in the env dictionary to the MCP server.
    token = os.getenv("PLAYWRIGHT_MCP_EXTENSION_TOKEN")

    server_params = StdioServerParameters(
        command="npx",
        args=[
            "@playwright/mcp@latest",
            "--extension"
        ],
        env={"PLAYWRIGHT_MCP_EXTENSION_TOKEN": token} if token else {}
    )

    results = []
    screenshot_paths = []

    # Very basic parsing by arrows
    steps = [s.strip() for s in flow_string.split("->") if s.strip()]
    if not steps:
        steps = [flow_string]

    # Create timestamped screenshot directory for this run
    screenshot_dir = _create_screenshot_dir()
    step_counter = 0

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("[TaskExecutor] MCP session initialized")

                # Navigate to the start URL
                print(f"[TaskExecutor] Navigating to {start_url}")
                results.append(f"Navigating to {start_url}...")
                await session.call_tool("browser_navigate", {"url": start_url})

                # Screenshot after navigation
                step_counter += 1
                path = await _take_screenshot(session, screenshot_dir, step_counter, f"navigate_{start_url.split('//')[1][:30]}")
                if path:
                    screenshot_paths.append(path)

                _emit_step(StepRecord(
                    step_number=step_counter,
                    action="navigate",
                    target_element=start_url,
                    matched_element=None,
                    match_type="none",
                    value=None,
                    accessibility_snapshot="",
                    screenshot_path=path or None,
                    result=f"Navigated to {start_url}",
                    url=start_url,
                ))

                for step in steps:
                    step_lower = step.lower()
                    try:
                        # Take a snapshot to get current page state and element refs
                        print(f"[TaskExecutor] Taking snapshot for step: {step}")
                        snapshot_res = await session.call_tool("browser_snapshot", {})
                        snapshot_text = ""
                        for block in snapshot_res.content:
                            if getattr(block, "type", None) == "text":
                                snapshot_text = block.text
                                break

                        if not snapshot_text:
                            print("[TaskExecutor] WARNING: Empty snapshot, skipping step")
                            results.append(f"Skipped '{step}' - empty snapshot")
                            continue

                        # Determine action type and extract value if present
                        # Use the robust parsers for fill/type and select steps
                        parsed_fill = _parse_fill_step(step)
                        parsed_select = _parse_select_step(step)

                        is_hover_action = "hover" in step_lower
                        is_click_action = "click" in step_lower or "press" in step_lower
                        is_wait_action = "wait" in step_lower
                        is_snapshot_fill = "snapshot_and_fill_remaining" in step_lower

                        action_done = False
                        action_type = "unknown"
                        target_element = step
                        matched_element = None
                        match_type = "none"
                        action_value = None
                        result_msg = ""
                        error_msg = None

                        if is_wait_action:
                            action_type = "wait"
                            wait_match = re.search(r"wait\s*(\d+)", step_lower)
                            seconds = int(wait_match.group(1)) if wait_match else 2
                            target_element = f"{seconds} seconds"
                            print(f"[TaskExecutor] Waiting {seconds} seconds...")
                            await asyncio.sleep(seconds)
                            result_msg = f"Waited {seconds} seconds"
                            results.append(result_msg)
                            action_done = True

                        elif parsed_fill is not None:
                            action_type = "fill"
                            element_desc, value = parsed_fill
                            action_value = value
                            target_element = element_desc or step
                            print(f"[TaskExecutor] Parsed fill step | element='{element_desc}' | value='{value}'")

                            ref = _find_textbox_ref(snapshot_text, element_desc)
                            if not ref:
                                ref = _find_ref_in_snapshot(snapshot_text, element_desc or step)

                            if ref:
                                # Determine match type
                                match_type = "exact" if element_desc.lower() in snapshot_text.lower() else "fuzzy"
                                matched_element = f"ref={ref}"
                                print(f"[TaskExecutor] Typing | ref={ref} | text={value}")
                                try:
                                    await session.call_tool("browser_type", {
                                        "ref": ref,
                                        "text": value,
                                        "slowly": True
                                    })
                                    result_msg = f"Typed '{value}' into element ref={ref}"
                                    results.append(result_msg)
                                    action_done = True
                                except Exception as type_err:
                                    print(f"[TaskExecutor] browser_type failed, trying browser_fill_form fallback: {type_err}")
                                    try:
                                        await session.call_tool("browser_fill_form", {
                                            "fields": [{
                                                "name": element_desc or "text field",
                                                "type": "textbox",
                                                "ref": ref,
                                                "value": value
                                            }]
                                        })
                                        result_msg = f"Filled '{value}' into element ref={ref} (via fill_form)"
                                        results.append(result_msg)
                                        action_done = True
                                    except Exception as fill_err:
                                        print(f"[TaskExecutor] browser_fill_form also failed: {fill_err}")
                                        result_msg = f"Could not type into element ref={ref}: {type_err}"
                                        error_msg = str(fill_err)
                                        results.append(result_msg)
                            else:
                                match_type = "not_found"
                                print(f"[TaskExecutor] WARNING: Could not find input element for: {step}")
                                result_msg = f"Could not find input element for: {step}"
                                error_msg = "Element not found in accessibility snapshot"
                                results.append(result_msg)

                        elif parsed_select is not None:
                            action_type = "select"
                            element_desc, desired_value = parsed_select
                            action_value = desired_value
                            target_element = element_desc
                            print(f"[TaskExecutor] Parsed select step | element='{element_desc}' | value='{desired_value}'")
                            success, msg = await _handle_select_action(
                                session, snapshot_text, element_desc, desired_value
                            )
                            result_msg = msg
                            results.append(msg)
                            action_done = success
                            match_type = "exact" if success else "not_found"
                            if success:
                                matched_element = element_desc

                        elif is_snapshot_fill:
                            action_type = "auto_fill"
                            target_element = "all remaining fields"
                            print("[TaskExecutor] Running snapshot_and_fill_remaining...")
                            step_counter = await _auto_fill_remaining_fields(
                                session, snapshot_text, screenshot_dir,
                                step_counter, results, screenshot_paths,
                                start_url,
                            )
                            result_msg = "Completed auto-fill of remaining fields"
                            results.append(result_msg)
                            action_done = True
                            match_type = "exact"

                        elif is_hover_action:
                            action_type = "hover"
                            hover_target = re.sub(r'hover\s*(on|over)?\s*', '', step_lower).strip()
                            target_element = hover_target or step
                            ref = _find_ref_in_snapshot(snapshot_text, hover_target or step)

                            if ref:
                                matched_element = f"ref={ref}"
                                match_type = "fuzzy"
                                print(f"[TaskExecutor] Hovering | ref={ref}")
                                await session.call_tool("browser_hover", {
                                    "ref": ref,
                                    "element": step
                                })
                                result_msg = f"Hovered over element ref={ref}"
                                results.append(result_msg)
                                action_done = True
                            else:
                                match_type = "not_found"
                                print(f"[TaskExecutor] WARNING: Could not find element to hover: {step}")
                                result_msg = f"Could not find hover target: {step}"
                                error_msg = "Element not found"
                                results.append(result_msg)

                        elif is_click_action:
                            action_type = "click"
                            click_target = re.sub(r'(click|press)\s*(on)?\s*', '', step_lower).strip()
                            target_element = click_target or step
                            ref = _find_ref_in_snapshot(snapshot_text, click_target or step)

                            if ref:
                                matched_element = f"ref={ref}"
                                match_type = "fuzzy"
                                print(f"[TaskExecutor] Clicking | ref={ref}")
                                await session.call_tool("browser_click", {
                                    "ref": ref,
                                    "element": step
                                })
                                result_msg = f"Clicked element ref={ref}"
                                results.append(result_msg)
                                action_done = True
                            else:
                                match_type = "not_found"
                                print(f"[TaskExecutor] WARNING: Could not find element to click: {step}")
                                result_msg = f"Could not find click target: {step}"
                                error_msg = "Element not found"
                                results.append(result_msg)
                        else:
                            action_type = "click"
                            ref = _find_ref_in_snapshot(snapshot_text, step)
                            if ref:
                                matched_element = f"ref={ref}"
                                match_type = "fuzzy"
                                print(f"[TaskExecutor] Clicking (default) | ref={ref}")
                                await session.call_tool("browser_click", {
                                    "ref": ref,
                                    "element": step
                                })
                                result_msg = f"Clicked '{step}' ref={ref}"
                                results.append(result_msg)
                                action_done = True
                            else:
                                match_type = "not_found"
                                print(f"[TaskExecutor] WARNING: Could not find element: {step}")
                                result_msg = f"Could not find element: {step}"
                                error_msg = "Element not found"
                                results.append(result_msg)

                        # Take screenshot after each completed action
                        screenshot_path = None
                        if action_done:
                            step_counter += 1
                            screenshot_path = await _take_screenshot(session, screenshot_dir, step_counter, step)
                            if screenshot_path:
                                screenshot_paths.append(screenshot_path)

                        # Emit step record
                        _emit_step(StepRecord(
                            step_number=step_counter if action_done else step_counter + 1,
                            action=action_type,
                            target_element=target_element,
                            matched_element=matched_element,
                            match_type=match_type,
                            value=action_value,
                            accessibility_snapshot=snapshot_text,
                            screenshot_path=screenshot_path,
                            result=result_msg,
                            url=start_url,
                            error=error_msg,
                        ))

                    except Exception as e:
                        print(f"[TaskExecutor] ERROR: Action step failed | step={step} | error={e}")
                        results.append(f"Failed step '{step}': {e}")

                        step_counter += 1
                        err_path = await _take_screenshot(session, screenshot_dir, step_counter, f"error_{step}")

                        _emit_step(StepRecord(
                            step_number=step_counter,
                            action="error",
                            target_element=step,
                            match_type="not_found",
                            accessibility_snapshot=snapshot_text if 'snapshot_text' in dir() else "",
                            screenshot_path=err_path or None,
                            result=f"Failed: {e}",
                            url=start_url,
                            error=str(e),
                        ))
                        break

                # Final screenshot
                step_counter += 1
                print("[TaskExecutor] Capturing final screenshot")
                path = await _take_screenshot(session, screenshot_dir, step_counter, "final_state")
                if path:
                    screenshot_paths.append(path)

                _emit_step(StepRecord(
                    step_number=step_counter,
                    action="final_screenshot",
                    target_element="final page state",
                    match_type="none",
                    screenshot_path=path or None,
                    result="Final screenshot captured",
                    url=start_url,
                ))

    except Exception as e:
        print(f"[TaskExecutor] ERROR: MCP Playwright error | error={e}")
        results.append(f"MCP Playwright Server Error: {str(e)}")

    # Summary
    results.append(f"\nScreenshots saved to: {screenshot_dir}")
    results.append(f"Total screenshots: {len(screenshot_paths)}")
    for sp in screenshot_paths:
        results.append(f"  - {Path(sp).name}")

    return "\n".join(results)
