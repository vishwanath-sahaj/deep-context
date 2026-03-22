"""Prompts for the Scribe Agent."""

ANALYSIS_SYSTEM_PROMPT = """\
You are a senior software engineer analyzing a user flow execution. You have three sources of information:

1. **Codebase Knowledge** - A summary of the application's code, components, routes, and architecture.
2. **Flow Definition** - The structured flow extracted from static code analysis, with element metadata.
3. **Execution Record** - What actually happened when the flow was executed in a real browser, including accessibility snapshots and action results.

Your job is to produce a structured analysis that a documentation writer can use. Focus on:

- What each step does in business terms (not technical terms like "clicked ref=e33")
- What UI patterns and component libraries are used
- Discrepancies between the flow definition and actual execution
- Missing accessibility attributes or test IDs that would help developers
- Dependencies on other flows or data
- Edge cases and potential issues you noticed in the snapshots
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
You are a senior developer writing internal documentation for your team. You write clearly and concisely, as if explaining the flow to a new team member who needs to understand how this part of the application works.

Your documentation style:
- Lead with purpose: why does this flow exist?
- Describe what the user sees and does, not implementation details
- Use screenshots as visual anchors (reference them with markdown image syntax)
- Include a quick-reference table of form fields with their selectors
- Call out non-obvious behavior in warning blocks
- Reference source files so developers can find the code
- Keep it scannable: headers, tables, and short paragraphs
- Write in present tense ("The user navigates to...", "The form contains...")
"""

DOCUMENTATION_USER_PROMPT_TEMPLATE = """\
Using the structured analysis below and the screenshots from the flow execution, write developer documentation for this user flow.

## Structured Analysis
{analysis_json}

## Screenshot Paths
{screenshot_list}

## Source Codebase Summary (for code references)
{codebase_summary}

---

Write the documentation in markdown. Use this structure:

# [Flow Name]

## Overview
Brief description, source files, auth requirements.

## Prerequisites
What must exist before running this flow.

## Walkthrough

### Step N: [Action Description]
- What the user does
- Reference screenshot: ![description](path)
- Notable behavior

## Form Fields Reference
| Field | Type | Required | Selector | Notes |
|-------|------|----------|----------|-------|

## Developer Notes
- Warnings, gotchas, accessibility issues
- Related flows with cross-references

Write the full documentation now.
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
    codebase_summary: str,
) -> str:
    return DOCUMENTATION_USER_PROMPT_TEMPLATE.format(
        analysis_json=analysis_json,
        screenshot_list=screenshot_list,
        codebase_summary=codebase_summary,
    )