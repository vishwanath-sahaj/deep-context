# Action Agent — Architecture & Design

## Overview

The **Action Agent** is an AI-powered system that autonomously executes UI flows on a live web application. Given a structured description of a user journey (e.g., "fill the Client form and save"), it navigates the browser, fills text fields, selects dropdowns, clicks buttons, and even creates prerequisite data — all without human intervention.

It is designed for **automated end-to-end UI testing** of the [Sadhak](https://dev.np-sadhak.sahaj.ai) application.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Entry Point                              │
│                    run_action_agent.py                           │
│   Loads .env → reads flow.md → creates ActionAgent → runs it    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ActionAgent (agent.py)                      │
│   LLM: Claude Haiku 4.5 (via LangChain + Anthropic)             │
│   System Prompt: prompt.md                                       │
│   Tool: task_executor                                            │
│   Loop: up to 3 iterations (invoke → tool call → feedback)      │
└──────────────────────────┬──────────────────────────────────────┘
                           │ LLM generates a flow_string:
                           │ "wait 2s -> fill 'Name' with 'X' -> click Save"
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                 task_executor (tools.py)                          │
│   Connects to Playwright MCP → parses flow_string → executes    │
│   each step: snapshot → match element → perform action           │
│   Screenshots saved per step                                     │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              Playwright MCP Server (Chrome Extension)            │
│   @playwright/mcp@latest --extension                             │
│   Controls a real Chrome browser via MCP protocol                │
│   Tools: browser_navigate, browser_snapshot, browser_type,       │
│          browser_click, browser_fill_form, browser_take_screenshot│
│          browser_select_option, browser_press_key, etc.          │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure

| File | Purpose |
|------|---------|
| `run_action_agent.py` | Entry point — loads env, reads `flow.md`, creates agent, runs it |
| `agent.py` | `ActionAgent` class — LLM agent loop with tool calling |
| `tools.py` | `task_executor` tool + all helper functions for browser interaction |
| `prompt.md` | System prompt instructing the LLM how to translate flows into actions |
| `flow.md` | The UI flow definition (structured steps with element metadata) |
| `models.py` | Pydantic `UIElement` model (for structured element representation) |
| `__init__.py` | Package exports: `UIElement`, `task_executor`, `ActionAgent` |
| `screenshots/` | Timestamped screenshot directories for each run |

---

## How It Works — End-to-End Flow

### Phase 1: Startup (`run_action_agent.py`)

1. Load environment variables from `.env` (includes `ANTHROPIC_API_KEY` and `PLAYWRIGHT_MCP_EXTENSION_TOKEN`)
2. Read the UI flow definition from `flow.md`
3. Set the target URL (e.g., `https://dev.np-sadhak.sahaj.ai`)
4. Create an `ActionAgent` instance and call `agent.run(instruction, url)`

### Phase 2: LLM Planning (`agent.py` → `prompt.md`)

The `ActionAgent` uses an **agentic tool-calling loop**:

1. **System prompt** is loaded from `prompt.md` — this teaches the LLM:
   - How to read structured UI flows
   - How to generate `TEST-HACK-` prefixed mock data
   - What action formats to produce (`fill`, `select`, `click`, `wait`, `snapshot_and_fill_remaining`)
   - To always include `snapshot_and_fill_remaining` before the submit button
2. **Human message** contains the flow instruction + target URL
3. The LLM (Claude Haiku 4.5) analyzes the flow and produces a **flow string** like:
   ```
   wait 2 seconds -> fill "Client Name" with "TEST-HACK-AcmeCorp" -> fill "Website" with "https://TEST-HACK-acme.com" -> select "Sales Region" -> snapshot_and_fill_remaining -> click button "Save Client"
   ```
4. The LLM calls `task_executor(flow_string, start_url)`
5. After execution, the tool result is fed back to the LLM
6. The LLM can iterate up to **3 times** (retry on failure, adapt strategy)

### Phase 3: Browser Execution (`tools.py`)

The `task_executor` connects to a real Chrome browser via the Playwright MCP extension and executes each step.

**For every step:**
1. Take an **accessibility snapshot** (`browser_snapshot`) — returns the page DOM as text with `[ref=X]` markers
2. **Parse** the step to determine action type (fill, select, click, wait, etc.)
3. **Match** the target element by searching the snapshot for the element description
4. **Execute** the action via the appropriate MCP tool
5. **Screenshot** after each action for audit trail

---

## Action Types & Parsing Logic

### Step Parsing Pipeline

The flow string is split by `->` into individual steps. Each step is analyzed through a priority chain:

```
Step → is_wait_action?
     → _parse_fill_step() returns (element, value)?
     → _parse_select_step() returns (element, value)?
     → is_snapshot_fill?
     → is_hover_action?
     → is_click_action?
     → default: try to click
```

### 1. `wait N seconds`

Detected by `"wait" in step`. Extracts the number and calls `asyncio.sleep()`.

### 2. `fill "Element" with "Value"` (Text Input)

**Parser: `_parse_fill_step()`** — Supports 4 formats:

| Pattern | Example |
|---------|---------|
| `fill "element" with "value"` | `fill "Client Name" with "TEST-HACK-AcmeCorp"` |
| `fill id="x" with value` | `fill id="clientName" with TEST-HACK-AcmeCorp` |
| `type 'value'` | `type 'hello world'` |
| `type(value)` | `type(hello world)` |

**Element matching: `_find_textbox_ref()`** — Searches the snapshot specifically for textbox/input/textarea elements matching the label. Uses a priority system:
- Priority 0: Exact label match (e.g., `"client name"` found in `textbox "Client Name *"`)
- Priority 1: Keyword match
- Priority 2: First textbox found (fallback when no description given)

**Execution:**
1. Calls `browser_type` with `ref`, `text`, and `slowly: true` (for React/Angular key handlers)
2. If `browser_type` fails, falls back to `browser_fill_form` (structured fill API)

### 3. `select "Element"` / `select "Element" with "Option"` (Dropdown)

**Parser: `_parse_select_step()`** — Extracts element name and optional desired option.

**Execution: `_handle_select_action()`** — A multi-phase process:

1. Find the combobox/dropdown in the snapshot
2. **Click** to open the dropdown
3. Take a **new snapshot** to see the rendered options
4. Search for matching `option`/`menuitem`/`listitem` elements
5. Skip placeholders (`"Select a..."`, `"Choose..."`, `"--"`)
6. Click the best match (or first valid option)

**Empty Dropdown Handling (Prerequisite Data Creation):**

If no options exist:
1. Press Escape to close the empty dropdown
2. Scan the page for **Add/Create/New** buttons (prefers ones matching the field context, e.g., "Add Contact")
3. Click the create button → navigate to sub-form
4. **Auto-fill all text fields** in the sub-form with `TEST-HACK-*` values
5. Find and click the **Save/Submit** button
6. **Retry** the original dropdown (recursive, one level deep)

### 4. `snapshot_and_fill_remaining` (Safety Net)

**Execution: `_auto_fill_remaining_fields()`** — Scans the entire page and fills any missed fields:

1. Takes a **fresh snapshot** (not stale from a prior step)
2. For each element in the snapshot:
   - **Textboxes**: Checks for content after `[ref=X]` — skips if already filled, otherwise fills with `TEST-HACK-<Label>`
   - **Dropdowns**: Checks for selected value — skips if already selected, otherwise triggers `_handle_select_action` (which includes the empty-dropdown-create-new logic)

### 5. `click button "Name"` / `click "Element"`

Detected by `"click"` or `"press"` in the step. Extracts the target, finds it in the snapshot via `_find_ref_in_snapshot()`, and calls `browser_click`.

### 6. `hover` (Hover)

Extracts hover target, finds ref, calls `browser_hover`.

---

## Element Matching System

Two complementary matchers:

### `_find_ref_in_snapshot()` — General Purpose

Searches any snapshot line for a matching element. Used for buttons, links, hover targets, etc.

- **Exact match** (priority): The description appears as a substring in the line
- **Fuzzy match** (fallback): Keywords from the description appear in the line (excludes generic terms like "button", "textbox" to avoid false matches)

### `_find_textbox_ref()` — Textbox Specific

Only matches `textbox`/`input`/`textarea`/`searchbox` roles. Returns candidates ranked by priority (exact label > keyword > first-found).

---

## Playwright MCP Tools Used

The task executor communicates with the browser through these MCP tools:

| MCP Tool | Used For | Parameters |
|----------|----------|------------|
| `browser_navigate` | Navigate to URL | `url` |
| `browser_snapshot` | Get accessibility tree (DOM) | — |
| `browser_type` | Type text into an input | `ref`, `text`, `slowly` |
| `browser_click` | Click an element | `ref`, `element` |
| `browser_fill_form` | Structured form fill (fallback) | `fields: [{name, type, ref, value}]` |
| `browser_select_option` | Select dropdown option | `ref`, `values` |
| `browser_take_screenshot` | Capture screenshot | `filename`, `type` |
| `browser_press_key` | Press a keyboard key | `key` |
| `browser_hover` | Hover over element | `ref`, `element` |

### How Snapshots Work

The `browser_snapshot` tool returns an accessibility tree as text. Each interactive element has a `[ref=X]` marker:

```
- heading "Add Client" [level=1]
- textbox "Client Name *" [active] [ref=e33]
- textbox "Website *" [ref=e37]
- combobox "Sales Region *" [ref=e41]: Select a sales region
- button "Save Client" [ref=e65] [cursor=pointer]
```

All element matching and action routing is based on parsing these snapshot lines.

---

## Screenshots & Audit Trail

Each run creates a timestamped directory under `screenshots/`:

```
screenshots/
└── 2026-03-06_19-39-43_170313/
    ├── 01_navigate_devnp-sadhaksahajaiclients.png
    ├── 02_wait_3_seconds.png
    ├── 03_fill_Client_Name_with_TEST-HACK-Acme_Corporation.png
    ├── 04_fill_Website_with_httpsTEST-HACK-acmecom.png
    ├── 05_click_button_SAVE_CLIENT.png
    └── 06_final_state.png
```

Screenshots are captured:
- After the initial navigation
- After each successful action
- On errors
- At the very end (final state)

---

## Flow Definition Format (`flow.md`)

Flows are structured markdown documents that describe a user journey step by step:

```markdown
#### Step 2: FILL client name input field

**Element Metadata:**
- **Role:** `textbox`
- **Accessible Name:** `"Client Name"`
- **Type:** `text`
- **Label:** `"Client Name"` (marked as required)
- **Test ID:** `input-text-box`
- **HTML Attributes:** `id="clientName"`, classes include `p-inputtext`

**Action:** Enter or modify client name
```

The flow intentionally uses `[UNKNOWN]` for metadata that isn't available from snapshot tests. The agent is designed to handle these gracefully.

---

## Configuration & Environment

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Claude API authentication |
| `PLAYWRIGHT_MCP_EXTENSION_TOKEN` | Connects to Chrome's Playwright MCP bridge extension |

The Playwright MCP server runs as a child process via `npx @playwright/mcp@latest --extension`, connecting to an existing Chrome instance with a persistent profile (preserving Google SSO sessions).

---

## Key Design Decisions

1. **Two-layer architecture**: The LLM plans (generates flow strings) and the tool executor acts (runs browser commands). This separation lets the LLM retry with different strategies if execution fails.

2. **Snapshot-based element matching**: Instead of brittle CSS selectors, we use Playwright's accessibility snapshot (`[ref=X]` markers) for element identification. This is resilient to DOM changes.

3. **TEST-HACK prefix**: All generated data is prefixed with `TEST-HACK-` to make test data easily identifiable and cleanable in the database.

4. **`snapshot_and_fill_remaining`**: A safety net that catches any form fields the flow definition didn't explicitly list. This handles real-world forms where the flow spec may be incomplete.

5. **Empty dropdown → auto-create**: When a required dropdown (e.g., Contact) has no options, the tool automatically finds and clicks "Add New" buttons, fills the sub-form, saves, and retries — handling prerequisite data creation autonomously.

6. **`slowly: true` for typing**: Characters are typed one at a time to trigger React/Angular key handlers that listening for individual keystrokes (e.g., for validation or autocomplete).
