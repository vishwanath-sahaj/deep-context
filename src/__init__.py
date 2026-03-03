"""
deep-context: A local AI agent for understanding entire codebases using OpenAI + FAISS.

Package structure:
  src/
    agents/         - Agent entry points
    common/         - Shared utilities (logging, config)
    indexer/        - Repository scanning and FAISS indexing
    retrieval/      - Vector search and context retrieval
    planner/        - ReAct query router and planner
    executor/       - Tool executors (metadata, search, reasoning)
    verifier/       - Output validation
"""
