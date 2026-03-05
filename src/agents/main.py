"""
RepoPilot — main CLI entry point.

Usage:
    uv run python -m src.agents.main [--repo <path>] [--reindex]
    uv run python -m src.agents.main --help
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agents.executor.agent import Executor
from agents.indexer.agent import index_repository
from agents.planner.agent import QueryRouter
from agents.verifier.agent import verify
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.spinner import Spinner
from rich.status import Status
from rich.text import Text

from src.common.config import config
from src.common.logger import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
console = Console()


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

BANNER = """
██████╗ ███████╗██████╗  ██████╗ ██████╗ ██╗██╗      ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██╔═══██╗██╔══██╗██║██║     ██╔═══██╗╚══██╔══╝
██████╔╝█████╗  ██████╔╝██║   ██║██████╔╝██║██║     ██║   ██║   ██║   
██╔══██╗██╔══╝  ██╔═══╝ ██║   ██║██╔═══╝ ██║██║     ██║   ██║   ██║   
██║  ██║███████╗██║     ╚██████╔╝██║     ██║███████╗╚██████╔╝   ██║   
╚═╝  ╚═╝╚══════╝╚═╝      ╚═════╝ ╚═╝     ╚═╝╚══════╝ ╚═════╝    ╚═╝   
"""

HELP_TEXT = """\
**Commands:**
- Type any question about the codebase to get an answer.
- `reindex`          — Re-scan and re-embed the repository.
- `clone <url>`      — Clone a GitHub repo and index it.
- `help`             — Show this help.
- `exit` / `quit`    — Exit RepoPilot.

**Query examples:**
- *How many Python files are in this repo?*
- *Where is the authentication logic defined?*
- *Explain the overall architecture of this project.*
- *What does the `collect_files` function do?*
"""


def _print_banner() -> None:
    console.print(
        Panel(
            Text(BANNER, style="bold cyan", justify="center"),
            subtitle="[dim]Powered by Claude + FAISS[/dim]",
            border_style="bright_blue",
            box=box.DOUBLE_EDGE,
        )
    )


def _print_help() -> None:
    console.print(
        Panel(
            Markdown(HELP_TEXT),
            title="[bold yellow]📖 Help[/bold yellow]",
            border_style="yellow",
        )
    )


# ---------------------------------------------------------------------------
# Core agent loop
# ---------------------------------------------------------------------------

def run_agent(repo_path: Path, reindex: bool = False) -> None:
    config.validate()

    _print_banner()

    console.print(
        Panel(
            f"[bold green]Repository:[/bold green] {repo_path}\n"
            f"[bold green]Embedding model:[/bold green] {config.EMBEDDING_MODEL}\n"
            f"[bold green]Chat model:[/bold green] {config.CLAUDE_CHAT_MODEL}",
            title="[bold]⚙️  Configuration[/bold]",
            border_style="green",
        )
    )

    # Index / load
    with Status(
        "[bold cyan]🔍 Indexing repository…[/bold cyan]",
        spinner="dots",
        console=console,
    ):
        try:
            vector_store = index_repository(repo_path, force=reindex)
        except Exception as exc:
            console.print(f"[bold red]❌ Indexing failed:[/bold red] {exc}")
            sys.exit(1)

    console.print(
        "[bold green]✅ Index ready.[/bold green] Ask anything about the codebase.\n"
    )
    _print_help()

    router = QueryRouter()
    executor = Executor(repo_path=repo_path, vector_store=vector_store)

    # Main REPL
    while True:
        console.print(Rule(style="dim"))
        try:
            query = Prompt.ask("[bold bright_blue]You[/bold bright_blue]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not query:
            continue

        if query.lower() in {"exit", "quit", "q"}:
            console.print("[dim]Goodbye! 👋[/dim]")
            break

        if query.lower() == "help":
            _print_help()
            continue

        # Classify → Execute → Verify
        query_type = router.classify(query)
        console.print(
            f"[dim]→ QueryType: [bold]{query_type.name}[/bold][/dim]"
        )

        with Status(
            "[bold cyan]🤖 Thinking…[/bold cyan]",
            spinner="arc",
            console=console,
        ):
            raw_answer = executor.run(query, query_type)
            # Re-expose updated vector store if tool changed it
            verified_answer = verify(
                raw_answer, query, auto_critique=False
            )

        console.print(
            Panel(
                Markdown(verified_answer),
                title="[bold magenta]🤖 RepoPilot[/bold magenta]",
                border_style="magenta",
                padding=(1, 2),
            )
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RepoPilot — AI agent for understanding codebases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run python -m src.agents.main\n"
            "  uv run python -m src.agents.main --repo /path/to/my-project\n"
            "  uv run python -m src.agents.main --repo . --reindex\n"
        ),
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path("."),
        help="Path to the repository to analyse (default: current directory)",
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Force re-scanning and re-embedding (ignores existing index)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    repo_path = args.repo.expanduser().resolve()

    if not repo_path.is_dir():
        console.print(f"[bold red]❌ Path does not exist:[/bold red] {repo_path}")
        sys.exit(1)

    run_agent(repo_path=repo_path, reindex=args.reindex)


if __name__ == "__main__":
    main()
