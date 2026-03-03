# 🤖 RepoPilot — Deep Context

A **local AI agent** for understanding entire codebases, powered by **OpenAI GPT** and **FAISS**.

Inspired by the [Medium article](https://medium.com/@agastyatodi/building-a-local-ai-agent-for-understanding-entire-codebases-5e8e5f9c7bb0) by Agastya Todi, re-implemented with OpenAI instead of Ollama.

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
│  Executor   │  ← Runs the right tool (metadata scan / FAISS search / GPT reasoning)
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
| `METADATA` | "how many", "list all", "count" | File-system scan → GPT |
| `SEARCH` | "where is", "find", "locate" | FAISS k-NN → GPT |
| `REASONING` | Everything else | FAISS RAG → GPT |
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

Copy `.env.example` to `.env` and set your key:

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-...
```

Or export directly:

```bash
export OPENAI_API_KEY=sk-...
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
uv run python -m src.agents.main --repo . --reindex
```

### Interactive commands (inside the REPL)

| Command | Effect |
|---------|--------|
| `reindex` | Re-scan and re-embed the repository |
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
│   ├── agents/      # CLI entry point (main.py)
│   ├── common/      # Config + logger
│   ├── indexer/     # File scanner + FAISS indexer
│   ├── retrieval/   # Similarity search + context builder
│   ├── planner/     # QueryRouter (METADATA/SEARCH/REASONING/TOOL)
│   ├── executor/    # Tool handlers + OpenAI calls
│   └── verifier/    # Output validation + self-critique
├── index/           # Persisted FAISS index (auto-created)
├── .env             # API keys (gitignored)
└── pyproject.toml
```

---

## Models used

| Purpose | Default model |
|---------|--------------|
| Embeddings | `text-embedding-3-small` |
| Chat / Reasoning | `gpt-4o-mini` |

Change via `.env`:

```bash
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_CHAT_MODEL=gpt-4o
```
