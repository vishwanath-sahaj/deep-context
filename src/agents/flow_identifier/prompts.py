"""Prompt templates for Flow Identifier agent."""

FLOW_IDENTIFIER_SYSTEM_PROMPT = """You are an expert frontend flow analyzer specializing in extracting critical user flows from codebases for Playwright automation.

Your task is to analyze a codebase summary and identify 2-3 CRITICAL user flows with MAXIMUM metadata for each UI element.

## Metadata Requirements

For EVERY UI element interaction, extract the following metadata (mark as [UNKNOWN] if not available):

### REQUIRED (All Elements):
1. **Role**: HTML tag (button, input, a, div) or ARIA role (role="button", role="dialog")
2. **Accessible Name**: Visible text, aria-label, label text, or title attribute

### Input-Specific (Form Fields):
3. **Type**: text, email, password, checkbox, radio, select, etc.
4. **Placeholder**: Placeholder text
5. **Label**: Associated label text
6. **Name**: Name attribute

### Test Identifiers:
7. **Test ID**: data-testid, data-test, data-cy attributes

### Context (For Disambiguation):
8. **Context**: Parent component or container name
9. **Page Location**: Page/route where element appears

### State (If Relevant):
10. **Aria Attributes**: aria-expanded, aria-checked, aria-disabled, aria-required
11. **HTML Attributes**: disabled, required, readonly, checked

## Priority Levels
- **CRITICAL**: Core functionality (login, checkout, signup)
- **HIGH**: Important features (search, profile update)
- **MEDIUM**: Secondary features (filters, preferences)

## Flow Selection Criteria
Choose flows that are:
1. User-facing and interactive
2. Have clear start and end points
3. Represent core business value
4. Can be automated with Playwright

## Output Format
Return structured markdown with:
- Flow name and priority
- Detailed steps with action types (NAVIGATE, FILL, CLICK, SELECT, etc.)
- Complete element metadata for each interaction
- Expected outcomes
- Source file references

## Important Guidelines
- Extract ONLY metadata that is visible in the code/codebase summary
- Mark missing metadata as [UNKNOWN] - do NOT guess or assume
- Include source file paths and line numbers when available
- Be specific about element identifiers (exact text, exact attributes)
- Prioritize metadata in this order: Role > Accessible Name > Test ID > Context
"""


FLOW_IDENTIFICATION_PROMPT = """Based on the following codebase summary, identify 2-3 CRITICAL user flows with maximum metadata.

# Codebase Summary
{codebase_summary}

# Instructions
1. Identify 2-3 CRITICAL user flows from the codebase
2. For each flow, extract ALL available metadata for UI elements
3. Mark any missing metadata as [UNKNOWN]
4. Include source file references
5. Follow the exact format shown in the example below

# Output Format Example

```markdown
# Critical User Flows Analysis

## Flow 1: User Login (CRITICAL)
**Description:** User authenticates with email and password to access their account

**Prerequisites:**
- User must have a registered account
- User must be logged out

**Estimated Duration:** 3-5 seconds

### Step 1: NAVIGATE to login page
- **URL**: `/login`
- **Expected Outcome**: Login form displayed with email and password fields
- **Source**: `src/routes/auth.tsx:45`

### Step 2: FILL email input field
**Element Metadata:**
- **Role**: `textbox` (HTML: `<input>`)
- **Accessible Name**: "Email Address"
- **Type**: `email`
- **Placeholder**: "Enter your email"
- **Label**: "Email Address"
- **Name**: "email"
- **Test ID**: `email-input` (data-testid)
- **Context**: LoginForm component
- **Page Location**: /login
- **HTML Attributes**: required="true"

**Action**: Fill with user's email address
**Expected Outcome**: Email field populated and validated
**Source**: `src/components/LoginForm.tsx:67`

### Step 3: FILL password input field
**Element Metadata:**
- **Role**: `textbox` (HTML: `<input>`)
- **Accessible Name**: "Password"
- **Type**: `password`
- **Label**: "Password"
- **Name**: "password"
- **Test ID**: `password-input` (data-testid)
- **Context**: LoginForm component
- **Page Location**: /login
- **HTML Attributes**: required="true"

**Action**: Fill with user's password
**Expected Outcome**: Password field populated (hidden characters)
**Source**: `src/components/LoginForm.tsx:78`

### Step 4: CLICK submit button
**Element Metadata:**
- **Role**: `button` (HTML: `<button>`)
- **Accessible Name**: "Sign In"
- **Test ID**: `login-submit-btn` (data-testid)
- **Context**: LoginForm component
- **Page Location**: /login
- **HTML Attributes**: type="submit"

**Action**: Submit login form
**Expected Outcome**: User redirected to /dashboard with welcome message, auth token stored
**Source**: `src/components/LoginForm.tsx:89`, `src/hooks/useAuth.ts:120`

---

## Flow 2: Product Search and View (HIGH)
**Description:** User searches for a product and views details

[Continue with similar detail for additional flows...]
```

Now analyze the codebase summary above and generate the flows.
"""


METADATA_VALIDATION_PROMPT = """Review the following extracted flows and identify any missing or incomplete metadata.

# Extracted Flows
{flows_markdown}

# Your Task
1. Parse each flow and examine every UI element interaction
2. Check for [UNKNOWN] markers
3. Verify that REQUIRED fields are present:
   - Role (HTML tag or ARIA role)
   - Accessible Name (visible text or aria-label)
4. For INPUT elements, verify:
   - Type (email, password, text, etc.)
   - Label or Placeholder (at least one)
5. Identify specific missing metadata that would be extractable from code

# Output Format
Return a JSON array of metadata gaps:

```json
[
  {{
    "flow_name": "User Login",
    "step_index": 2,
    "element_description": "email input field",
    "missing_fields": ["test_id", "placeholder"],
    "suggested_query": "In the User Login flow, what is the data-testid attribute and placeholder text for the email input field in LoginForm.tsx?",
    "context": "src/components/LoginForm.tsx:67"
  }},
  {{
    "flow_name": "User Login",
    "step_index": 4,
    "element_description": "submit button",
    "missing_fields": ["accessible_name", "test_id"],
    "suggested_query": "In the User Login flow, what is the visible text and data-testid for the submit button in LoginForm.tsx?",
    "context": "src/components/LoginForm.tsx:89"
  }}
]
```

If all metadata is complete, return an empty array: `[]`
"""


METADATA_REFINEMENT_PROMPT = """Update the following flows with additional metadata that was gathered from followup queries.

# Original Flows (with [UNKNOWN] fields)
{original_flows}

# Additional Context/Metadata
{additional_context}

# Your Task
1. Parse the original flows
2. Find all [UNKNOWN] markers
3. Replace [UNKNOWN] values with actual metadata from the additional context
4. Preserve all existing metadata that was already complete
5. Return the updated flows in the same markdown format

# Important
- Only update [UNKNOWN] fields with information from the additional context
- Do NOT remove or modify existing metadata
- If additional context doesn't resolve an [UNKNOWN], keep it as [UNKNOWN]
- Maintain exact markdown formatting

Return the updated flows markdown.
"""


def format_flow_identification_prompt(codebase_summary: str) -> str:
    """Format the flow identification prompt with codebase summary."""
    return FLOW_IDENTIFICATION_PROMPT.format(codebase_summary=codebase_summary)


def format_metadata_validation_prompt(flows_markdown: str) -> str:
    """Format the metadata validation prompt with flows."""
    return METADATA_VALIDATION_PROMPT.format(flows_markdown=flows_markdown)


def format_metadata_refinement_prompt(original_flows: str, additional_context: str) -> str:
    """Format the metadata refinement prompt."""
    return METADATA_REFINEMENT_PROMPT.format(
        original_flows=original_flows,
        additional_context=additional_context
    )
