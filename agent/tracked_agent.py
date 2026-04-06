"""Agent with trajectory recording."""

import asyncio
from loguru import logger

from agent.bus.queue import MessageBus
from agent.bus.events import OutboundMessage
from orchestrator.trajectory import TrajectoryRecorder


class TrackedAgent:
    """Agent with trajectory recording."""

    def __init__(self, bus: MessageBus, recorder: TrajectoryRecorder):
        self.bus = bus
        self.recorder = recorder
        self._running = False

    async def start(self):
        """Start processing messages."""
        self._running = True
        session_id = self.recorder.start_session()
        logger.info(f"Agent started, session: {session_id}")

        while self._running:
            try:
                msg = await self.bus.consume_inbound()

                # Record inbound message
                self.recorder.record_event("message.inbound", {
                    "channel": msg.channel,
                    "sender_id": msg.sender_id,
                    "chat_id": msg.chat_id,
                    "content": msg.content
                })

                logger.info(f"Received: {msg.content}")

                # Generate response
                response = OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=f"Echo: {msg.content}",
                )

                # Record outbound message
                self.recorder.record_event("message.outbound", {
                    "channel": response.channel,
                    "chat_id": response.chat_id,
                    "content": response.content
                })

                await self.bus.publish_outbound(response)

            except Exception as e:
                logger.error(f"Agent error: {e}")

    async def stop(self):
        """Stop the agent and save trajectory."""
        self._running = False
        output_file = self.recorder.save_session()
        logger.info(f"Trajectory saved to {output_file}")

