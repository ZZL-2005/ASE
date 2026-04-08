"""Task: a single experiment run with its own sandbox cluster.
ASE/orchestrator/task.py
A Task encapsulates the full lifecycle of one experiment:
  created → starting → running → stopping → stopped

Each Task has:
  - Unique ID and isolated Docker containers (network, ports, volumes)
  - Either interactive (human via web) or simulated (LLM-driven) user mode
  - Trajectory collection from both agent and user sandboxes
  - Status monitoring
"""

import json
import subprocess
import time
import shutil
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

import httpx
from loguru import logger

from orchestrator.port_allocator import PortAllocator
from orchestrator.compose_gen import generate_compose


class TaskState(str, Enum):
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class TaskConfig:
    """Configuration for a Task."""
    name: str = ""
    user_mode: str = "interactive"  # "interactive" or "simulated"
    llm_config: Dict[str, str] = field(default_factory=dict)
    user_script: Optional[str] = None  # Path to user scenario script (simulated mode)
    description: str = ""
    replay_config: Optional[Dict[str, Any]] = None  # Replay mode config


@dataclass
class TaskInfo:
    """Serializable Task metadata."""
    task_id: str
    config: TaskConfig
    state: TaskState
    created_at: str
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None
    ports: Dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None


class Task:
    """A single experiment run with its own sandbox cluster."""

    def __init__(self, task_id: str, config: TaskConfig, task_dir: Path, port_allocator: PortAllocator):
        self.task_id = task_id
        self.config = config
        self.task_dir = task_dir
        self.task_dir.mkdir(parents=True, exist_ok=True)

        self._port_allocator = port_allocator
        self.ports = port_allocator.allocate(task_id)
        self.compose_file: Optional[Path] = None
        self.state = TaskState.CREATED
        self.created_at = datetime.now().isoformat()
        self.started_at: Optional[str] = None
        self.stopped_at: Optional[str] = None
        self.error: Optional[str] = None

        self._save_info()

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self):
        """Start the Task: generate compose, pull up containers, create accounts."""
        self.state = TaskState.STARTING
        self.started_at = datetime.now().isoformat()
        self._save_info()

        try:
            # 1. Build agent image (if not exists)
            self._ensure_agent_image()

            # 2. Generate compose file
            self.compose_file = generate_compose(
                task_id=self.task_id,
                ports=self.ports,
                task_dir=self.task_dir,
                user_mode=self.config.user_mode,
                llm_config=self.config.llm_config,
                replay_config=self.config.replay_config,
            )

            # 3. Start containers
            logger.info(f"[{self.task_id}] Starting containers...")
            result = subprocess.run(
                ["docker", "compose", "-f", str(self.compose_file),
                 "-p", f"ase-{self.task_id}", "up", "-d"],
                capture_output=True, text=True, cwd=str(self.task_dir)
            )
            if result.returncode != 0:
                raise RuntimeError(f"docker compose up failed: {result.stderr}")

            # 4. Wait for services to be ready
            self._wait_for_services()

            # 5. Create Rocket.Chat accounts
            self._setup_rocketchat_accounts()

            # 6. Create email accounts
            self._setup_email_accounts()

            self.state = TaskState.RUNNING
            self._save_info()

            logger.info(f"[{self.task_id}] Task started successfully")
            logger.info(f"[{self.task_id}] Rocket.Chat: http://localhost:{self.ports['rocketchat']}")
            logger.info(f"[{self.task_id}] Web Env: http://localhost:{self.ports['web']}")
            if self.config.user_mode == "interactive":
                logger.info(f"[{self.task_id}] Login as testuser / test_pass_2026")

        except Exception as e:
            self.state = TaskState.ERROR
            self.error = str(e)
            self._save_info()
            logger.error(f"[{self.task_id}] Start failed: {e}")
            raise

    def stop(self):
        """Stop the Task: collect trajectories, stop containers."""
        self.state = TaskState.STOPPING
        self._save_info()

        try:
            logger.info(f"[{self.task_id}] Stopping containers...")
            if self.compose_file and self.compose_file.exists():
                subprocess.run(
                    ["docker", "compose", "-f", str(self.compose_file),
                     "-p", f"ase-{self.task_id}", "down"],
                    capture_output=True, text=True
                )

            self.stopped_at = datetime.now().isoformat()
            self.state = TaskState.STOPPED
            self._save_info()
            self._port_allocator.release(self.task_id)
            logger.info(f"[{self.task_id}] Task stopped")

        except Exception as e:
            self.state = TaskState.ERROR
            self.error = str(e)
            self._save_info()
            logger.error(f"[{self.task_id}] Stop failed: {e}")

    def destroy(self):
        """Stop and remove all data for this Task."""
        self.stop()
        # Remove volumes
        if self.compose_file and self.compose_file.exists():
            subprocess.run(
                ["docker", "compose", "-f", str(self.compose_file),
                 "-p", f"ase-{self.task_id}", "down", "-v"],
                capture_output=True, text=True
            )
        logger.info(f"[{self.task_id}] Task destroyed")

    # ── Status ────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Get Task status including container states."""
        info = {
            "task_id": self.task_id,
            "name": self.config.name,
            "state": self.state.value,
            "user_mode": self.config.user_mode,
            "ports": self.ports,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
        }

        if self.state == TaskState.RUNNING and self.compose_file:
            info["containers"] = self._get_container_states()

        return info

    def _get_container_states(self) -> List[Dict[str, str]]:
        """Query actual container states from Docker."""
        result = subprocess.run(
            ["docker", "compose", "-f", str(self.compose_file),
             "-p", f"ase-{self.task_id}", "ps", "--format", "json"],
            capture_output=True, text=True
        )
        containers = []
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                try:
                    c = json.loads(line)
                    containers.append({
                        "name": c.get("Name", c.get("name", "")),
                        "state": c.get("State", c.get("state", "")),
                        "status": c.get("Status", c.get("status", "")),
                    })
                except json.JSONDecodeError:
                    pass
        return containers

    # ── Trajectories ──────────────────────────────────────────

    def get_trajectories(self) -> Dict[str, List[Path]]:
        """List trajectory files collected from sandboxes."""
        result = {"agent": [], "user": []}
        agent_dir = self.task_dir / "trajectories" / "agent"
        user_dir = self.task_dir / "trajectories" / "user"

        if agent_dir.exists():
            result["agent"] = sorted(agent_dir.glob("*.jsonl"))
        if user_dir.exists():
            result["user"] = sorted(user_dir.glob("*.jsonl"))

        return result

    def get_logs(self, service: str = None, tail: int = 50) -> str:
        """Get container logs for a service or all services."""
        if not self.compose_file or not self.compose_file.exists():
            return ""
        cmd = ["docker", "compose", "-f", str(self.compose_file),
               "-p", f"ase-{self.task_id}", "logs", "--tail", str(tail)]
        if service:
            cmd.append(service)
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout + result.stderr

    # ── Internal ──────────────────────────────────────────────

    def _ensure_agent_image(self):
        """Build agent Docker image if it doesn't exist."""
        ase_root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            ["docker", "images", "-q", "ase-agent"],
            capture_output=True, text=True
        )
        if not result.stdout.strip():
            logger.info(f"[{self.task_id}] Building agent image...")
            subprocess.run(
                ["docker", "build", "-f", str(ase_root / "agent" / "Dockerfile"),
                 "-t", "ase-agent", str(ase_root)],
                capture_output=True, text=True, check=True
            )

    def _wait_for_services(self, timeout: int = 300):
        """Wait for Rocket.Chat to be fully operational.

        Phases:
          1. HTTP reachable (/api/info)
          2. Admin login works
          3. Account creation works (the real readiness gate)

        Phase 3 is critical: after fresh MongoDB replica-set init, the first
        users.create can take 60-120s while MongoDB builds indexes. We keep
        retrying until it succeeds or timeout.
        """
        rc_url = f"http://localhost:{self.ports['rocketchat']}"
        logger.info(f"[{self.task_id}] Waiting for Rocket.Chat at {rc_url}...")
        deadline = time.time() + timeout
        phase = "connect"  # connect → login → create_accounts
        headers = {}

        users_to_create = [
            {"username": "agent", "email": "agent@ase.local",
             "password": "agent_pass_2026", "name": "Agent"},
            {"username": "testuser", "email": "testuser@ase.local",
             "password": "test_pass_2026", "name": "Test User"},
        ]
        users_created = set()

        while time.time() < deadline:
            try:
                if phase == "connect":
                    resp = httpx.get(f"{rc_url}/api/info", timeout=5)
                    if resp.status_code == 200:
                        logger.info(f"[{self.task_id}] Rocket.Chat HTTP ready")
                        phase = "login"

                if phase == "login":
                    resp = httpx.post(
                        f"{rc_url}/api/v1/login",
                        json={"user": "aseadmin", "password": "admin_pass_2026"},
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        auth = resp.json()["data"]
                        headers = {
                            "X-Auth-Token": auth["authToken"],
                            "X-User-Id": auth["userId"],
                        }
                        logger.info(f"[{self.task_id}] Admin login OK, creating accounts...")
                        phase = "create_accounts"

                if phase == "create_accounts":
                    for user in users_to_create:
                        if user["username"] in users_created:
                            continue
                        # Use remaining time as timeout, min 15s
                        remaining = max(15, int(deadline - time.time()))
                        resp = httpx.post(
                            f"{rc_url}/api/v1/users.create",
                            headers=headers, json=user, timeout=remaining,
                        )
                        if resp.status_code == 200:
                            logger.info(f"[{self.task_id}] Created RC user: {user['username']}")
                            users_created.add(user["username"])
                        else:
                            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                            if "already in use" in body.get("error", ""):
                                logger.info(f"[{self.task_id}] RC user {user['username']} already exists")
                                users_created.add(user["username"])
                            else:
                                logger.warning(f"[{self.task_id}] RC user {user['username']}: {resp.text[:120]}")

                    if len(users_created) == len(users_to_create):
                        logger.info(f"[{self.task_id}] All RC accounts ready")
                        return

            except httpx.TimeoutException:
                elapsed = int(time.time() + timeout - deadline + timeout)
                logger.info(f"[{self.task_id}] RC API slow (DB warming up), retrying... ({len(users_created)}/{len(users_to_create)} users done)")
            except Exception as e:
                logger.debug(f"[{self.task_id}] Wait probe failed: {e}")
            time.sleep(3)

        # If we got some but not all users, that's still partially OK
        if users_created:
            logger.warning(f"[{self.task_id}] Timeout but {len(users_created)}/{len(users_to_create)} users created")
        else:
            raise TimeoutError(f"Rocket.Chat not ready after {timeout}s")

    def _setup_rocketchat_accounts(self):
        """No-op: accounts are now created during _wait_for_services."""
        pass

    def _setup_email_accounts(self):
        """Create email accounts in the mail server."""
        container = f"ase-{self.task_id}-mailserver"
        for account, password in [
            ("test@ase.local", "test_pass_2026"),
            ("agent@ase.local", "agent_pass_2026"),
        ]:
            subprocess.run(
                ["docker", "exec", container, "setup", "email", "add", account, password],
                capture_output=True, text=True
            )
            logger.info(f"[{self.task_id}] Created email: {account}")

    def _save_info(self):
        """Persist Task metadata to disk."""
        info = TaskInfo(
            task_id=self.task_id,
            config=self.config,
            state=self.state,
            created_at=self.created_at,
            started_at=self.started_at,
            stopped_at=self.stopped_at,
            ports=self.ports,
            error=self.error,
        )
        info_file = self.task_dir / "task_info.json"
        with open(info_file, "w") as f:
            json.dump(asdict(info), f, indent=2, default=str)

    @classmethod
    def load(cls, task_dir: Path, port_allocator: PortAllocator) -> "Task":
        """Load a Task from its saved metadata."""
        info_file = task_dir / "task_info.json"
        data = json.loads(info_file.read_text())

        config = TaskConfig(**data["config"])
        task = cls.__new__(cls)
        task.task_id = data["task_id"]
        task.config = config
        task.task_dir = task_dir
        task._port_allocator = port_allocator
        task.ports = data.get("ports", {})
        task.state = TaskState(data["state"])
        task.created_at = data["created_at"]
        task.started_at = data.get("started_at")
        task.stopped_at = data.get("stopped_at")
        task.error = data.get("error")
        task.compose_file = task_dir / "docker-compose.yml" if (task_dir / "docker-compose.yml").exists() else None
        return task
