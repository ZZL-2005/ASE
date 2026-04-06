"""AgentHook that records execution trajectory for replay and analysis."""

from __future__ import annotations

from loguru import logger

from agent.core.hook import AgentHook, AgentHookContext
from orchestrator.trajectory import TrajectoryRecorder


class TrajectoryHook(AgentHook):
    """Record LLM calls, tool calls, and responses into TrajectoryRecorder."""

    def __init__(self, recorder: TrajectoryRecorder, model: str = "unknown"):
        self.recorder = recorder
        self.model = model
        self._recorded_first_msg = False

    async def before_iteration(self, context: AgentHookContext) -> None:
        """Record the inbound user message on the first iteration."""
        if context.iteration == 0:
            user_msg = self._extract_last_user_msg(context.messages)
            if user_msg:
                # Extract clean user text (strip Runtime Context prefix)
                clean = user_msg
                if clean.startswith("[Runtime Context"):
                    parts = clean.rsplit("\n\n", 1)
                    clean = parts[-1].strip() if len(parts) > 1 else clean
                # Extract chat_id from context lines
                chat_id = ""
                for line in user_msg.split("\n"):
                    if line.startswith("Chat ID:"):
                        chat_id = line.split(":", 1)[1].strip()
                self.recorder.record_event("message.inbound", {
                    "channel": "rocketchat",
                    "chat_id": chat_id,
                    "content": clean,
                })

    async def after_iteration(self, context: AgentHookContext) -> None:
        """Record LLM response and tool calls after each iteration."""
        if context.response is not None:
            self.recorder.record_llm_call(
                prompt=self._extract_last_user_msg(context.messages),
                response=context.response.content or "",
                model=self.model,
                metadata={
                    "iteration": context.iteration,
                    "usage": context.usage,
                    "stop_reason": context.stop_reason,
                },
            )

        for i, tc in enumerate(context.tool_calls):
            result = context.tool_results[i] if i < len(context.tool_results) else None
            self.recorder.record_tool_call(
                tool_name=tc.name,
                params=tc.arguments,
                result=str(result) if result is not None else "",
            )

        self.recorder.save_session()

    @staticmethod
    def _extract_last_user_msg(messages: list[dict]) -> str:
        """Extract the last user message from the conversation."""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    texts = [b.get("text", "") for b in content if b.get("type") == "text"]
                    return " ".join(texts)
        return ""
