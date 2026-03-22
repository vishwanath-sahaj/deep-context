"""Discovery Agent: Orchestrates codebase exploration and flow identification."""

from __future__ import annotations
import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from rich.console import Console
from rich.status import Status
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.common.logger import get_logger
from src.agents.executor.agent import Executor, QueryType
from src.agents.indexer.agent import index_repository
from src.agents.flow_identifier import FlowIdentifierAgent, FlowIdentificationResult
from .types import DiscoveryResult, ExplorationQuery
from .prompts import get_exploration_queries

logger = get_logger(__name__)
console = Console()


class DiscoveryAgent:
    """
    Orchestrates codebase exploration and flow identification.

    The Discovery Agent:
    1. Ensures repository is indexed
    2. Queries codebase for UI components, forms, routes
    3. Extracts critical user flows with rich metadata
    4. Iteratively refines flows by filling metadata gaps
    5. (Optional) Executes flows via Action Agent and documents them via Scribe Agent
    """

    def __init__(self, repo_path: Path, vector_store=None, auto_index: bool = True, force_reindex: bool = False):
        """
        Initialize Discovery Agent.

        Args:
            repo_path: Path to repository to analyze
            vector_store: Pre-loaded FAISS vector store (optional)
            auto_index: Whether to automatically index if needed
            force_reindex: Force re-indexing even if index exists
        """
        self.repo_path = Path(repo_path)
        self.auto_index = auto_index
        self.force_reindex = force_reindex

        # Ensure repo is indexed
        if vector_store is None and auto_index:
            vector_store = self._ensure_indexed(force=force_reindex)

        # Initialize sub-agents
        self.executor = Executor(repo_path=self.repo_path, vector_store=vector_store)
        self.flow_agent = FlowIdentifierAgent()

        logger.info("discovery_agent_initialized", repo=str(self.repo_path), force_reindex=force_reindex)

    def discover_flows(self, initial_query: Optional[str] = None) -> DiscoveryResult:
        """
        Main entry point: Discover critical user flows.

        Args:
            initial_query: Optional custom starting query

        Returns:
            DiscoveryResult with flows, metadata, and context
        """
        start_time = time.time()
        logger.info("discovery_started", repo=str(self.repo_path))

        try:
            # Step 1: Explore codebase
            console.print("\n[bold cyan]Step 1/3: Exploring codebase...[/bold cyan]")
            codebase_summary = self._explore_codebase(initial_query)
            logger.debug("codebase_summary_length", chars=len(codebase_summary))

            # Step 2: Extract flows
            console.print("[bold cyan]Step 2/3: Identifying flows...[/bold cyan]")
            initial_result = self.flow_agent.identify_flows(codebase_summary)

            # Step 3: Refine if needed
            if initial_result.followup_queries and len(initial_result.followup_queries) > 0:
                console.print(
                    f"[bold yellow]Found {len(initial_result.followup_queries)} "
                    f"metadata gaps. Refining...[/bold yellow]"
                )
                result = self._refine_flows(initial_result, codebase_summary)
            else:
                console.print("[bold green]All metadata extracted successfully[/bold green]")
                result = DiscoveryResult(
                    flows_markdown=initial_result.flows_markdown,
                    codebase_summary=codebase_summary,
                    sources=self._extract_sources(codebase_summary),
                    is_complete=True,
                    num_flows=self._count_flows(initial_result.flows_markdown)
                )

            elapsed = time.time() - start_time
            logger.info("discovery_completed", duration_sec=round(elapsed, 2))

            return result

        except Exception as exc:
            logger.error("discovery_failed", error=str(exc))
            console.print(f"[bold red]Discovery failed: {exc}[/bold red]")
            raise

    def discover_and_document(
        self,
        target_url: str,
        initial_query: Optional[str] = None,
    ) -> List:
        """
        Full pipeline: Discover flows, execute them in the browser, and generate documentation.

        Args:
            target_url: The live application URL to execute flows against
            initial_query: Optional custom starting query

        Returns:
            List of ScribeOutput objects, one per flow
        """
        from src.agents.scribe import ScribeAgent, FlowExecutionRecord, StepRecord
        from src.agents.scribe.flow_parser import parse_flows_markdown
        from src.agents.action.agent import ActionAgent
        from src.agents.action.tools import set_step_callback

        # Phase 1: Discover flows (reuse existing logic)
        discovery_result = self.discover_flows(initial_query)

        # Phase 2: Parse flows into individual blocks
        parsed_flows = parse_flows_markdown(discovery_result.flows_markdown)
        console.print(
            f"\n[bold cyan]Step 4/5: Executing {len(parsed_flows)} flows in browser...[/bold cyan]"
        )

        # Phase 3: Execute each flow and collect step records
        action_agent = ActionAgent()
        scribe_agent = ScribeAgent()
        scribe_outputs = []

        for i, pflow in enumerate(parsed_flows, 1):
            console.print(
                f"\n[bold yellow]--- Flow {i}/{len(parsed_flows)}: {pflow.name} ({pflow.priority}) ---[/bold yellow]"
            )

            # Set up step record collection via the global callback
            collected_steps: List[StepRecord] = []

            def _collect(record: StepRecord, _steps=collected_steps) -> None:
                _steps.append(record)

            set_step_callback(_collect)

            started_at = datetime.now()
            try:
                result_text = asyncio.run(
                    action_agent.run(instruction=pflow.markdown, url=target_url)
                )
                # ActionAgent.run() may return a list (LangChain content blocks) or a string
                if isinstance(result_text, list):
                    result_text = "\n".join(
                        block.get("text", str(block)) if isinstance(block, dict) else str(block)
                        for block in result_text
                    )
                result_text = str(result_text)
                success = "error" not in result_text.lower()[:100]
            except Exception as exc:
                logger.error("flow_execution_failed", flow=pflow.name, error=str(exc))
                console.print(f"[red]Execution failed for {pflow.name}: {exc}[/red]")
                result_text = f"Execution failed: {exc}"
                success = False
            finally:
                set_step_callback(None)  # Clear callback

            finished_at = datetime.now()

            # Build the execution record
            execution_record = FlowExecutionRecord(
                flow_name=pflow.name,
                flow_markdown=pflow.markdown,
                start_url=target_url,
                steps=collected_steps,
                screenshot_dir=self._extract_screenshot_dir(result_text),
                success=success,
                started_at=started_at,
                finished_at=finished_at,
            )

            # Phase 4: Generate documentation via scribe
            console.print(
                f"[bold cyan]Step 5/5: Generating documentation for {pflow.name}...[/bold cyan]"
            )
            try:
                scribe_output = scribe_agent.generate_documentation(
                    execution_record=execution_record,
                    codebase_summary=discovery_result.codebase_summary,
                )
                scribe_outputs.append(scribe_output)
                console.print(f"[green]Documentation generated for {pflow.name}[/green]")
            except Exception as exc:
                logger.error("scribe_failed", flow=pflow.name, error=str(exc))
                console.print(f"[red]Documentation generation failed for {pflow.name}: {exc}[/red]")

        return scribe_outputs

    def _extract_screenshot_dir(self, result_text: str) -> str:
        """Extract screenshot directory path from task_executor result."""
        import re
        match = re.search(r'Screenshots saved to:\s*(.+)', result_text)
        return match.group(1).strip() if match else ""

    def _ensure_indexed(self, force: bool = False) -> object:
        """
        Ensure repository is indexed, index if needed.

        Args:
            force: Force re-indexing even if index exists

        Returns:
            FAISS vector store
        """
        index_path = self.repo_path / ".deep-context-index"
        faiss_file = index_path / "index.faiss"

        if force and faiss_file.exists():
            console.print("[bold yellow]Force re-indexing repository...[/bold yellow]")
            logger.info("force_reindexing", path=str(self.repo_path))

            with Status("[cyan]Rebuilding FAISS index...", spinner="dots"):
                # Only index src directory to avoid build artifacts
                vector_store = index_repository(self.repo_path, force=True, include_dirs=["src"])

            console.print("[green]Repository re-indexed successfully[/green]")
            return vector_store

        elif faiss_file.exists():
            console.print("[dim]Using existing index[/dim]")
            logger.info("using_existing_index", path=str(index_path))
            from langchain_community.vectorstores import FAISS
            from langchain_huggingface import HuggingFaceEmbeddings
            from src.common.config import config

            embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
            return FAISS.load_local(
                str(index_path),
                embeddings,
                allow_dangerous_deserialization=True
            )
        else:
            console.print("[bold yellow]No index found. Indexing repository...[/bold yellow]")
            logger.info("indexing_repository", path=str(self.repo_path))

            with Status("[cyan]Building FAISS index...", spinner="dots"):
                # Only index src directory to avoid build artifacts
                vector_store = index_repository(self.repo_path, force=False, include_dirs=["src"])

            console.print("[green]Repository indexed successfully[/green]")
            return vector_store

    def _explore_codebase(self, custom_query: Optional[str] = None) -> str:
        """
        Query codebase to build comprehensive summary.

        Args:
            custom_query: Optional single query instead of default exploration

        Returns:
            Combined markdown summary of codebase
        """
        if custom_query:
            queries = [custom_query]
        else:
            queries = get_exploration_queries(max_queries=5)

        summaries = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(
                f"[cyan]Querying codebase ({len(queries)} queries)...",
                total=len(queries)
            )

            for i, query in enumerate(queries, 1):
                logger.debug("codebase_query", query_num=i, query=query[:60])

                # Use REASONING query type for comprehensive answers
                response = self.executor.run(query, QueryType.REASONING)
                summaries.append(f"### Query {i}\n**Q:** {query}\n\n{response}\n")

                progress.update(task, advance=1)

        combined = "\n---\n\n".join(summaries)
        logger.info("codebase_explored", total_chars=len(combined), num_queries=len(queries))

        return combined

    def _refine_flows(
        self,
        initial_result: FlowIdentificationResult,
        codebase_summary: str
    ) -> DiscoveryResult:
        """
        Iteratively refine flows by querying for missing metadata.

        Args:
            initial_result: Result from initial flow extraction
            codebase_summary: Original codebase summary

        Returns:
            DiscoveryResult with refined flows
        """
        console.print("[bold cyan]Step 3/3: Refining metadata...[/bold cyan]")

        refined_flows = initial_result.flows_markdown
        queries_used = []

        # Limit to 1 refinement iteration (as per requirements)
        followup_queries_list = initial_result.followup_queries or []
        max_queries = min(len(followup_queries_list), 5)
        followup_queries = followup_queries_list[:max_queries]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(
                f"[cyan]Refining metadata ({len(followup_queries)} queries)...",
                total=len(followup_queries)
            )

            for query in followup_queries:
                logger.debug("refinement_query", query=query[:60])

                # Query codebase for missing metadata
                additional_context = self.executor.run(query, QueryType.REASONING)
                queries_used.append(query)

                # Refine flows with new context
                refined_flows = self.flow_agent.refine_with_additional_context(
                    refined_flows,
                    additional_context
                )

                progress.update(task, advance=1)

        console.print(f"[green]Refined {len(queries_used)} metadata gaps[/green]")
        logger.info("refinement_completed", queries_used=len(queries_used))

        return DiscoveryResult(
            flows_markdown=refined_flows,
            codebase_summary=codebase_summary,
            sources=self._extract_sources(codebase_summary),
            followup_queries_used=queries_used,
            is_complete=True,
            num_flows=self._count_flows(refined_flows),
            num_refinement_iterations=1
        )

    def _extract_sources(self, codebase_summary: str) -> List[str]:
        """Extract file paths mentioned in codebase summary."""
        import re

        # Match file paths in markdown code blocks and text
        patterns = [
            r'`([a-zA-Z0-9_/.-]+\.[a-zA-Z0-9]+)`',  # `src/file.tsx`
            r'\*\*Source:\*\*\s*`([^`]+)`',          # **Source:** `file`
            r'File:\s*`([^`]+)`',                    # File: `file`
        ]

        sources = set()
        for pattern in patterns:
            matches = re.findall(pattern, codebase_summary)
            sources.update(matches)

        return sorted(list(sources))

    def _count_flows(self, flows_markdown: str) -> int:
        """Count number of flows in markdown."""
        import re
        # Count "## Flow N:" patterns
        matches = re.findall(r'^## Flow \d+:', flows_markdown, re.MULTILINE)
        return len(matches)


# Convenience function for standalone usage
def discover_flows(repo_path: Path) -> DiscoveryResult:
    """
    Convenience function to discover flows in a repository.

    Args:
        repo_path: Path to repository

    Returns:
        DiscoveryResult with flows and metadata
    """
    agent = DiscoveryAgent(repo_path)
    return agent.discover_flows()
