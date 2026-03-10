#!/usr/bin/env python3
"""CLI runner for the Orchestrator Agent."""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from dotenv import load_dotenv
load_dotenv()

from src.agents.orchestrator import OrchestratorAgent, orchestrate


async def main():
    """Run the orchestrator agent from command line."""
    parser = argparse.ArgumentParser(
        description="Orchestrator Agent - Manages codebase analysis and UI automation pipeline"
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=".",
        help="Path to repository to analyze (default: current directory)"
    )
    parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="Target URL to execute flows against"
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Initial query to focus the discovery (optional)"
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="Maximum LLM iterations (default: 20)"
    )
    
    args = parser.parse_args()
    
    # Resolve repo path
    repo_path = Path(args.repo).resolve()
    if not repo_path.exists():
        print(f"Error: Repository path does not exist: {repo_path}")
        sys.exit(1)
    
    # Run orchestrator
    agent = OrchestratorAgent()
    result = await agent.run(
        repo_path=str(repo_path),
        target_url=args.url,
        initial_query=args.query,
        max_iterations=args.max_iterations
    )
    
    # Exit with appropriate code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    asyncio.run(main())
