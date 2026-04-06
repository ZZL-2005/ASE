#!/usr/bin/env python3
"""Test ASE system without Rocket.Chat dependency."""

import asyncio
from loguru import logger

from agent.bus.queue import MessageBus
from agent.bus.events import InboundMessage
from agent.simple_agent import SimpleAgent
from orchestrator.trajectory import TrajectoryRecorder


async def test_agent():
    """Test agent with simulated messages."""
    bus = MessageBus()
    recorder = TrajectoryRecorder(sandbox_type="agent")
    agent = SimpleAgent(bus=bus)

    # Start agent
    agent_task = asyncio.create_task(agent.start())

    # Simulate messages
    await asyncio.sleep(1)

    msg = InboundMessage(
        channel="test",
        chat_id="test_chat",
        sender_id="test_user",
        content="Hello Agent!"
    )

    await bus.publish_inbound(msg)
    logger.info("Sent test message")

    # Get response
    await asyncio.sleep(1)
    response = await bus.consume_outbound()
    logger.info(f"Got response: {response.content}")

    await agent.stop()
    logger.info("Test complete!")


if __name__ == "__main__":
    asyncio.run(test_agent())
