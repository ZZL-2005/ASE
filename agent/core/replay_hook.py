"""Replay hook: intercepts LLM calls and tool execution with recorded results."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

from loguru import logger

from agent.core.hook import AgentHook, AgentHookContext
from agent.providers.base import LLMResponse, ToolCallRequest


class ReplayHook(AgentHook):
    """Load a trajectory JSONL and replay LLM/tool results without real calls.

    Events are consumed in order. When the AgentRunner asks for an LLM
    response or a tool result, the next matching event is popped from the
    queue and returned.
    """

    def __init__(self, trajectory_path: str, max_steps: int | None = None):
        self._llm_queue: deque[dict] = deque()
        self._tool_queue: deque[dict] = deque()
        self._step = 0
        self._max_steps = max_steps
        self._done = False
        self._load(trajectory_path, max_steps)

    def _load(self, path: str, max_steps: int | None):
        """Load trajectory JSONL and split into llm / tool queues."""
        events = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))

        if max_steps is not None:
            events = events[:max_steps]

        for ev in events:
            etype = ev.get("type", "")
            if etype == "llm.call":
                self._llm_queue.append(ev["data"])
            elif etype == "tool.call":
                self._tool_queue.append(ev["data"])
            # message.inbound / message.outbound are handled by the CLI injector

        logger.info(
            "ReplayHook loaded: {} LLM calls, {} tool calls from {}",
            len(self._llm_queue), len(self._tool_queue), path,
        )

    @property
    def is_done(self) -> bool:
        return self._done

    async def get_forced_response(self, context: AgentHookContext) -> LLMResponse | None:
        if not self._llm_queue:
            self._done = True
            return None

        data = self._llm_queue.popleft()
        response_text = data.get("response", "")
        # Strip leading whitespace that DeepSeek sometimes adds
        response_text = response_text.strip()

        logger.info("ReplayHook: forcing LLM response ({}  remaining)", len(self._llm_queue))

        # Build tool calls if the response contained them (check next events)
        tool_calls = self._extract_pending_tool_calls(data)

        return LLMResponse(
            content=response_text if not tool_calls else (response_text or None),
            tool_calls=tool_calls,
            finish_reason="stop" if not tool_calls else "tool_calls",
            usage=data.get("metadata", {}).get("usage", {}),
        )

    def _extract_pending_tool_calls(self, llm_data: dict) -> list[ToolCallRequest]:
        """If the original LLM response triggered tool calls, reconstruct them.

        We detect this by checking if stop_reason was not 'completed' (meaning
        the LLM wanted to call tools), and peek at the tool queue.
        """
        stop_reason = llm_data.get("metadata", {}).get("stop_reason")
        if stop_reason == "completed" or stop_reason is None:
            return []

        # Peek at tool queue — take tool events that would have been part of
        # this LLM iteration
        tool_calls = []
        # We don't know exact count, but tools are consumed in get_forced_tool_result
        # Return empty — the content already includes tool call markers that the
        # provider would have parsed. We need to let the runner handle this.
        return []

    def get_forced_tool_result(self, tool_name: str, params: dict) -> str | None:
        if not self._tool_queue:
            return None

        data = self._tool_queue.popleft()
        result = data.get("result", "")
        recorded_tool = data.get("tool", data.get("tool_name", ""))
        logger.info("ReplayHook: forcing tool result for {} ({} remaining)", recorded_tool, len(self._tool_queue))
        return result
