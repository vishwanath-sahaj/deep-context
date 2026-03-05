# Discovery Agent

## Overview

The Discovery Agent is an orchestration layer that combines the **Codebase Agent** (Indexer, Retrieval, Executor) and **Flow Identifier Agent** to automatically extract critical user flows from frontend repositories. It produces structured markdown documentation with rich metadata suitable for automated testing tools like Playwright.

## Purpose

When analyzing a frontend codebase, you want to understand:
- What are the critical user journeys? (login, checkout, profile management, etc.)
- What UI elements are involved? (buttons, forms, inputs)
- What metadata is needed for automation? (selectors, labels, test IDs)

The Discovery Agent automates this entire process by:
1. **Indexing** the repository (if not already indexed)
2. **Exploring** the codebase with strategic queries
3. **Identifying** critical user flows
4. **Refining** metadata gaps iteratively
5. **Producing** structured markdown with all necessary details

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                    Discovery Agent                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │   Indexer    │  │   Executor   │  │ Flow Identifier │  │
│  │  (FAISS)     │→ │  (Queries)   │→ │    (Claude)     │  │
│  └──────────────┘  └──────────────┘  └─────────────────┘  │
│         ↓                 ↓                    ↓            │
│  Vector Store      Codebase Summary      Flow Markdown     │
└─────────────────────────────────────────────────────────────┘
```

### Component Dependencies

#### 1. **Indexer Agent** (`src/agents/indexer/`)
- **Purpose**: Creates FAISS vector index of the repository
- **Input**: Repository path
- **Output**: Vector store with embedded code chunks
- **Used by**: Discovery Agent for ensuring repo is searchable
- **Key Function**: `index_repository(repo_path, force=False)`

#### 2. **Executor Agent** (`src/agents/executor/`)
- **Purpose**: Executes queries against the indexed codebase
- **Input**: Natural language query + QueryType
- **Output**: Comprehensive answer with code references
- **Used by**: Discovery Agent for codebase exploration queries
- **Key Method**: `executor.run(query, QueryType.REASONING)`
- **Query Types**: 
  - `REASONING`: Deep analysis with multi-hop retrieval
  - `FACTUAL`: Quick fact retrieval
  - `CODE_SEARCH`: Specific code pattern search

#### 3. **Flow Identifier Agent** (`src/agents/flow_identifier/`)
- **Purpose**: Extracts user flows from codebase descriptions
- **Input**: Codebase summary (markdown text)
- **Output**: `FlowIdentificationResult` with:
  - `flows_markdown`: Structured flows with metadata
  - `followup_queries`: List of questions to fill metadata gaps
  - `metadata_gaps`: Specific missing information
- **Used by**: Discovery Agent for flow extraction and refinement
- **Key Methods**:
  - `identify_flows(codebase_summary)`: Initial extraction
  - `refine_with_additional_context(flows, context)`: Iterative refinement

#### 4. **Retrieval System** (`src/agents/retrieval/`)
- **Purpose**: Semantic search and code retrieval from vector store
- **Input**: Query string + vector store
- **Output**: Relevant code chunks ranked by similarity
- **Used by**: Executor Agent internally
- **Key Features**:
  - Semantic similarity search (top-k retrieval)
  - Code deduplication
  - Chunk context assembly

## Discovery Process Flow

### Step 1: Indexing
```python
# Discovery Agent checks for existing index
index_path = repo_path / ".deep-context-index" / "index.faiss"

if force_reindex:
    # Rebuild from scratch
    vector_store = index_repository(repo_path, force=True)
elif index_path.exists():
    # Load existing index (fast)
    vector_store = FAISS.load_local(index_path, embeddings)
else:
    # Create new index (first time)
    vector_store = index_repository(repo_path, force=False)
```

**What happens**: The Indexer walks the repository, chunks code files, embeds them using HuggingFace transformers, and stores vectors in FAISS.

### Step 2: Exploration
```python
# 5 strategic queries sent to Executor
queries = [
    "List all pages, routes, and their file paths...",
    "Identify all form components including input fields...",
    "Where is user authentication implemented?...",
    "Find all button and link elements...",
    "Identify critical user interactions like checkout...",
]

for query in queries:
    response = executor.run(query, QueryType.REASONING)
    summaries.append(response)

codebase_summary = "\n---\n".join(summaries)
```

**What happens**: The Executor uses Retrieval to find relevant code chunks, then sends them to Claude along with the query to generate comprehensive answers.

### Step 3: Flow Identification
```python
# Flow Identifier extracts structured flows
result = flow_agent.identify_flows(codebase_summary)

# Returns:
# - flows_markdown: "## Flow 1: Login\n### Step 1: FILL email..."
# - followup_queries: ["What is the data-testid for login button?"]
# - metadata_gaps: [MetadataGap(element="login button", missing=["testid"])]
```

**What happens**: Claude analyzes the codebase summary and produces structured markdown flows following a specific format with element metadata.

### Step 4: Refinement (if needed)
```python
if result.followup_queries:
    for query in result.followup_queries[:5]:  # Max 5 refinements
        # Query codebase for missing details
        additional_context = executor.run(query, QueryType.REASONING)
        
        # Update flows with new context
        flows_markdown = flow_agent.refine_with_additional_context(
            flows_markdown, 
            additional_context
        )
```

**What happens**: If metadata gaps exist (e.g., missing test IDs), the Discovery Agent queries the codebase again with specific questions, then asks Flow Identifier to update the flows.

## File Structure

```text
src/agents/discovery/
├── __init__.py          # Public API exports
├── agent.py             # Main DiscoveryAgent class
├── types.py             # DiscoveryResult, ExplorationQuery dataclasses
├── prompts.py           # Strategic exploration queries
└── README.md            # This file
```

### Key Classes

#### `DiscoveryAgent`
```python
class DiscoveryAgent:
    def __init__(
        self, 
        repo_path: Path, 
        vector_store=None,
        auto_index: bool = True, 
        force_reindex: bool = False
    ):
        """Initialize with automatic indexing."""
        
    def discover_flows(
        self, 
        initial_query: Optional[str] = None
    ) -> DiscoveryResult:
        """Main entry point: discovers flows end-to-end."""
```

**Key Methods**:
- `_ensure_indexed(force)`: Handles index creation/loading
- `_explore_codebase(custom_query)`: Runs strategic queries via Executor
- `_refine_flows(initial_result, summary)`: Iterative metadata improvement
- `_extract_sources(summary)`: Parses file paths from responses
- `_count_flows(markdown)`: Counts "## Flow N:" patterns

#### `DiscoveryResult`
```python
@dataclass
class DiscoveryResult:
    flows_markdown: str              # Primary output
    codebase_summary: str            # Exploration responses
    sources: List[str]               # Files analyzed
    followup_queries_used: List[str] # Refinement queries
    is_complete: bool                # Whether gaps remain
    timestamp: datetime              # When discovery ran
    num_flows: int                   # Total flows found
    num_refinement_iterations: int   # Refinement passes
```

#### `ExplorationQuery`
```python
@dataclass
class ExplorationQuery:
    query: str      # "List all pages, routes, and their file paths..."
    purpose: str    # "Understand application structure and navigation"
    priority: int   # 1 (highest) to N (lowest)
```

## Output Format

The Discovery Agent produces markdown in this structure:

```markdown
# Critical User Flows Analysis

## Flow 1: User Login (CRITICAL)
**Description:** User authenticates with email and password

### Step 1: NAVIGATE to login page
- **URL**: `/login`
- **Expected Outcome**: Login form is displayed

### Step 2: FILL email input
**Element Metadata:**
- **Role**: textbox
- **Accessible Name**: "Email"
- **Type**: email
- **Placeholder**: "Enter your email"
- **Label**: "Email Address"
- **Test ID**: email-input
- **Context**: Login form
- **Additional**: required attribute

**Expected Outcome**: Email field populated
**Source**: src/components/LoginForm.tsx:45

### Step 3: FILL password input
**Element Metadata:**
- **Role**: textbox
- **Accessible Name**: "Password"
- **Type**: password
...

### Step 4: CLICK login button
**Element Metadata:**
- **Role**: button
- **Accessible Name**: "Log In"
- **Test ID**: login-submit-btn
...

**Expected Outcome**: User redirected to dashboard
**Source**: src/components/LoginForm.tsx:78

---

## Flow 2: Product Search
...
```

This format is:
- ✅ **Human-readable**: Clear markdown structure
- ✅ **LLM-consumable**: Structured for parsing by Action Agent
- ✅ **Automation-ready**: Rich metadata for Playwright selectors
- ✅ **Source-traceable**: File references for verification

## Usage

### From REPL (Interactive)
```bash
uv run python -m src.agents.main

> discover .                        # Discover flows in current repo
> discover /path/to/frontend        # Discover flows in specific path
> discover . --reindex              # Force re-index before discovery
```

### Programmatic Usage
```python
from pathlib import Path
from src.agents.discovery import DiscoveryAgent

# Initialize
agent = DiscoveryAgent(
    repo_path=Path("./my-frontend-app"),
    auto_index=True,
    force_reindex=False
)

# Discover flows
result = agent.discover_flows()

# Access results
print(f"Found {result.num_flows} flows")
print(f"Analyzed {len(result.sources)} files")
print(result.flows_markdown)
```

### Custom Exploration Query
```python
# Instead of default 5 queries, use a custom one
result = agent.discover_flows(
    initial_query="Focus on the checkout and payment flows only"
)
```

## Configuration

### Environment Variables
```bash
# Required
CLAUDE_API_KEY=sk-ant-...

# Optional (has defaults)
CLAUDE_CHAT_MODEL=claude-sonnet-4-5
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Tunable Parameters

**In `agent.py`**:
```python
# Number of initial exploration queries (default: 5)
queries = get_exploration_queries(max_queries=5)

# Max refinement queries per iteration (default: 5)
max_queries = min(len(followup_queries), 5)
```

**In `prompts.py`**:
```python
# Customize exploration queries
EXPLORATION_QUERIES = [
    ExplorationQuery(
        query="Your custom query...",
        purpose="What you want to find",
        priority=1  # Lower = higher priority
    ),
    ...
]
```

## Integration with Main CLI

The Discovery Agent is integrated into `main.py` via the `_handle_discover_command()` function:

```python
# In REPL loop
if query.lower().startswith("discover"):
    _handle_discover_command(query)
    continue
```

**Command Parser**:
- Extracts path from `discover <path>`
- Detects `--reindex` or `-r` flag
- Validates path exists and is a directory
- Initializes `DiscoveryAgent` with appropriate settings
- Displays results in Rich panels


## Error Handling

### Common Issues

**No index found**:
```
⚠️  No index found. Indexing repository...
✓ Repository indexed successfully
```
→ Automatic: Agent creates index on first run

**Path not found**:
```
❌ Path not found: /nonexistent/path
```
→ User error: Check path spelling

**Missing API key**:
```
❌ CLAUDE_API_KEY not set in environment
```
→ Configuration error: Add key to `.env` file

**Discovery failed**:
```
❌ Discovery failed: <error message>
```
→ Logged with full stack trace for debugging

## Dependencies

The Discovery Agent depends on these components:

```python
# Internal dependencies
from src.agents.executor.agent import Executor, QueryType
from src.agents.indexer.agent import index_repository
from src.agents.flow_identifier import FlowIdentifierAgent, FlowIdentificationResult

# External dependencies
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from rich.console import Console
from rich.progress import Progress
```

All dependencies are specified in `pyproject.toml`.

## Testing

### Manual Testing
```bash
# Test on current repository
uv run python test_discovery_agent.py

# Test with specific repo
uv run python -c "
from pathlib import Path
from src.agents.discovery import DiscoveryAgent

agent = DiscoveryAgent(Path('./your-repo'))
result = agent.discover_flows()
print(result.flows_markdown)
"
```

### Import Testing
```bash
# Verify all imports work
uv run python -c "from src.agents.discovery import *; print('✓ OK')"
```

### Syntax Checking
```bash
python3 -m py_compile src/agents/discovery/*.py
```

## Future Enhancements

Potential improvements for the Discovery Agent:

1. **Parallel Queries**: Execute exploration queries concurrently
2. **Incremental Discovery**: Update flows when code changes
3. **Flow Validation**: Verify flows work on live app (via Playwright)
4. **Custom Templates**: User-defined flow output formats
5. **Multi-language Support**: Extend beyond frontend (mobile apps, APIs)
6. **Caching**: Cache exploration results to speed up refinement
7. **Interactive Mode**: Let user guide exploration with follow-up questions
8. **Export Formats**: JSON, YAML, Playwright test code generation

## Related Documentation

- **Flow Identifier Agent**: `src/agents/flow_identifier/README.md` - How flows are extracted
- **Executor Agent**: `src/agents/executor/README.md` - Query execution logic
- **Indexer Agent**: `src/agents/indexer/README.md` - FAISS indexing process
- **Main CLI**: `src/agents/main.py` - REPL integration

## Example Session

```bash
$ uv run python -m src.agents.main

██████╗ ███████╗██████╗  ██████╗ ██████╗ ██╗██╗      ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██╔═══██╗██╔══██╗██║██║     ██╔═══██╗╚══██╔══╝
██████╔╝█████╗  ██████╔╝██║   ██║██████╔╝██║██║     ██║   ██║   ██║   
██╔══██╗██╔══╝  ██╔═══╝ ██║   ██║██╔═══╝ ██║██║     ██║   ██║   ██║   
██║  ██║███████╗██║     ╚██████╔╝██║     ██║███████╗╚██████╔╝   ██║   
╚═╝  ╚═╝╚══════╝╚═╝      ╚═════╝ ╚═╝     ╚═╝╚══════╝ ╚═════╝    ╚═╝   

⚙️  Configuration
Repository: /home/user/my-frontend
Embedding model: sentence-transformers/all-MiniLM-L6-v2
Chat model: claude-sonnet-4-5

✅ Index ready. Ask anything about the codebase.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You: discover .

🔍 Discovering flows in: /home/user/my-frontend

✓ Using existing index

📋 Step 1/3: Exploring codebase...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 5/5

🔍 Step 2/3: Identifying flows...

⚠️  Found 3 metadata gaps. Refining...

🔧 Step 3/3: Refining metadata...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 3/3

✓ Refined 3 metadata gaps

┌─────────────────────────────────────────────────────────────┐
│           🎯 Critical User Flows (3 flows)                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ## Flow 1: User Authentication (CRITICAL)                   │
│ **Description:** User logs in with credentials              │
│ ...                                                         │
└─────────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────────
✓ Analyzed 12 source files
✓ Refined metadata with 3 queries
✓ Completion: 100%
────────────────────────────────────────────────────────────────
```

## Summary

The Discovery Agent is a high-level orchestrator that:
- **Abstracts complexity**: User doesn't need to know about indexing, retrieval, or prompting
- **Automates discovery**: End-to-end flow extraction with one command
- **Produces actionable output**: Structured markdown ready for automation tools
- **Integrates seamlessly**: Works within existing RepoPilot CLI

It leverages the strengths of each underlying component:
- **Indexer** for fast semantic search
- **Executor** for intelligent query answering
- **Flow Identifier** for structured extraction

This makes it easy to understand any frontend codebase's user journeys without manual code exploration.
