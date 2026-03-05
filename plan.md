# Implementation Plan: Standalone Flow Identifier Tool

## Overview
**Purpose:** Build a standalone Flow Identifier tool that analyzes frontend codebases and extracts critical user flows with maximum metadata for Playwright MCP automation.

## Key Features:
1. Takes natural language codebase summary as input (injectable)
2. Identifies 2-3 critical user flows with rich metadata
3. Detects missing metadata and requests clarification
4. Outputs structured natural language for LLM consumption
5. Completely standalone (no integration with other agents)

---

## Essential Metadata Framework
Based on analysis of Playwright MCP requirements and code-extractable information, the Flow Identifier extracts:

### For Every UI Element:
1. **Role** (REQUIRED)
   - HTML tag: `button`, `input`, `a`, `div`
   - ARIA role: `role="button"`, `role="dialog"`
   - Extractable from: tag names, role attributes
2. **Accessible Name** (REQUIRED)
   - Visible text, `aria-label`, label text, title
   - Extractable from: text content, label associations, aria attributes
3. **Input-Specific** (for form fields)
   - Type: `text`, `email`, `password`, `checkbox`
   - Placeholder text
   - Name attribute
   - Extractable from: input attributes
4. **Test IDs** (if available)
   - `data-testid`, `data-test`, `data-cy`
   - Extractable from: data attributes in JSX/templates
5. **Context** (for disambiguation)
   - Parent component/container
   - Page location
   - Extractable from: component hierarchy, route info
6. **State** (if relevant)
   - `aria-expanded`, `aria-checked`, `disabled`, `required`
   - Extractable from: aria attributes, HTML attributes

---

## Directory Structure

```text
src/agents/flow-identifier/
├── __init__.py
├── agent.py                 # Main FlowIdentifierAgent class
├── prompts.py              # All prompt templates
├── metadata_validator.py   # Validates metadata completeness
├── metadata_requester.py   # Generates followup queries
└── types.py                # Type definitions
```

---

## Implementation Components

### 1. Type Definitions (`types.py`)
Defines data structures:
- `ElementMetadata`: All extractable metadata for a UI element
- `FlowStep`: Single action in a flow with metadata
- `Flow`: Complete user flow with multiple steps
- `MetadataGap`: Represents missing metadata needing clarification

Key structures:
```python
# - ElementMetadata: role, accessible_name, type, placeholder, label, test_id, context, aria_attributes
# - FlowStep: action, description, element_metadata, value, url, expected_outcome, source_file
# - Flow: name, priority, description, steps, source_files
# - MetadataGap: flow_name, step_index, element_description, missing_fields, suggested_query
```

### 2. Prompt Engineering (`prompts.py`)
Three main prompts:

#### A. `FLOW_IDENTIFIER_SYSTEM_PROMPT`
- Instructs LLM to extract flows with maximum metadata
- Defines required metadata fields (role, accessible name, etc.)
- Specifies priority levels (critical/high/medium)
- Sets output format expectations

#### B. `FLOW_IDENTIFICATION_PROMPT`
- Template for initial flow extraction
- Includes detailed example showing metadata structure
- Instructs to mark missing data as `UNKNOWN`
- Formats: `{codebase_summary}` injection point

#### C. `METADATA_VALIDATION_PROMPT`
- Reviews extracted flows for completeness
- Identifies `UNKNOWN` fields
- Generates specific queries for missing metadata

### 3. Main Agent (`agent.py`)
`FlowIdentifierAgent` class with three key methods:

- `identify_flows(codebase_summary, request_missing_metadata=True)`
  - Main entry point
  - Extracts flows from codebase summary
  - Optionally validates metadata and generates followup queries
  - Returns: `(flows_markdown, optional_followup_queries)`

- `_extract_flows(codebase_summary)`
  - Calls Claude API with system + user prompts
  - Uses: `claude-sonnet-4-5`, `max_tokens=8192`, `temperature=0.0`
  - Returns: Structured markdown with flows

- `refine_with_additional_context(initial_flows, additional_context)`
  - Takes initial flows with `UNKNOWN` fields
  - Merges with additional metadata from followup answers
  - Returns: Updated flows with filled metadata

### 4. Metadata Validator (`metadata_validator.py`)
`MetadataValidator` class:

- `identify_gaps(flows_markdown)`
  - Parses markdown to find missing metadata
  - Checks for `UNKNOWN` markers
  - Validates required fields (role, accessible_name)
  - For inputs: validates type, label/placeholder
  - Returns: List of `MetadataGap` objects

- `_parse_flows(markdown)`
  - Parses markdown into structured flow data
  - Returns: List of flows with steps

- `_check_missing_metadata(step)`
  - Checks if step has required metadata
  - Returns: List of missing field names

- `_generate_query(step, missing_fields)`
  - Creates specific query for missing metadata
  - Returns: Natural language query string

### 5. Metadata Requester (`metadata_requester.py`)
`MetadataRequester` class:

- `generate_queries(gaps)`
  - Takes list of `MetadataGap` objects
  - Builds specific queries for each gap
  - Deduplicates similar queries
  - Returns: List of natural language queries for codebase tool

- `_build_query(gap)`
  - Constructs targeted query based on:
    - Flow name
    - Element description
    - Missing fields
  - Examples:
    - "In the User Login flow, for the 'email input', what is the HTML tag and label text?"
    - "For the 'submit button' in checkout, what is the data-testid attribute?"

---

## Output Format
The Flow Identifier produces structured markdown like this:

```markdown
Critical User Flows Analysis

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
- **Context**: Login form component
- **Additional**: required attribute present

**Expected Outcome**: Email field populated
**Source**: `src/components/LoginForm.tsx:67`

### Step 3: FILL password input field
**Element Metadata:**
- **Role**: `textbox`
- **Accessible Name**: "Password"
- **Type**: `password`
- **Label**: "Password"
- **Test ID**: `password-input`
- **Context**: Login form component
- **Additional**: required attribute present

**Expected Outcome**: Password field populated (hidden)
**Source**: `src/components/LoginForm.tsx:78`

### Step 4: CLICK submit button
**Element Metadata:**
- **Role**: `button`
- **Accessible Name**: "Sign In"
- **Test ID**: `login-submit-btn`
- **Context**: Login form component
- **Additional**: `type="submit"`

**Expected Outcome**: Redirect to /dashboard with welcome message
**Source**: `src/components/LoginForm.tsx:89`, `src/hooks/useAuth.ts:120`

---

## Flow 2: [Next Flow]...
```

---

## Usage Workflow

### Scenario 1: Complete Metadata Available
```python
from agents.flow_identifier import FlowIdentifierAgent

agent = FlowIdentifierAgent()

# Input: Natural language codebase summary
codebase_summary = """
The application has a login page at /login with:
- Email input: <input type="email" placeholder="Enter your email" data-testid="email-input">
- Password input: <input type="password" data-testid="password-input">
- Submit button: <button type="submit">Sign In</button>
Located in: src/components/LoginForm.tsx
"""

# Extract flows
flows_markdown, followup_queries = await agent.identify_flows(codebase_summary)

# If followup_queries is None, all metadata was extracted
print(flows_markdown)
```

### Scenario 2: Missing Metadata - Requests Clarification
```python
# Input: Incomplete codebase summary
incomplete_summary = """
The app has a login page with an email field, password field, and submit button.
Located in: src/pages/Login.tsx
"""

# Extract flows
flows_markdown, followup_queries = await agent.identify_flows(incomplete_summary)

# followup_queries will contain:
# [
#   "In the User Login flow, what is the HTML element type and label for the email field?",
#   "What are the data-testid attributes for the email and password inputs?",
#   "What is the visible text on the submit button?"
# ]

# User provides additional context by querying codebase tool with these questions
additional_context = """
Email field: <input type="email" data-testid="email-input" aria-label="Email Address">
Password field: <input type="password" data-testid="pwd-input">
Submit button: <button>Log In</button>
"""

# Refine flows with additional metadata
refined_flows = await agent.refine_with_additional_context(
    flows_markdown, 
    additional_context
)

print(refined_flows)
```

---

## Key Design Decisions
1. **Natural Language I/O:** Inputs and outputs are natural language markdown, not JSON
   - Easier for LLMs to consume
   - Human-readable and editable
   - Flexible structure
2. **Metadata-First Approach:** Prioritizes extracting maximum element metadata
   - Enables reliable Playwright automation
   - Reduces ambiguity in element selection
   - Follows Playwright best practices (role > label > text > testid)
3. **Graceful Degradation:** Marks missing metadata as `UNKNOWN` and requests it
   - Doesn't fail on incomplete information
   - Generates specific followup queries
   - Allows iterative refinement
4. **Code-Extractable Only:** All metadata must be extractable from code analysis
   - No assumptions about runtime behavior
   - No reliance on screenshots or visual inspection
   - Based on static code structure
5. **Standalone & Injectable:** No external dependencies on other agents
   - Takes raw input (codebase summary)
   - Returns structured output (flows + optional queries)
   - Can be tested with mock inputs

---

## Summary
This implementation plan provides:
- ✅ Standalone tool - No integration complexity  
- ✅ Rich metadata extraction - Maximum element details for Playwright  
- ✅ Missing metadata detection - Identifies and requests clarification  
- ✅ Code-based extraction - All metadata extractable from frontend code  
- ✅ LLM-friendly I/O - Natural language inputs and outputs  
- ✅ Injectable inputs - Easy to test with sample data  
- ✅ Iterative refinement - Can enhance flows with additional context  

### Next Steps for Implementation:
1. Create directory structure
2. Implement type definitions
3. Write prompt templates
4. Implement `FlowIdentifierAgent`
5. Implement `MetadataValidator`
6. Implement `MetadataRequester`
7. Test with sample codebase summaries

Ready to proceed with implementation when you are!

▣  Plan · claude-sonnet-4-5 · 53.8s

Before that could u generate an architecture diagram of what the system would look like when this is implemented ? Include each component u are suggesting for the flow identifier and show how it fits in the architecture that is already present include it in the plan as well. 

Perfect! Let me create an architecture diagram showing how the Flow Identifier fits into the existing system. First, let me explore the current architecture to understand it better.

# Explore Task
Map current system architecture (16 toolcalls)
└ Bash List Python files to understand structure
ctrl+x right view subagents

Excellent! Now I have a clear picture of the current architecture. Let me create a comprehensive architecture diagram showing both the existing system and where the Flow Identifier fits in.

## Architecture Diagrams

### Current System Architecture (Based on Exploration)

```text
┌─────────────────────────────────────────────────────────────────────┐
│                          USER (CLI/REPL)                            │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Main Orchestrator     │
                    │   (main.py)             │
                    │   - CLI interface       │
                    │   - REPL loop           │
                    │   - Coordinates agents  │
                    └────┬─────────────┬──────┘
                         │             │
          ┌──────────────▼─┐      ┌───▼──────────────┐
          │   Planner      │      │   Indexer        │
          │   (QueryRouter)│      │   - Walks repo   │
          │   - Classifies │      │   - Chunks files │
          │     queries    │      │   - Creates FAISS│
          │   - Routes to  │      │     index        │
          │     query type │      └───┬──────────────┘
          └────────┬───────┘          │
                   │                  │
        ┌──────────▼──────────────────▼─────────────┐
        │         Executor                          │
        │   - Holds vector_store reference          │
        │   - Routes by query type:                 │
        │     • METADATA: file stats + Claude       │
        │     • SEARCH: FAISS search + Claude       │
        │     • REASONING: Deep RAG + Claude        │
        │     • TOOL: reindex/clone operations      │
        └─────────────┬──────────┬──────────────────┘
                      │          │
          ┌───────────▼─┐    ┌───▼───────────┐
          │  Retrieval  │    │   Verifier    │
          │  - FAISS    │    │  - Validates  │
          │    k-NN     │    │    responses  │
          │  - Context  │    │  - Detects    │
          │    builder  │    │    uncertainty│
          └─────────────┘    └───────────────┘
                │                    │
                └────────┬───────────┘
                         │
              ┌──────────▼──────────┐
              │  Claude API         │
              │  (Anthropic)        │
              │  - Answer queries   │
              │  - Summarize data   │
              │  - Self-critique    │
              └─────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL RESOURCES                           │
│  • FAISS Index: <repo>/.deep-context-index/                         │
│  • HuggingFace Embeddings: Local model (all-MiniLM-L6-v2)           │
│  • File System: Repository files                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Proposed Architecture with Flow Identifier Integration

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                          USER (CLI/REPL)                                │
│                     "Identify critical flows in this repo"              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Main Orchestrator     │
                    │   (main.py)             │
                    │   - Routes flow         │
                    │     discovery requests  │
                    └────┬────────────────────┘
                         │
          ┌──────────────▼─────────────────┐
          │   Discovery Agent (NEW)        │
          │   - Orchestrates flow          │
          │     identification             │
          │   - Manages tool calls         │
          │   - Synthesizes results        │
          └──┬──────────────────┬──────────┘
             │                  │
   ┌─────────▼──────┐    ┌──────▼───────────────────────────┐
   │  Codebase Tool │    │  Flow Identifier Tool (NEW)      │
   │  (Existing)    │    │  ┌────────────────────────────┐  │
   │  Uses:         │    │  │  FlowIdentifierAgent       │  │
   │  - Planner     │    │  │  - identify_flows()        │  │
   │  - Executor    │    │  │  - refine_with_context()   │  │
   │  - Retrieval   │    │  └──────────┬─────────────────┘  │
   │                │    │             │                    │
   │  Returns:      │    │  ┌──────────▼─────────────────┐  │
   │  Natural       │    │  │  MetadataValidator         │  │
   │  language      │    │  │  - identify_gaps()         │  │
   │  summaries     │    │  │  - check_missing_metadata()│  │
   │                │    │  └──────────┬─────────────────┘  │
   └────────────────┘    │             │                    │
                         │  ┌──────────▼─────────────────┐  │
                         │  │  MetadataRequester         │  │
                         │  │  - generate_queries()      │  │
                         │  │  - build_query()           │  │
                         │  └──────────┬─────────────────┘  │
                         │             │                    │
                         │  ┌──────────▼─────────────────┐  │
                         │  │  Prompts Module            │  │
                         │  │  - FLOW_IDENTIFIER_PROMPT  │  │
                         │  │  - VALIDATION_PROMPT       │  │
                         │  └────────────────────────────┘  │
                         └──────────────────────────────────┘
                                        │
                         ┌──────────────▼──────────────┐
                         │     Claude API              │
                         │     - Flow extraction       │
                         │     - Metadata validation   │
                         └─────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│                    DATA FLOW (Flow Identification)                   │
│                                                                      │
│  1. User: "Identify critical flows"                                  │
│  2. Orchestrator → Discovery Agent                                   │
│  3. Discovery → Codebase Tool (multiple queries):                    │
│      - "List all user-facing pages and routes"                       │
│      - "Identify form components and their fields"                   │
│      - "Where is authentication logic?"                              │
│  4. Codebase Tool returns: Natural language summaries (markdown)     │
│  5. Discovery → Flow Identifier Tool (with codebase summaries)       │
│  6. Flow Identifier:                                                 │
│      a. Extracts flows with Claude (via prompts)                     │
│      b. Validates metadata completeness                              │
│      c. IF missing metadata:                                         │
│         - Generates followup queries                                 │
│         - Returns (flows_markdown, followup_queries)                 │
│      d. IF complete:                                                 │
│         - Returns (flows_markdown, None)                             │
│  7. IF followup queries exist:                                       │
│      a. Discovery → Codebase Tool (with followup queries)            │
│      b. Codebase Tool returns: Additional metadata                   │
│      c. Discovery → Flow Identifier (refine_with_context)            │
│      d. Flow Identifier returns: Updated flows                       │
│  8. Discovery → Orchestrator (final flows)                           │
│  9. Orchestrator → User (display flows)                              │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Flow Identifier Internal Architecture (Detailed)

```text
┌───────────────────────────────────────────────────────────────────────┐
│                     Flow Identifier Tool                              │
│                     (Standalone Module)                               │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                  FlowIdentifierAgent                            │  │
│  │  ┌──────────────────────────────────────────────────────────┐   │  │
│  │  │  identify_flows(codebase_summary)                        │   │  │
│  │  │    ↓                                                     │   │  │
│  │  │  1. _extract_flows() ─────────┐                          │   │  │
│  │  │    • Formats prompt           │                          │   │  │
│  │  │    • Calls Claude API         │                          │   │  │
│  │  │    • Returns flows_markdown   │                          │   │  │
│  │  │                               │                          │   │  │
│  │  │  2. MetadataValidator ◄───────┘                          │   │  │
│  │  │    • identify_gaps()                                     │   │  │
│  │  │    • Parses markdown                                     │   │  │
│  │  │    • Checks for [UNKNOWN]                                │   │  │
│  │  │    • Validates required fields                           │   │  │
│  │  │    • Returns List[MetadataGap]                           │   │  │
│  │  │                               │                          │   │  │
│  │  │  3. MetadataRequester ◄───────┘                          │   │  │
│  │  │    • generate_queries()                                  │   │  │
│  │  │    • Builds specific questions                           │   │  │
│  │  │    • Deduplicates                                        │   │  │
│  │  │    • Returns List[str]                                   │   │  │
│  │  │                                                          │   │  │
│  │  │  Returns: (flows_markdown, followup_queries)             │   │  │
│  │  └──────────────────────────────────────────────────────────┘   │  │
│  │                                                                 │  │
│  │  ┌──────────────────────────────────────────────────────────┐   │  │
│  │  │  refine_with_additional_context(flows, context)          │   │  │
│  │  │    ↓                                                     │   │  │
│  │  │  1. Merges initial flows with additional metadata        │   │  │
│  │  │  2. Calls Claude with refinement prompt                  │   │  │
│  │  │  3. Fills in [UNKNOWN] fields                            │   │  │
│  │  │                                                          │   │  │
│  │  │  Returns: refined_flows_markdown                         │   │  │
│  │  └──────────────────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                   Supporting Modules                            │  │
│  │                                                                 │  │
│  │  ┌────────────────┐  ┌─────────────────┐  ┌────────────────┐    │  │
│  │  │  types.py      │  │  prompts.py     │  │  validators    │    │  │
│  │  │                │  │                 │  │                │    │  │
│  │  │ • ElementMeta  │  │ • SYSTEM_PROMPT │  │ • Regex checks │    │  │
│  │  │ • FlowStep     │  │ • USER_PROMPT   │  │ • Field checks │    │  │
│  │  │ • Flow         │  │ • VALIDATION    │  │ • Parse logic  │    │  │
│  │  │ • MetadataGap  │  │   _PROMPT       │  │                │    │  │
│  │  └────────────────┘  └─────────────────┘  └────────────────┘    │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────────┐
│                        INPUT / OUTPUT                                 │
│                                                                       │
│  INPUT:  Natural language codebase summary (from Codebase Tool)       │
│          ↓                                                            │
│          "The app has pages at /login, /dashboard, /checkout..."      │
│          "Login form has email input (type='email'), password..."     │
│                                                                       │
│  OUTPUT: Structured markdown with flows + metadata                    │
│          ↓                                                            │
│          ## Flow 1: User Login (CRITICAL)                             │
│          ### Step 1: FILL email field                                 │
│          **Element Metadata:**                                        │
│          - Role: textbox                                              │
│          - Accessible Name: "Email Address"                           │
│          - Type: email                                                │
│          - Placeholder: "Enter your email"                            │
│          ...                                                          │
│                                                                       │
│  OPTIONAL OUTPUT: Followup queries (if metadata incomplete)           │
│          ↓                                                            │
│          ["In login flow, what is the data-testid for email?",        │
│           "What is the visible text on the submit button?"]           │
└───────────────────────────────────────────────────────────────────────┘
```

---

### Component Interaction Diagram (Sequence)

```text
User    Orchestrator   Discovery    Codebase    Flow Identifier    Claude API
 │           │            │           Tool           Tool              │
 │───────────▶│           │            │              │                │
 │ "identify │           │            │              │                │
 │  flows"   │           │            │              │                │
 │           │───────────▶│           │              │                │
 │           │           │────────────▶│             │                │
 │           │           │"list pages"│             │                │
 │           │           │◄────────────│             │                │
 │           │           │  summary   │             │                │
 │           │           │────────────▶│             │                │
 │           │           │"find forms"│             │                │
 │           │           │◄────────────│             │                │
 │           │           │  summary   │             │                │
 │           │           │                           │                │
 │           │           │───────────────────────────▶│               │
 │           │           │  Combined codebase summary│                │
 │           │           │                           │────────────────▶│
 │           │           │                           │ extract flows  │
 │           │           │                           │◄────────────────│
 │           │           │                           │  flows_markdown│
 │           │           │                           │                │
 │           │           │                           │ (internal:     │
 │           │           │                           │  validate      │
 │           │           │                           │  metadata)     │
 │           │           │                           │                │
 │           │           │◄───────────────────────────│               │
 │           │           │ (flows, followup_queries) │                │
 │           │           │                           │                │
 │           │           │─────────────▶│            │                │
 │           │           │ followup Q1  │            │                │
 │           │           │◄─────────────│            │                │
 │           │           │  metadata    │            │                │
 │           │           │                           │                │
 │           │           │───────────────────────────▶│               │
 │           │           │  refine with metadata     │                │
 │           │           │                           │────────────────▶│
 │           │           │                           │  merge context │
 │           │           │                           │◄────────────────│
 │           │           │◄───────────────────────────│               │
 │           │           │   refined flows           │                │
 │           │◄───────────│                          │                │
 │           │  final flows                          │                │
 │◄───────────│                                      │                │
 │  Display  │                                       │                │
```

---

### File Structure Integration

```text
deep-context/
├── src/
│   ├── agents/
│   │   ├── main.py                    # Orchestrator (existing)
│   │   ├── planner/
│   │   │   └── agent.py              # QueryRouter (existing)
│   │   ├── executor/
│   │   │   └── agent.py              # Executor (existing)
│   │   ├── verifier/
│   │   │   └── agent.py              # Verifier (existing)
│   │   ├── indexer/
│   │   │   └── agent.py              # Indexer (existing)
│   │   ├── retrieval/
│   │   │   └── agent.py              # Retrieval (existing)
│   │   ├── discovery/                # NEW - Discovery Agent
│   │   │   ├── __init__.py
│   │   │   └── agent.py              # Orchestrates flow discovery
│   │   └── flow-identifier/          # NEW - Flow Identifier Tool
│   │       ├── __init__.py
│   │       ├── agent.py              # FlowIdentifierAgent
│   │       ├── prompts.py            # Prompt templates
│   │       ├── metadata_validator.py # MetadataValidator class
│   │       ├── metadata_requester.py # MetadataRequester class
│   │       └── types.py              # Type definitions
│   ├── common/
│   │   ├── config.py                 # Config (existing)
│   │   └── logger.py                 # Logger (existing)
└── .deep-context-index/              # FAISS indices (per repo)
```

---

## Key Architecture Changes Summary

### What's Added:
1. **Discovery Agent (`src/agents/discovery/agent.py`)**
   - **Role:** Orchestrator for flow identification workflow
   - **Responsibilities:** 
     - Manages calls to Codebase Tool
     - Invokes Flow Identifier Tool
     - Handles iterative metadata refinement
   - **Integration:** Called by Main Orchestrator for flow discovery requests
2. **Flow Identifier Tool (`src/agents/flow-identifier/`)**
   - **Role:** Standalone tool for extracting flows with metadata
   - **Components:**
     - `agent.py`: Main `FlowIdentifierAgent` class
     - `metadata_validator.py`: Validates metadata completeness
     - `metadata_requester.py`: Generates followup queries
     - `prompts.py`: LLM prompt templates
     - `types.py`: Type definitions
   - **Integration:** Called by Discovery Agent as a tool

### What's Reused:
1. **Codebase Tool** (existing Planner + Executor + Retrieval)
   - Used by Discovery Agent to query repository
   - No modifications needed
2. **Claude API integration** (existing patterns)
   - Flow Identifier uses same Anthropic client pattern
   - Follows existing prompt engineering approach
3. **Configuration & Logging** (existing)
   - Flow Identifier uses same `Config` class
   - Uses existing structured logging

### Integration Points:
1. **Main Orchestrator → Discovery Agent**
   - When user requests flow identification
   - Passes repository path
2. **Discovery Agent → Codebase Tool**
   - Queries for UI components, routes, forms
   - Gets natural language summaries
3. **Discovery Agent → Flow Identifier Tool**
   - Passes codebase summaries
   - Receives flows + optional followup queries
4. **Flow Identifier → Claude API**
   - Extracts flows
   - Validates metadata

### Data Flow Characteristics:
- **Input:** Natural language (codebase summaries)
- **Output:** Structured natural language (flows markdown)
- **Communication:** Synchronous method calls (matches existing pattern)
- **State:** Minimal state (flows held temporarily in Discovery Agent)
- **Error handling:** Graceful degradation with `UNKNOWN` markers

---

This architecture maintains the existing system's design patterns while adding the Flow Identifier as a clean, standalone module that integrates naturally into the agent ecosystem.
