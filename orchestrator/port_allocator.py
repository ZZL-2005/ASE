"""Port allocator for multi-task isolation.

Each Task gets an independent port range so multiple Tasks can run in parallel
without port conflicts.
"""

import json
from pathlib import Path
from typing import Dict, Optional
from loguru import logger


class PortAllocator:
    """Allocate non-conflicting port ranges for each Task.

    Strategy: base_port = 10000 + task_index * 100
    Each Task gets ports:
        - rocketchat:  base + 1
        - mongodb:     (internal only, no host mapping)
        - smtp:        base + 25
        - imap:        base + 43
        - smtp_submit: base + 87
        - imaps:       base + 93
        - web:         base + 80
    """

    PORT_OFFSET = {
        "rocketchat": 1,
        "smtp": 25,
        "imap": 43,
        "web": 80,
        "smtp_submit": 87,
        "imaps": 93,
    }

    def __init__(self, base: int = 10000, step: int = 100, state_file: str = None):
        self.base = base
        self.step = step
        self._allocated: Dict[str, int] = {}  # task_id -> base_port
        self._next_index = 0

        if state_file is None:
            state_file = str(Path(__file__).resolve().parent.parent / "tasks" / ".port_state.json")
        self.state_file = Path(state_file)
        self._load_state()

    def _load_state(self):
        """Load allocation state from disk."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                self._allocated = data.get("allocated", {})
                self._next_index = data.get("next_index", 0)
            except Exception:
                pass

    def _save_state(self):
        """Persist allocation state to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps({
            "allocated": self._allocated,
            "next_index": self._next_index,
        }, indent=2))

    def allocate(self, task_id: str) -> Dict[str, int]:
        """Allocate a port range for a Task. Returns port mapping dict."""
        if task_id in self._allocated:
            base = self._allocated[task_id]
        else:
            base = self.base + self._next_index * self.step
            self._allocated[task_id] = base
            self._next_index += 1
            self._save_state()

        ports = {name: base + offset for name, offset in self.PORT_OFFSET.items()}
        logger.info(f"Ports for {task_id}: RC={ports['rocketchat']}, Web={ports['web']}, IMAP={ports['imap']}")
        return ports

    def release(self, task_id: str):
        """Release ports for a stopped Task."""
        if task_id in self._allocated:
            del self._allocated[task_id]
            self._save_state()

    def get_ports(self, task_id: str) -> Optional[Dict[str, int]]:
        """Get allocated ports for a Task without allocating new ones."""
        if task_id not in self._allocated:
            return None
        base = self._allocated[task_id]
        return {name: base + offset for name, offset in self.PORT_OFFSET.items()}
