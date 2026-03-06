# 🤖 RepoPilot — Deep Context

A **local AI agent** for understanding entire codebases, powered by **Anthropic Claude** + **FAISS**.

Inspired by the [Medium article](https://medium.com/@agastyatodi/building-a-local-ai-agent-for-understanding-entire-codebases-5e8e5f9c7bb0) by Agastya Todi.

---

## Architecture

```
User Query
    │
    ▼
┌─────────────┐
│   Planner   │  ← QueryRouter classifies into METADATA / SEARCH / REASONING / TOOL
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Executor   │  ← Runs the right tool (metadata scan / FAISS search / Claude reasoning)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Verifier   │  ← Validates output, optionally self-critiques
└──────┬──────┘
       │
       ▼
   Rich CLI Answer
```

### Query Types

| Type | Trigger keywords | Tool used |
|------|-----------------|-----------|
| `METADATA` | "how many", "list all", "count" | File-system scan → Claude |
| `SEARCH` | "where is", "find", "locate" | FAISS k-NN → Claude |
| `REASONING` | Everything else | FAISS RAG → Claude |
| `TOOL` | "reindex", "clone" | Side-effect commands |

---

## Setup

### 1. Install [uv](https://github.com/astral-sh/uv)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Sync dependencies

```bash
cd deep-context
uv sync
```

### 3. Configure API key

Copy `.env.example` to `.env` and set your Anthropic API key:

```bash
cp .env.example .env
# Edit .env and set CLAUDE_API_KEY=sk-ant-...
```

Or export directly:

```bash
export CLAUDE_API_KEY=sk-ant-...
```

---

## Usage

### Analyse the current directory

```bash
uv run python -m src.agents.main
```

### Analyse a specific repository

```bash
uv run python -m src.agents.main --repo /path/to/my-project
```

### Force re-scan + re-embed

```bash
uv run python -m src.agents.main --repo /path/to/my-project --reindex
```

### Interactive commands (inside the REPL)

| Command | Effect |
|---------|--------|
| `reindex` | Re-scan and re-embed the current repository |
| `clone <url>` | Clone a GitHub repo and index it |
| `help` | Show help |
| `exit` / `quit` | Quit |

---

## Example questions

- *How many Python files are in this repo?*
- *Where is the authentication logic defined?*
- *Explain the overall architecture of this project.*
- *What does the `collect_files` function do?*
- *Which modules depend on the database layer?*

---

## Project Structure

```
deep-context/
├── src/
│   ├── agents/
│   │   ├── main.py      # CLI entry point & REPL
│   │   ├── planner/     # QueryRouter (METADATA/SEARCH/REASONING/TOOL)
│   │   ├── executor/    # Tool handlers + Claude calls
│   │   ├── indexer/     # File scanner + FAISS indexer
│   │   ├── retrieval/   # Similarity search + context builder
│   │   └── verifier/    # Output validation + self-critique
│   └── common/          # Config + structured logger
├── .env                 # API keys (gitignored)
├── .env.example         # Template for environment variables
└── pyproject.toml
```

> **Index location:** Each analysed repository gets its own FAISS index stored at
> `<repo>/.deep-context-index/` (auto-created, gitignored by default).  
> You can override this globally with the `INDEX_DIR` env var.

---

## Models

| Purpose | Default |
|---------|---------|
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (runs locally, no API needed) |
| Chat / Reasoning | `claude-haiku-4-5` |

Override via `.env`:

```bash
CLAUDE_CHAT_MODEL=claude-opus-4-5
EMBEDDING_MODEL=sentence-transformers/all-mpnet-base-v2
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CLAUDE_API_KEY` | ✅ | — | Your Anthropic/Claude API key |
| `CLAUDE_CHAT_MODEL` | ❌ | `claude-haiku-4-5` | Claude model for chat/reasoning |
| `EMBEDDING_MODEL` | ❌ | `all-MiniLM-L6-v2` | HuggingFace sentence-transformer model |
| `INDEX_DIR` | ❌ | `<repo>/.deep-context-index` | Override FAISS index storage path |

---

## Playwright MCP & Google SSO Setup (Action Agent)

In order to test the Action Agent on websites that require Google Single Sign-On (SSO) securely and easily without wiping your session cookies, Playwright MCP now supports connecting directly to your active browser via a Chrome Extension!

### 1. Install the Chrome Extension
1. Install the [Playwright MCP Bridge](https://chromewebstore.google.com/detail/playwright-mcp-bridge/mmlmfjhmonkocbjadbfplnigmagldckm) directly from the official Chrome Web Store on the browser you want to use.

### 2. Configure Authentication & the MCP Tool
The Chrome Extension will display a token you must use to authenticate. Open your `.env` file and add it:

```bash
PLAYWRIGHT_MCP_EXTENSION_TOKEN=your_token_from_extension_here
```

Ensure your `task_executor` (`tools.py`) sets the `--extension` flag. The token will be automatically inherited by the Playwright MCP server when `run_action_agent.py` loads your `.env` file!

```python
server_params = StdioServerParameters(
    command="npx",
    args=[
        "-y", "@playwright/mcp", 
        "--extension"
    ]
)
```

### 3. Run the Agent
1. Have your Chrome browser open (you can already be logged into your sites, GitHub, Google, etc.).
2. Run your action agent:

```bash
python src/agents/action/run_action_agent.py
```

Playwright MCP will magically connect to your open browser tab using the MCP bridge extension. You will literally see it interact with your already-logged-in session right in front of your eyes!
