# Discovery Agent - Quick Summary

## What is it?

The Discovery Agent automatically analyzes frontend codebases and extracts **critical user flows** (like login, checkout, search) with all the metadata needed for automated testing with tools like Playwright.

## Why use it?

Instead of manually exploring code to understand user journeys, run one command:

```bash
discover /path/to/frontend
```

And get structured documentation like this:

```markdown
## Flow 1: User Login (CRITICAL)

### Step 1: NAVIGATE to login page
- **URL**: `/login`

### Step 2: FILL email input
- **Role**: textbox
- **Label**: "Email Address"
- **Test ID**: email-input
- **Type**: email

### Step 3: FILL password input
- **Role**: textbox
- **Test ID**: password-input
- **Type**: password

### Step 4: CLICK login button
- **Role**: button
- **Test ID**: login-submit-btn
- **Expected Outcome**: User redirected to dashboard
```

## How does it work?

```
┌─────────────────────────────────────────────────────────────┐
│ 1. INDEX                                                     │
│    Build/load FAISS vector index of codebase               │
│    [Takes 30s-5min first time, <1s after]                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 2. EXPLORE                                                   │
│    Ask 5 strategic questions about the codebase:           │
│    • "What are all the routes/pages?"                       │
│    • "Where are the forms and input fields?"                │
│    • "How is authentication implemented?"                   │
│    • "What buttons/links exist?"                            │
│    • "What are the critical user interactions?"             │
│    [Takes ~30-60 seconds]                                   │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 3. IDENTIFY FLOWS                                           │
│    Use Claude to extract structured flows from answers      │
│    [Takes ~15-30 seconds]                                   │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│ 4. REFINE (if needed)                                       │
│    If metadata is missing (test IDs, selectors), query     │
│    codebase again with specific questions                   │
│    [Takes ~20-40 seconds if needed]                         │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
        📄 Structured Markdown Output
```

**Total time**: ~1-2 minutes for complete analysis

## What does it produce?

A structured markdown document with:

✅ **Critical user flows** prioritized by importance  
✅ **Step-by-step actions** (NAVIGATE, FILL, CLICK, etc.)  
✅ **Rich metadata** for each UI element:
   - Accessible names/labels
   - Test IDs and data attributes
   - Element types and roles
   - Placeholder text
   - Context (which form/page)
✅ **Source references** - exact file:line for verification  
✅ **Expected outcomes** for each step  

## Quick Start

### From CLI (Interactive)
```bash
# Start RepoPilot
uv run python -m src.agents.main

# In the REPL
> discover .                        # Current directory
> discover /path/to/frontend        # Specific path
> discover . --reindex              # Force re-index first
```

## Key Features

| Feature | Description |
|---------|-------------|
| **Auto-indexing** | Automatically indexes repo on first run, reuses index after |
| **Smart exploration** | Uses strategic queries to understand codebase structure |
| **Metadata extraction** | Finds test IDs, labels, selectors needed for automation |
| **Gap filling** | Automatically queries codebase again if metadata is incomplete |
| **Source tracking** | Every flow step includes file:line reference |
| **Progress display** | Beautiful Rich console output with progress bars |

## What it uses under the hood

The Discovery Agent orchestrates three existing components:

1. **Indexer Agent** (`src/agents/indexer/`)
   - Creates FAISS vector index of codebase
   - Enables semantic search over code

2. **Executor Agent** (`src/agents/executor/`)
   - Executes queries against indexed codebase
   - Retrieves relevant code and generates answers

3. **Flow Identifier Agent** (`src/agents/flow_identifier/`)
   - Extracts structured flows from codebase descriptions
   - Identifies metadata gaps and generates follow-up queries

## Architecture at a glance

```
User runs: discover /path/to/repo
           ↓
    ┌──────────────────┐
    │ Discovery Agent  │
    └────────┬─────────┘
             │
    ┌────────┼────────┐
    │        │        │
    ▼        ▼        ▼
┌────────┐ ┌────────┐ ┌──────────────┐
│Indexer │ │Executor│ │Flow Identifier│
│(FAISS) │ │(Query) │ │   (Claude)    │
└────────┘ └────────┘ └──────────────┘
    │        │              │
    ▼        ▼              ▼
  Vector  Codebase      Structured
  Store   Summary       Flows (MD)
```

## Configuration

Only one required environment variable:

```bash
CLAUDE_API_KEY=sk-ant-...
```

Optional:
```bash
CLAUDE_CHAT_MODEL=claude-sonnet-4-5  # Default
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2  # Default
```

```

Tips:
- ✅ Reuse indexes (don't use `--reindex` unless code changed)
- ✅ Point to specific subdirectories for faster analysis
- ✅ Use custom queries to focus on specific flows

## When to use each command flag

```bash
discover .               # Normal: Use existing index or create new
discover . --reindex     # Code changed: Rebuild index from scratch
```


