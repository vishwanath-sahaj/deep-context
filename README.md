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
