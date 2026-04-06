"""State recovery and replay mechanism."""

import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger


class StateRecovery:
    """Recover system state by replaying trajectories."""

    def __init__(self, trajectory_dir: str = "trajectories"):
        self.trajectory_dir = Path(trajectory_dir)
        self.agent_sandbox = None
        self.user_sandbox = None

    @classmethod
    def from_task_dir(cls, task_dir: str) -> "StateRecovery":
        """Create a StateRecovery from a task directory."""
        return cls(trajectory_dir=str(Path(task_dir) / "trajectories"))

    def load_trajectories(self, session_id: str = None) -> Dict[str, List[Dict]]:
        """Load both agent and user trajectories.

        If session_id is given, look for exact files. Otherwise, scan for
        the latest trajectory files in agent/ and user/ subdirectories
        (task-based layout) or flat layout.
        """
        trajectories = {"agent": [], "user": []}

        if session_id:
            # Try flat layout first
            for side in ("agent", "user"):
                flat = self.trajectory_dir / f"{side}_{session_id}.jsonl"
                nested = self.trajectory_dir / side / f"{side}_{session_id}.jsonl"
                path = flat if flat.exists() else nested
                if path.exists():
                    trajectories[side] = self._read_jsonl(path)
        else:
            # Auto-discover: find latest trajectory files
            for side in ("agent", "user"):
                subdir = self.trajectory_dir / side
                search_dir = subdir if subdir.is_dir() else self.trajectory_dir
                files = sorted(search_dir.glob(f"{side}_*.jsonl"))
                if files:
                    trajectories[side] = self._read_jsonl(files[-1])
                    logger.info(f"Loaded {side} trajectory: {files[-1].name} ({len(trajectories[side])} events)")

        return trajectories

    @staticmethod
    def _read_jsonl(path: Path) -> List[Dict]:
        """Read a JSONL file into a list of dicts."""
        events = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events

    def merge_trajectories(self, trajectories: Dict[str, List[Dict]]) -> List[Dict]:
        """Merge agent and user trajectories by timestamp."""
        all_events = []
        all_events.extend(trajectories["agent"])
        all_events.extend(trajectories["user"])
        all_events.sort(key=lambda e: e["timestamp"])
        return all_events

    def replay_to_step(self, target_step: int, session_id: str = None) -> List[Dict]:
        """Load and return events up to a specific step.

        Args:
            target_step: Number of events to replay (1-indexed)
            session_id: Optional session ID; if None, auto-discovers latest
        """
        trajectories = self.load_trajectories(session_id)
        merged = self.merge_trajectories(trajectories)

        if target_step > len(merged):
            target_step = len(merged)

        logger.info(f"Replaying {target_step}/{len(merged)} events")
        return merged[:target_step]

    def get_state_at_step(self, step: int, session_id: str = None) -> Dict[str, Any]:
        """Get system state summary at a specific step."""
        events = self.replay_to_step(step, session_id)

        state = {
            "step": step,
            "total_events": len(events),
            "last_event": events[-1] if events else None,
            "summary": self._summarize_state(events),
        }
        return state

    def _summarize_state(self, events: List[Dict]) -> Dict[str, int]:
        """Summarize state from events."""
        summary = {
            "messages_sent": 0,
            "llm_calls": 0,
            "tool_calls": 0,
            "user_actions": 0,
        }
        for event in events:
            event_type = event["type"]
            if "message" in event_type:
                summary["messages_sent"] += 1
            elif event_type == "llm.call":
                summary["llm_calls"] += 1
            elif event_type == "tool.call":
                summary["tool_calls"] += 1
            elif event_type == "user.action":
                summary["user_actions"] += 1
        return summary

    async def replay_events(self, events: List[Dict], agent_sandbox, user_sandbox):
        """Replay events by re-executing operations."""
        self.agent_sandbox = agent_sandbox
        self.user_sandbox = user_sandbox

        if agent_sandbox:
            agent_sandbox.enable_replay_mode()

        for i, event in enumerate(events):
            logger.info(f"Replaying step {i+1}/{len(events)}: {event['type']}")
            await self._replay_single_event(event)

        if agent_sandbox:
            agent_sandbox.disable_replay_mode()

    async def _replay_single_event(self, event: Dict):
        """Replay a single event."""
        event_type = event["type"]
        data = event["data"]
        sandbox = event["sandbox"]

        if sandbox == "user":
            await self._replay_user_event(event_type, data)
        elif sandbox == "agent":
            await self._replay_agent_event(event_type, data)

    async def _replay_user_event(self, event_type: str, data: Dict):
        """Replay user sandbox event."""
        if event_type == "user.action":
            action_type = data["action_type"]
            details = data["details"]

            if action_type == "send_message":
                await self.user_sandbox.send_message(
                    details["target"], details["message"]
                )
            elif action_type == "send_email":
                await self.user_sandbox.send_email(
                    details["to"], details["subject"], details["body"]
                )

    async def _replay_agent_event(self, event_type: str, data: Dict):
        """Replay agent sandbox event.

        Force agent to output recorded responses without calling LLM.
        """
        if event_type == "llm.call":
            prompt = data.get("prompt")
            response = data.get("response")
            logger.info(f"Forcing LLM response (no actual call)")
            await self.agent_sandbox.force_llm_response(prompt, response)

        elif event_type == "tool.call":
            tool_name = data.get("tool_name")
            params = data.get("params")
            result = data.get("result")
            logger.info(f"Forcing tool result: {tool_name}")
            await self.agent_sandbox.force_tool_result(tool_name, params, result)

        elif event_type == "message.outbound":
            channel = data.get("channel")
            content = data.get("content")
            logger.info(f"Forcing outbound message via {channel}")
            await self.agent_sandbox.force_send_message(channel, content)
