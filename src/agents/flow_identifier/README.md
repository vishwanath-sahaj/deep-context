# Flow Identifier Agent

A standalone tool that analyzes frontend codebases and extracts critical user flows with maximum metadata for Playwright automation.

## Overview

The Flow Identifier is designed to:
- Extract 2-3 critical user flows from codebase summaries
- Capture rich metadata for every UI element (role, accessible name, test IDs, etc.)
- Detect missing metadata and generate specific followup queries
- Support iterative refinement as more information becomes available

## Architecture

```
flow-identifier/
├── __init__.py              # Public API exports
├── agent.py                 # Main FlowIdentifierAgent class
├── prompts.py              # LLM prompt templates
├── types.py                # Type definitions
├── metadata_validator.py   # Validates metadata completeness
├── metadata_requester.py   # Generates followup queries
└── README.md               # This file
```

## Key Components

### FlowIdentifierAgent (`agent.py`)
Main entry point for flow identification.

**Methods:**
- `identify_flows(codebase_summary, request_missing_metadata=True)` - Extract flows from codebase summary
- `refine_with_additional_context(initial_flows, additional_context)` - Update flows with additional metadata

### Type Definitions (`types.py`)
Defines data structures:
- `ElementMetadata` - All extractable metadata for a UI element
- `FlowStep` - Single action in a flow
- `Flow` - Complete user flow
- `MetadataGap` - Missing metadata requiring clarification
- `FlowIdentificationResult` - Result of flow identification

### Prompts (`prompts.py`)
LLM prompt templates for:
- Flow extraction with metadata requirements
- Metadata validation
- Flow refinement with additional context

### MetadataValidator (`metadata_validator.py`)
Validates extracted flows for completeness:
- Checks for `[UNKNOWN]` markers
- Validates required fields (role, accessible_name)
- Verifies input-specific requirements

### MetadataRequester (`metadata_requester.py`)
Generates followup queries for missing metadata:
- Creates specific, targeted queries
- Deduplicates similar queries
- Formats queries for codebase tool

## Usage

### Basic Usage

```python
from src.agents.flow_identifier import FlowIdentifierAgent

# Initialize agent
agent = FlowIdentifierAgent()

# Provide codebase summary
codebase_summary = """
The application has a login page at /login with:
- Email input: <input type="email" data-testid="email-input">
- Password input: <input type="password" data-testid="password-input">
- Submit button: <button type="submit">Sign In</button>
Located in: src/components/LoginForm.tsx
"""

# Extract flows
result = agent.identify_flows(codebase_summary)

# Access flows
print(result.flows_markdown)

# Check for missing metadata
if result.followup_queries:
    print("Missing metadata detected:")
    for query in result.followup_queries:
        print(f"  - {query}")
```

### With Metadata Refinement

```python
# Initial extraction with incomplete data
result = agent.identify_flows(incomplete_summary)

if result.followup_queries:
    # Use queries with codebase tool to get additional context
    additional_context = codebase_tool.query(result.followup_queries[0])
    
    # Refine flows with additional metadata
    refined_flows = agent.refine_with_additional_context(
        initial_flows=result.flows_markdown,
        additional_context=additional_context
    )
    
    print(refined_flows)
```

### Convenience Functions

```python
from src.agents.flow_identifier import identify_flows

# Quick one-liner
result = identify_flows(codebase_summary)
```

## Metadata Framework

The Flow Identifier extracts the following metadata for each UI element:

### Required (All Elements)
- **Role**: HTML tag or ARIA role (e.g., `button`, `textbox`)
- **Accessible Name**: Visible text, aria-label, or label text

### Input-Specific
- **Type**: Input type (e.g., `email`, `password`, `text`)
- **Placeholder**: Placeholder text
- **Label**: Associated label text
- **Name**: Name attribute

### Test Identifiers
- **Test ID**: data-testid, data-test, or data-cy attributes

### Context
- **Context**: Parent component or container
- **Page Location**: Route or page where element appears

### State
- **ARIA Attributes**: aria-expanded, aria-checked, etc.
- **HTML Attributes**: disabled, required, readonly, etc.

## Output Format

Flows are returned as structured markdown:

```markdown
# Critical User Flows Analysis

## Flow 1: User Login (CRITICAL)
**Description:** User authenticates with email and password

### Step 1: NAVIGATE to login page
- **URL**: `/login`
- **Expected Outcome**: Login form displayed
- **Source**: `src/routes/auth.tsx:45`

### Step 2: FILL email input field
**Element Metadata:**
- **Role**: `textbox`
- **Accessible Name**: "Email Address"
- **Type**: `email`
- **Placeholder**: "Enter your email"
- **Label**: "Email Address"
- **Test ID**: `email-input`
- **Context**: LoginForm component

**Expected Outcome**: Email field populated
**Source**: `src/components/LoginForm.tsx:67`
```

## Testing

Run the test script to verify the implementation:

```bash
python test_flow_identifier.py
```

This will:
1. Extract flows from a sample codebase summary
2. Validate metadata completeness
3. Generate followup queries if needed
4. Test metadata refinement

## Design Decisions

1. **Natural Language I/O**: Inputs and outputs are natural language markdown
   - Easier for LLMs to consume
   - Human-readable and editable
   - Flexible structure

2. **Metadata-First Approach**: Prioritizes extracting maximum element metadata
   - Enables reliable Playwright automation
   - Reduces ambiguity in element selection
   - Follows Playwright best practices

3. **Graceful Degradation**: Marks missing metadata as `[UNKNOWN]`
   - Doesn't fail on incomplete information
   - Generates specific followup queries
   - Allows iterative refinement

4. **Code-Extractable Only**: All metadata must be extractable from code
   - No assumptions about runtime behavior
   - No reliance on screenshots or visual inspection
   - Based on static code structure

5. **Standalone & Injectable**: No external dependencies
   - Takes raw input (codebase summary)
   - Returns structured output
   - Can be tested with mock inputs

## Configuration

The agent uses the Claude API with the following settings:
- **Model**: `claude-sonnet-4-5`
- **Temperature**: `0.0` (deterministic)
- **Max Tokens**: `8192` (for flow extraction)

API key is loaded from environment via `config.CLAUDE_API_KEY`.

## Integration Points

The Flow Identifier is designed to work with:
- **Codebase Tool**: Provides natural language summaries of the codebase
- **Discovery Agent**: Orchestrates the flow identification workflow
- **Playwright MCP**: Consumes the extracted flows for automation

## Future Enhancements

Potential improvements:
- Support for more complex flows (conditional branches, loops)
- Visual flow diagrams generation
- Direct integration with Playwright test generation
- Support for mobile-specific flows
- Confidence scores for metadata quality

## Troubleshooting

### API Key Issues
Ensure `CLAUDE_API_KEY` is set in your `.env` file:
```bash
CLAUDE_API_KEY=your_api_key_here
```

### Import Errors
Make sure you're importing from the correct module:
```python
from src.agents.flow_identifier import FlowIdentifierAgent
```

### Empty Flows
If flows are empty, check:
- Codebase summary has enough detail
- Summary describes user-facing UI elements
- Summary includes file paths and line numbers

### Too Many Followup Queries
If the agent generates many followup queries:
- Provide more detailed codebase summaries upfront
- Include specific HTML attributes in summaries
- Add test IDs and labels to summaries

## Contributing

When adding new features:
1. Update type definitions in `types.py`
2. Add corresponding prompt templates in `prompts.py`
3. Update validation logic in `metadata_validator.py`
4. Add tests to `test_flow_identifier.py`
5. Update this README

## License

Part of the deep-context project.
