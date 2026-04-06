"""Run LLM-powered agent."""

import asyncio
import signal
from loguru import logger

from agent.bus.queue import MessageBus
from agent.llm_agent import LLMAgent
from agent.channels.rocketchat_ws import RocketChatWSChannel
from agent.channels.email import EmailChannel
from orchestrator.trajectory import TrajectoryRecorder


class Config:
    """Simple config object."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


async def dispatch_outbound(bus: MessageBus, channels: dict):
    """Dispatch outbound messages to the correct channel."""
    while True:
        msg = await bus.consume_outbound()
        channel = channels.get(msg.channel)
        if channel:
            try:
                await channel.send(msg)
            except Exception as e:
                logger.error(f"Failed to send via {msg.channel}: {e}")
        else:
            logger.warning(f"No channel for: {msg.channel}")


async def main():
    """Start LLM agent with Rocket.Chat and Email."""
    bus = MessageBus()
    recorder = TrajectoryRecorder(sandbox_type="agent")
    recorder.start_session()
    agent = LLMAgent(bus=bus, recorder=recorder)

    # Rocket.Chat config
    rc_config = Config(
        base_url="http://rocketchat:3000",
        username="agent",
        password="agent_pass_2026",
        allow_from=["*"],
        streaming=False,
    )
    rc_channel = RocketChatWSChannel(config=rc_config, bus=bus)

    # Email config
    email_config = Config(
        imap_host="mailserver",
        imap_port=143,
        smtp_host="mailserver",
        smtp_port=587,
        username="agent@ase.local",
        password="agent_pass_2026",
        allow_from=["*"],
        streaming=False,
    )
    email_channel = EmailChannel(config=email_config, bus=bus)

    channels = {
        "rocketchat": rc_channel,
        "email": email_channel,
    }

    # Save trajectory on shutdown
    def _save_on_exit():
        path = recorder.save_session()
        if path:
            logger.info(f"Trajectory saved to {path}")

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _save_on_exit)

    logger.info("Starting LLM agent with Rocket.Chat + Email...")
    await asyncio.gather(
        rc_channel.start(),
        email_channel.start(),
        agent.start(),
        dispatch_outbound(bus, channels),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent stopped")
