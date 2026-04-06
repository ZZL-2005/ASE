#!/usr/bin/env python3
"""Start ASE experiment environment."""

import sys
from orchestrator.orchestrate import ASEOrchestrator
from loguru import logger


def main():
    """Start all ASE services."""
    orchestrator = ASEOrchestrator()

    try:
        orchestrator.start_all_services()
        logger.info("ASE environment ready")
        orchestrator.status()
    except Exception as e:
        logger.error(f"Failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
