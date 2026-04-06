"""Orchestrate all ASE services."""

import subprocess
import time
from pathlib import Path
from loguru import logger
from orchestrator.manager import SandboxManager


class ASEOrchestrator:
    """Orchestrate all ASE sandbox services.

    Uses docker compose as the primary deployment method to stay consistent
    with docker-compose.yml, with SandboxManager as a fallback for
    programmatic container management.
    """

    def __init__(self, compose_file: str = None):
        self.manager = SandboxManager(project_name="ase")
        if compose_file is None:
            compose_file = str(Path(__file__).resolve().parent.parent / "docker-compose.yml")
        self.compose_file = compose_file

    def start_all_services(self):
        """Start all required services via docker compose."""
        logger.info("Starting ASE services via docker compose...")
        result = subprocess.run(
            ["docker", "compose", "-f", self.compose_file, "up", "-d"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.error(f"docker compose up failed: {result.stderr}")
            raise RuntimeError(result.stderr)
        logger.info("All services started")

    def stop_all_services(self):
        """Stop all services via docker compose."""
        logger.info("Stopping all services...")
        result = subprocess.run(
            ["docker", "compose", "-f", self.compose_file, "down"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            logger.error(f"docker compose down failed: {result.stderr}")

    def status(self):
        """Show status of all services."""
        result = subprocess.run(
            ["docker", "compose", "-f", self.compose_file, "ps", "--format", "json"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            import json
            services = []
            for line in result.stdout.strip().splitlines():
                try:
                    svc = json.loads(line)
                    name = svc.get("Name", svc.get("name", "unknown"))
                    state = svc.get("State", svc.get("state", "unknown"))
                    logger.info(f"{name}: {state}")
                    services.append({"name": name, "status": state})
                except json.JSONDecodeError:
                    pass
            return services
        else:
            # Fallback to plain text
            result = subprocess.run(
                ["docker", "compose", "-f", self.compose_file, "ps"],
                capture_output=True, text=True
            )
            logger.info(result.stdout)
            return []

    def restart_service(self, service_name: str):
        """Restart a single service."""
        subprocess.run(
            ["docker", "compose", "-f", self.compose_file, "restart", service_name],
            capture_output=True, text=True
        )
        logger.info(f"Restarted {service_name}")


if __name__ == "__main__":
    orchestrator = ASEOrchestrator()
    orchestrator.start_all_services()
    orchestrator.status()
