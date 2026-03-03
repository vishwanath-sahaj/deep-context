"""Configuration management for deep-context."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (walk up until we find it)
_root = Path(__file__).resolve().parents[2]
load_dotenv(_root / ".env")


class Config:
    """Central configuration object."""

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_EMBEDDING_MODEL: str = os.getenv(
        "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
    )
    OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

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
        if not cls.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Please set it in your .env file or environment."
            )


config = Config()
