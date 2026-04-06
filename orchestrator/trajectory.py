"""Trajectory recording and management for agent and user sandboxes."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class TrajectoryRecorder:
    """Record execution trajectory for replay and analysis."""

    def __init__(self, sandbox_type: str, output_dir: str = "trajectories"):
        """
        Args:
            sandbox_type: "agent" or "user"
            output_dir: Directory to save trajectories
        """
        self.sandbox_type = sandbox_type
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.current_session = None
        self.events = []

    def start_session(self, session_id: str = None):
        """Start a new recording session."""
        if session_id is None:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.current_session = session_id
        self.events = []
        return session_id

    def record_event(self, event_type: str, data: Dict[str, Any]):
        """Record a single event with full context."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "sandbox": self.sandbox_type,
            "type": event_type,
            "data": data
        }
        self.events.append(event)

    def record_llm_call(self, prompt: str, response: str, model: str, metadata: Optional[Dict] = None):
        """Record complete LLM input/output for interpretability analysis."""
        self.record_event("llm.call", {
            "prompt": prompt,
            "response": response,
            "model": model,
            "metadata": metadata or {}
        })

    def record_user_action(self, action_type: str, details: Dict[str, Any]):
        """Record user sandbox actions (send email, send message, web operation)."""
        self.record_event("user.action", {
            "action_type": action_type,
            "details": details
        })

    def record_tool_call(self, tool_name: str, params: Dict, result: Any):
        """Record complete tool call with parameters and result."""
        self.record_event("tool.call", {
            "tool": tool_name,
            "params": params,
            "result": result
        })

    def save_session(self):
        """Save current session to file."""
        if not self.current_session:
            return

        filename = f"{self.sandbox_type}_{self.current_session}.jsonl"
        output_file = self.output_dir / filename
        with open(output_file, "w") as f:
            for event in self.events:
                f.write(json.dumps(event) + "\n")

        return output_file

    def load_session(self, session_id: str):
        """Load a session from file."""
        input_file = self.output_dir / f"{session_id}.jsonl"
        if not input_file.exists():
            raise FileNotFoundError(f"Session {session_id} not found")

        events = []
        with open(input_file, "r") as f:
            for line in f:
                events.append(json.loads(line))

        return events

