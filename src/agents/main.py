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
from agents.discovery.agent import DiscoveryAgent
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
- `discover <path>`                    — Extract critical user flows from repository.
- `discover <path> --reindex`          — Force re-index before discovering flows.
- `discover <path> --url <url>`        — Discover, execute, and document flows.
- `discover <path> --url <url> --reindex` — Full pipeline with re-indexing.
- `reindex`                            — Re-scan and re-embed the repository.
- `clone <url>`                        — Clone a GitHub repo and index it.
- `help`                               — Show this help.
- `exit` / `quit`                      — Exit RepoPilot.

**Examples:**
- `discover .`                                         — Discover flows in current repo
- `discover /home/user/frontend`                       — Discover flows in specific repo
- `discover . --url https://dev.example.com`           — Full pipeline: discover + execute + document
- `discover . --url https://dev.example.com --reindex` — Re-index then full pipeline
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
            title="[bold yellow]Help[/bold yellow]",
            border_style="yellow",
        )
    )


# ---------------------------------------------------------------------------
# Command Handlers
# ---------------------------------------------------------------------------

def _handle_discover_command(command: str) -> None:
    """Handle 'discover <path> [--reindex] [--url <url>]' command."""
    from pathlib import Path
    from agents.discovery.agent import DiscoveryAgent

    # Parse command
    parts = command.split()
    if len(parts) < 2:
        console.print("[yellow]Usage: discover <path> [--reindex] [--url <url>][/yellow]")
        console.print("[dim]Examples:[/dim]")
        console.print("[dim]  discover /home/user/frontend[/dim]")
        console.print("[dim]  discover . --url https://dev.example.com[/dim]")
        console.print("[dim]  discover . --url https://dev.example.com --reindex[/dim]")
        return

    # Extract path and flags
    target_path_str = parts[1]
    force_reindex = "--reindex" in parts or "-r" in parts

    # Extract --url value
    target_url = None
    for i, part in enumerate(parts):
        if part == "--url" and i + 1 < len(parts):
            target_url = parts[i + 1]
            break

    target_path = Path(target_path_str).expanduser().resolve()

    # Validate path
    if not target_path.exists():
        console.print(f"[red]Path not found: {target_path}[/red]")
        return

    if not target_path.is_dir():
        console.print(f"[red]Not a directory: {target_path}[/red]")
        return

    # Run discovery
    try:
        reindex_msg = " (with re-indexing)" if force_reindex else ""
        url_msg = f" | URL: {target_url}" if target_url else ""
        console.print(f"\n[bold]Discovering flows in:[/bold] [cyan]{target_path}[/cyan]{reindex_msg}{url_msg}\n")

        discovery = DiscoveryAgent(repo_path=target_path, auto_index=True, force_reindex=force_reindex)

        if target_url:
            # Full pipeline: discover + execute + document
            scribe_outputs = discovery.discover_and_document(target_url=target_url)

            if not scribe_outputs:
                console.print("[yellow]No documentation was generated.[/yellow]")
                return

            # Display each flow's documentation
            for output in scribe_outputs:
                console.print("\n")
                console.print(
                    Panel(
                        Markdown(output.documentation_markdown),
                        title=f"[bold green]{output.flow_name}[/bold green]",
                        border_style="green",
                        padding=(1, 2),
                    )
                )

            # Save combined documentation to file
            output_dir = target_path / ".deep-context-docs"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / "flows.md"

            combined = "\n\n---\n\n".join(
                o.documentation_markdown for o in scribe_outputs
            )
            output_file.write_text(combined, encoding="utf-8")

            console.print(f"\n[bold green]Documentation saved to: {output_file}[/bold green]")
            console.print(f"[dim]Generated docs for {len(scribe_outputs)} flows[/dim]")

        else:
            # Discovery only (existing behavior)
            result = discovery.discover_flows()

            # Display results
            console.print("\n")
            console.print(
                Panel(
                    Markdown(result.flows_markdown),
                    title=f"Critical User Flows ({result.num_flows} flows)",
                    border_style="green",
                    padding=(1, 2),
                )
            )

            # Display metadata
            console.print("\n[dim]" + "-" * 80 + "[/dim]")
            console.print(f"[dim]Analyzed {len(result.sources)} source files[/dim]")
            if result.followup_queries_used:
                console.print(
                    f"[dim]Refined metadata with {len(result.followup_queries_used)} queries[/dim]"
                )
            console.print(f"[dim]Completion: {'100%' if result.is_complete else 'Partial'}[/dim]")
            console.print("[dim]" + "-" * 80 + "[/dim]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]Discovery cancelled by user[/yellow]")
    except Exception as exc:
        console.print(f"\n[red]Discovery failed: {exc}[/red]")
        logger.error("discover_command_failed", error=str(exc))


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
            title="[bold]Configuration[/bold]",
            border_style="green",
        )
    )

    # Index / load
    with Status(
        "[bold cyan]Indexing repository...[/bold cyan]",
        spinner="dots",
        console=console,
    ):
        try:
            vector_store = index_repository(repo_path, force=reindex)
        except Exception as exc:
            console.print(f"[bold red]Indexing failed:[/bold red] {exc}")
            sys.exit(1)

    console.print(
        "[bold green]Index ready.[/bold green] Ask anything about the codebase.\n"
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
            console.print("[dim]Goodbye![/dim]")
            break

        if query.lower() == "help":
            _print_help()
            continue

        # NEW: Discover command
        if query.lower().startswith("discover"):
            _handle_discover_command(query)
            continue

        # Classify -> Execute -> Verify
        query_type = router.classify(query)
        console.print(
            f"[dim]-> QueryType: [bold]{query_type.name}[/bold][/dim]"
        )

        with Status(
            "[bold cyan]Thinking...[/bold cyan]",
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
                title="[bold magenta]RepoPilot[/bold magenta]",
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
        console.print(f"[bold red]Path does not exist:[/bold red] {repo_path}")
        sys.exit(1)

    run_agent(repo_path=repo_path, reindex=args.reindex)


if __name__ == "__main__":
    main()
