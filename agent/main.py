"""Agent main entry point."""

import asyncio
from typing import Any

from loguru import logger

from agent.bus.queue import MessageBus
from agent.channels.rocketchat_simple import RocketChatChannel
from agent.channels.email import EmailChannel
from agent.simple_agent import SimpleAgent


class SimpleConfig:
    """Simple config object."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


async def dispatch_outbound(bus: MessageBus, channels: dict):
    """Dispatch outbound messages to channels."""
    while True:
        msg = await bus.consume_outbound()
        channel = channels.get(msg.channel)
        if channel:
            try:
                await channel.send(msg)
            except Exception as e:
                logger.error(f"Failed to send via {msg.channel}: {e}")


async def main():
    """Start agent with channels."""
    bus = MessageBus()

    # Rocket.Chat config
    rc_config = SimpleConfig(
        base_url="http://localhost:3001",
        username="agent",
        password="agent_pass_2026",
        allow_from=["*"],
        streaming=False,
    )

    # Email config
    email_config = SimpleConfig(
        imap_host="localhost",
        imap_port=1143,
        smtp_host="localhost",
        smtp_port=1587,
        username="agent@ase.local",
        password="agent_pass_2026",
        allow_from=["*"],
        streaming=False,
    )

    rc_channel = RocketChatChannel(rc_config, bus)
    email_channel = EmailChannel(email_config, bus)

    channels = {
        "rocketchat": rc_channel,
        "email": email_channel,
    }

    agent = SimpleAgent(bus)

    logger.info("Starting ASE agent...")

    try:
        await asyncio.gather(
            rc_channel.start(),
            email_channel.start(),
            agent.start(),
            dispatch_outbound(bus, channels),
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        await rc_channel.stop()
        await email_channel.stop()
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())

