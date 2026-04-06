"""Real-time Task monitor: aggregate and display logs from all sandbox containers.

Provides a unified terminal view of all running Tasks, showing inter-sandbox
communication, tool calls, and system events in real time.
"""

import subprocess
import threading
import time
import re
from typing import Dict, List, Optional
from loguru import logger

from orchestrator.task_manager import TaskManager
from orchestrator.task import TaskState


# ANSI color codes for different sandbox types
COLORS = {
    "agent": "\033[36m",      # Cyan
    "rocketchat": "\033[33m", # Yellow
    "mailserver": "\033[35m", # Magenta
    "webenv": "\033[32m",     # Green
    "user": "\033[34m",       # Blue
    "mongodb": "\033[90m",    # Gray
    "system": "\033[97m",     # White
}
RESET = "\033[0m"
BOLD = "\033[1m"


class TaskMonitor:
    """Real-time monitor for all running Tasks."""

    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager
        self._running = False
        self._threads: List[threading.Thread] = []

    def start(self, task_ids: List[str] = None, follow: bool = True):
        """Start monitoring. If task_ids is None, monitor all running tasks."""
        self._running = True

        if task_ids:
            tasks = [self.task_manager.get_task(tid) for tid in task_ids]
        else:
            tasks = self.task_manager.get_running_tasks()

        if not tasks:
            print(f"{BOLD}No running tasks to monitor.{RESET}")
            return

        print(f"{BOLD}{'='*70}")
        print(f"  ASE Task Monitor — {len(tasks)} task(s)")
        print(f"{'='*70}{RESET}\n")

        for task in tasks:
            print(f"  {BOLD}{task.task_id}{RESET}: "
                  f"RC=http://localhost:{task.ports.get('rocketchat', '?')} "
                  f"Web=http://localhost:{task.ports.get('web', '?')} "
                  f"Mode={task.config.user_mode}")
        print()

        if follow:
            # Stream logs from each task in a separate thread
            for task in tasks:
                t = threading.Thread(
                    target=self._stream_task_logs,
                    args=(task.task_id, task.compose_file),
                    daemon=True,
                )
                self._threads.append(t)
                t.start()

            try:
                while self._running:
                    time.sleep(1)
            except KeyboardInterrupt:
                self._running = False
                print(f"\n{BOLD}Monitor stopped.{RESET}")
        else:
            # One-shot: print recent logs
            for task in tasks:
                self._print_recent_logs(task)

    def stop(self):
        """Stop monitoring."""
        self._running = False

    def _stream_task_logs(self, task_id: str, compose_file):
        """Stream docker compose logs for a task."""
        if not compose_file or not compose_file.exists():
            return

        proc = subprocess.Popen(
            ["docker", "compose", "-f", str(compose_file),
             "-p", f"ase-{task_id}", "logs", "-f", "--tail", "20"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        try:
            for line in proc.stdout:
                if not self._running:
                    break
                formatted = self._format_log_line(task_id, line.rstrip())
                if formatted:
                    print(formatted)
        except Exception:
            pass
        finally:
            proc.terminate()

    def _format_log_line(self, task_id: str, line: str) -> Optional[str]:
        """Format a log line with colors and task prefix."""
        if not line.strip():
            return None

        # Try to extract service name from docker compose log format
        # Format: "service-name  | log content"
        service = "system"
        content = line

        # Docker compose log format: "container_name  | message"
        match = re.match(r'^([\w-]+)\s+\|\s+(.*)', line)
        if match:
            container_name = match.group(1)
            content = match.group(2)

            # Extract service from container name (e.g., "ase-task-001-agent" -> "agent")
            for svc in ["agent", "user", "rocketchat", "mailserver", "webenv", "mongodb"]:
                if svc in container_name:
                    service = svc
                    break

        color = COLORS.get(service, COLORS["system"])

        # Highlight interesting events
        highlight = ""
        if "Tool call:" in content or "tool.call" in content:
            highlight = f"{BOLD}"
        elif "LLM response:" in content or "llm.call" in content:
            highlight = f"{BOLD}"
        elif "received message" in content or "sent message" in content:
            highlight = f"{BOLD}"

        return f"{color}[{task_id}/{service}]{RESET} {highlight}{content}{RESET if highlight else ''}"

    def _print_recent_logs(self, task, tail: int = 30):
        """Print recent logs for a task (non-streaming)."""
        logs = task.get_logs(tail=tail)
        if logs:
            print(f"\n{BOLD}--- {task.task_id} ---{RESET}")
            for line in logs.splitlines():
                formatted = self._format_log_line(task.task_id, line)
                if formatted:
                    print(formatted)


def print_task_table(tasks: List[Dict]):
    """Pretty-print a list of tasks as a table."""
    if not tasks:
        print("No tasks found.")
        return

    print(f"\n{BOLD}{'ID':<12} {'Name':<15} {'State':<10} {'Mode':<12} {'RC Port':<10} {'Web Port':<10} {'Created'}{RESET}")
    print("-" * 85)
    for t in tasks:
        state = t["state"]
        color = {
            "running": "\033[32m",
            "stopped": "\033[90m",
            "error": "\033[31m",
            "starting": "\033[33m",
        }.get(state, "")
        created = t["created_at"][:19] if t["created_at"] else ""
        print(f"{t['task_id']:<12} {t.get('name', ''):<15} {color}{state:<10}{RESET} "
              f"{t['user_mode']:<12} {str(t.get('rc_port', '')):<10} "
              f"{str(t.get('web_port', '')):<10} {created}")
    print()
