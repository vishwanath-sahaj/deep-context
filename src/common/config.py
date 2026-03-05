"""Configuration management for deep-context."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (walk up until we find it)
_root = Path(__file__).resolve().parents[2]
load_dotenv(_root / ".env")


class Config:
    """Central configuration object."""

    # Anthropic / Claude
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_CHAT_MODEL: str = os.getenv("CLAUDE_CHAT_MODEL", "claude-haiku-4-5")

    # Embeddings — Anthropic has no embedding API; use a local HuggingFace model
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # Paths
    INDEX_DIR: Path = Path(os.getenv("INDEX_DIR", "./index"))

    # Chunking
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # Files to skip
    SKIP_EXTENSIONS: frozenset = frozenset(
        {
            ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
            ".mp4", ".mp3", ".wav", ".avi", ".mov",
            ".zip", ".tar", ".gz", ".bz2", ".rar", ".7z",
            ".exe", ".dll", ".so", ".dylib",
            ".pdf", ".doc", ".docx", ".xls", ".xlsx",
            ".pyc", ".pyo", ".pyd",
            ".lock", ".sum",
        }
    )

    SKIP_DIRS: frozenset = frozenset(
        {
            ".git", "__pycache__", "node_modules", ".venv", "venv", "env",
            "dist", "build", ".eggs", "*.egg-info",
            ".idea", ".vscode", ".pytest_cache", ".mypy_cache",
            "coverage", "htmlcov", ".tox",
        }
    )

    MAX_FILE_SIZE_BYTES: int = 200_000  # 200 KB

    @classmethod
    def validate(cls) -> None:
        if not cls.ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Please set it in your .env file or environment."
            )


config = Config()
