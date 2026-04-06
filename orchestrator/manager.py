"""Unified sandbox orchestrator."""

import asyncio
from typing import Dict, List, Optional
from loguru import logger
import docker
from pathlib import Path


class SandboxManager:
    """Manage all sandbox containers."""

    def __init__(self, project_name: str = "ase"):
        self.project_name = project_name
        self.client = docker.from_env()
        self.containers: Dict[str, docker.models.containers.Container] = {}
        self.network_name = f"{project_name}_network"

    def create_network(self):
        """Create Docker network for sandboxes."""
        try:
            network = self.client.networks.get(self.network_name)
            logger.info(f"Network {self.network_name} already exists")
            return network
        except docker.errors.NotFound:
            network = self.client.networks.create(
                self.network_name,
                driver="bridge"
            )
            logger.info(f"Created network: {self.network_name}")
            return network

    def start_service(self, service_name: str, image: str, **kwargs):
        """Start a service container."""
        container_name = f"{self.project_name}_{service_name}"

        try:
            container = self.client.containers.get(container_name)
            if container.status != "running":
                container.start()
                logger.info(f"Started existing container: {container_name}")
            else:
                logger.info(f"Container already running: {container_name}")
            self.containers[service_name] = container
            return container
        except docker.errors.NotFound:
            container = self.client.containers.run(
                image,
                name=container_name,
                network=self.network_name,
                detach=True,
                **kwargs
            )
            logger.info(f"Created and started: {container_name}")
            self.containers[service_name] = container
            return container

    def stop_service(self, service_name: str):
        """Stop a service container."""
        if service_name in self.containers:
            container = self.containers[service_name]
            container.stop()
            logger.info(f"Stopped: {service_name}")

    def remove_service(self, service_name: str):
        """Remove a service container."""
        if service_name in self.containers:
            container = self.containers[service_name]
            container.stop()
            container.remove()
            del self.containers[service_name]
            logger.info(f"Removed: {service_name}")

    def stop_all(self):
        """Stop all managed containers."""
        for name in list(self.containers.keys()):
            self.stop_service(name)

    def remove_all(self):
        """Remove all managed containers."""
        for name in list(self.containers.keys()):
            self.remove_service(name)

    def get_container_status(self, service_name: str) -> Optional[str]:
        """Get container status."""
        if service_name in self.containers:
            container = self.containers[service_name]
            container.reload()
            return container.status
        return None

    def list_services(self) -> List[Dict]:
        """List all managed services."""
        services = []
        for name, container in self.containers.items():
            container.reload()
            services.append({
                "name": name,
                "status": container.status,
                "id": container.id[:12]
            })
        return services

