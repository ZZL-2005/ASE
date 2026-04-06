#!/usr/bin/env python3
"""Stop ASE experiment environment."""

from orchestrator.orchestrate import ASEOrchestrator
from loguru import logger


def main():
    """Stop all ASE services."""
    orchestrator = ASEOrchestrator()
    orchestrator.stop_all_services()
    logger.info("ASE environment stopped")


if __name__ == "__main__":
    main()
