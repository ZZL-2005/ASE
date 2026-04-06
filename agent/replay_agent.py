"""Agent with replay support for state recovery."""

import asyncio
from typing import Optional, Dict, Any
from loguru import logger

from agent.bus.queue import MessageBus
from agent.bus.events import OutboundMessage
from orchestrator.trajectory import TrajectoryRecorder


class ReplayAgent:
    """Agent that supports forced replay from trajectories."""

    def __init__(self, bus: MessageBus, recorder: Optional[TrajectoryRecorder] = None):
        self.bus = bus
        self.recorder = recorder
        self._running = False
        self._replay_mode = False
        self._forced_responses = asyncio.Queue()

    async def start(self):
        """Start processing messages."""
        self._running = True
        logger.info("ReplayAgent started")

        while self._running:
            try:
                msg = await self.bus.consume_inbound()

                if self._replay_mode:
                    # In replay mode, use forced response
                    response_data = await self._forced_responses.get()
                    response = OutboundMessage(
                        channel=response_data["channel"],
                        chat_id=response_data["chat_id"],
                        content=response_data["content"],
                    )
                else:
                    # Normal mode: process message
                    response = await self._process_message(msg)

                    # Record outbound message
                    if self.recorder:
                        self.recorder.record_message(
                            direction="outbound",
                            channel=response.channel,
                            chat_id=response.chat_id,
                            content=response.content
                        )

                await self.bus.publish_outbound(response)

            except Exception as e:
                logger.error(f"Agent error: {e}")

    async def _process_message(self, msg):
        """Process inbound message (override in subclass)."""
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=f"Echo: {msg.content}",
        )

    def enable_replay_mode(self):
        """Enable replay mode."""
        self._replay_mode = True
        logger.info("Replay mode enabled")

    def disable_replay_mode(self):
        """Disable replay mode."""
        self._replay_mode = False
        logger.info("Replay mode disabled")

    async def force_send_message(self, channel: str, chat_id: str, content: str):
        """Force agent to send a specific message."""
        await self._forced_responses.put({
            "channel": channel,
            "chat_id": chat_id,
            "content": content
        })

    async def force_llm_response(self, prompt: str, response: str):
        """Force LLM response without actual call."""
        logger.info(f"Forced LLM response (replay)")
        # Store for next message processing
        self._last_forced_llm = response

    async def force_tool_result(self, tool_name: str, params: Dict, result: Any):
        """Force tool result without actual execution."""
        logger.info(f"Forced tool result: {tool_name} (replay)")
        # Store for next message processing
        self._last_forced_tool = result

    async def stop(self):
        """Stop the agent."""
        self._running = False
