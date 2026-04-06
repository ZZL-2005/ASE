"""TaskManager: manage multiple concurrent Tasks.

Provides a high-level API for creating, starting, stopping, and listing Tasks.
Each Task is stored in tasks/{task_id}/ with its compose file, trajectories,
and metadata.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from orchestrator.port_allocator import PortAllocator
from orchestrator.task import Task, TaskConfig, TaskState


class TaskManager:
    """Manage the lifecycle of multiple experiment Tasks."""

    def __init__(self, tasks_dir: str = None):
        if tasks_dir is None:
            tasks_dir = str(Path(__file__).resolve().parent.parent / "tasks")
        self.tasks_dir = Path(tasks_dir)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

        self._port_allocator = PortAllocator(
            state_file=str(self.tasks_dir / ".port_state.json")
        )
        self._tasks: Dict[str, Task] = {}
        self._next_id = 1

        # Load existing tasks from disk
        self._load_existing_tasks()

    def _load_existing_tasks(self):
        """Load all existing tasks from the tasks directory."""
        for task_dir in sorted(self.tasks_dir.iterdir()):
            if task_dir.is_dir() and (task_dir / "task_info.json").exists():
                try:
                    task = Task.load(task_dir, self._port_allocator)
                    self._tasks[task.task_id] = task
                    # Track highest ID for auto-increment
                    try:
                        num = int(task.task_id.split("-")[-1])
                        if num >= self._next_id:
                            self._next_id = num + 1
                    except ValueError:
                        pass
                except Exception as e:
                    logger.warning(f"Failed to load task from {task_dir}: {e}")

    def _generate_task_id(self) -> str:
        """Generate the next task ID."""
        task_id = f"task-{self._next_id:03d}"
        self._next_id += 1
        return task_id

    # ── Public API ────────────────────────────────────────────

    def create_task(self, config: TaskConfig = None, task_id: str = None) -> Task:
        """Create a new Task (does not start it)."""
        if config is None:
            config = TaskConfig()

        if task_id is None:
            task_id = self._generate_task_id()

        task_dir = self.tasks_dir / task_id
        task = Task(
            task_id=task_id,
            config=config,
            task_dir=task_dir,
            port_allocator=self._port_allocator,
        )
        self._tasks[task_id] = task

        logger.info(f"Created task: {task_id} (mode={config.user_mode})")
        return task

    def start_task(self, task_id: str):
        """Start a Task by ID."""
        task = self._get_task(task_id)
        task.start()

    def stop_task(self, task_id: str):
        """Stop a Task by ID."""
        task = self._get_task(task_id)
        task.stop()

    def destroy_task(self, task_id: str):
        """Destroy a Task and remove all its data."""
        task = self._get_task(task_id)
        task.destroy()
        del self._tasks[task_id]

    def get_task(self, task_id: str) -> Task:
        """Get a Task by ID."""
        return self._get_task(task_id)

    def list_tasks(self) -> List[Dict]:
        """List all Tasks with their status."""
        result = []
        for task_id, task in sorted(self._tasks.items()):
            result.append({
                "task_id": task_id,
                "name": task.config.name,
                "state": task.state.value,
                "user_mode": task.config.user_mode,
                "rc_port": task.ports.get("rocketchat", "N/A"),
                "web_port": task.ports.get("web", "N/A"),
                "created_at": task.created_at,
            })
        return result

    def get_running_tasks(self) -> List[Task]:
        """Get all currently running Tasks."""
        return [t for t in self._tasks.values() if t.state == TaskState.RUNNING]

    def stop_all(self):
        """Stop all running Tasks."""
        for task in self.get_running_tasks():
            try:
                task.stop()
            except Exception as e:
                logger.error(f"Failed to stop {task.task_id}: {e}")

    # ── Internal ──────────────────────────────────────────────

    def _get_task(self, task_id: str) -> Task:
        """Get task or raise."""
        if task_id not in self._tasks:
            raise KeyError(f"Task not found: {task_id}")
        return self._tasks[task_id]
