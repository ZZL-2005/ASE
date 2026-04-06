"""Simple agent runner for testing channels."""

import asyncio
from loguru import logger

from agent.bus.queue import MessageBus
from agent.bus.events import OutboundMessage


class SimpleAgent:
    """Simple echo agent for testing."""

    def __init__(self, bus: MessageBus):
        self.bus = bus
        self._running = False

    async def start(self):
        """Start processing messages."""
        self._running = True
        logger.info("Agent started")

        while self._running:
            try:
                msg = await self.bus.consume_inbound()
                logger.info(f"Received: {msg.content} from {msg.sender_id}")

                # Echo response
                response = OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=f"Echo: {msg.content}",
                )

                await self.bus.publish_outbound(response)
                logger.info(f"Sent response to {msg.chat_id}")

            except Exception as e:
                logger.error(f"Agent error: {e}")

    async def stop(self):
        """Stop the agent."""
        self._running = False
