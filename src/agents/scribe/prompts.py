"""Prompts for the Scribe Agent."""

ANALYSIS_SYSTEM_PROMPT = """\
You are analyzing a user flow execution. Describe what the user does at each step in simple, plain English. Focus only on the user's actions and what they see — no technical details.
"""

ANALYSIS_USER_PROMPT_TEMPLATE = """\
## Codebase Summary
{codebase_summary}

## Flow Definition (from static analysis)
{flow_markdown}

## Execution Record
{execution_summary}

---

Produce a structured analysis as JSON with these fields:
- `flow_purpose`: 1-2 sentence business description
- `ui_framework`: Component library/framework detected (e.g., "PrimeNG", "Material UI")
- `steps_analysis`: Array of objects, one per executed step:
  - `step_number`: int
  - `business_description`: What the user is doing in plain English
  - `element_description`: Human-friendly description of the UI element
  - `selector_hints`: Best selectors for this element (id, test-id, aria-label)
  - `notes`: Any observations (missing test-id, shared selector, etc.)
- `prerequisites`: What must exist before this flow can run
- `related_flows`: Other flows this depends on or leads to
- `accessibility_issues`: List of accessibility problems found
- `developer_warnings`: List of gotchas or non-obvious behaviors
- `missing_test_coverage`: Elements lacking test IDs or unique selectors

Return ONLY valid JSON, no markdown code fences.
"""

DOCUMENTATION_SYSTEM_PROMPT = """\
You are writing simple user flow documentation. Describe what the user does, step by step, in plain English. Keep it short and easy to read.
"""

DOCUMENTATION_USER_PROMPT_TEMPLATE = """\
Using the information below, write a simple step-by-step user flow.

## Flow Summary
{analysis_json}

## Screenshots
{screenshot_list}

---

Write the output in markdown using this structure:

# [Flow Name]

Brief one-sentence description of what this flow does.

## Steps

1. [What the user does]
2. [What the user does next]
...

Reference screenshots where helpful: ![description](path)

Keep it concise. No technical details, no tables, no developer notes.
"""


def format_analysis_prompt(
    codebase_summary: str,
    flow_markdown: str,
    execution_summary: str,
) -> str:
    return ANALYSIS_USER_PROMPT_TEMPLATE.format(
        codebase_summary=codebase_summary,
        flow_markdown=flow_markdown,
        execution_summary=execution_summary,
    )


def format_documentation_prompt(
    analysis_json: str,
    screenshot_list: str,
) -> str:
    return DOCUMENTATION_USER_PROMPT_TEMPLATE.format(
        analysis_json=analysis_json,
        screenshot_list=screenshot_list,
    )