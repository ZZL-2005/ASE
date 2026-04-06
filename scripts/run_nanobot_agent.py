"""Full nanobot agent entry point for ASE sandbox."""

import asyncio
import os
import signal
from pathlib import Path

from loguru import logger

from agent.bus.queue import MessageBus
from agent.channels.rocketchat_ws import RocketChatWSChannel
from agent.channels.email import EmailChannel
from agent.config.schema import ExecToolConfig, WebSearchConfig
from agent.providers.openai_compat_provider import OpenAICompatProvider
from agent.core.loop import AgentLoop
from agent.core.trajectory_hook import TrajectoryHook
from agent.core.replay_hook import ReplayHook
from orchestrator.trajectory import TrajectoryRecorder


class Config:
    """Simple config object."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


async def dispatch_outbound(bus: MessageBus, channels: dict, recorder: TrajectoryRecorder = None):
    """Dispatch outbound messages to the correct channel."""
    while True:
        msg = await bus.consume_outbound()
        # Skip progress/streaming messages
        if msg.metadata and msg.metadata.get("_progress"):
            continue
        channel = channels.get(msg.channel)
        if channel:
            try:
                await channel.send(msg)
                if recorder:
                    recorder.record_event("message.outbound", {
                        "channel": msg.channel,
                        "chat_id": msg.chat_id,
                        "content": msg.content,
                    })
                    recorder.save_session()
            except Exception as e:
                logger.error(f"Failed to send via {msg.channel}: {e}")
        else:
            logger.warning(f"No channel for: {msg.channel}")


async def main():
    """Start the full nanobot agent with Rocket.Chat and Email channels."""
    bus = MessageBus()

    # LLM configuration from environment
    api_base = os.environ.get("LLM_API_BASE", "https://api2.aigcbest.top/v1")
    api_key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "DeepSeek-V3")
    temperature = float(os.environ.get("LLM_TEMPERATURE", "0.7"))
    max_tokens = int(os.environ.get("LLM_MAX_TOKENS", "8192"))

    # Workspace
    workspace = Path(os.environ.get("AGENT_WORKSPACE", "/app/workspace"))
    workspace.mkdir(parents=True, exist_ok=True)

    # Create LLM provider
    from agent.providers.base import GenerationSettings
    provider = OpenAICompatProvider(
        api_key=api_key,
        api_base=api_base,
        default_model=model,
    )
    provider.generation = GenerationSettings(
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Tool configs
    exec_config = ExecToolConfig(enable=True, timeout=60)
    web_search_config = WebSearchConfig()

    # Trajectory / Replay
    replay_mode = os.environ.get("REPLAY_MODE", "") == "1"
    traj_dir = Path(os.environ.get("TRAJECTORY_DIR", "/app/trajectories"))
    traj_dir.mkdir(parents=True, exist_ok=True)

    hooks = []
    recorder = None
    if replay_mode:
        replay_path = os.environ.get("REPLAY_TRAJECTORY", "")
        replay_steps = int(os.environ.get("REPLAY_STEPS", "0")) or None
        if replay_path and Path(replay_path).exists():
            logger.info(f"REPLAY MODE: loading {replay_path}, steps={replay_steps}")
            hooks.append(ReplayHook(replay_path, max_steps=replay_steps))
        else:
            logger.error(f"REPLAY MODE but trajectory not found: {replay_path}")
    else:
        recorder = TrajectoryRecorder(sandbox_type="agent", output_dir=str(traj_dir))
        recorder.start_session()
        hooks.append(TrajectoryHook(recorder, model=model))

    # Create the full AgentLoop (nanobot core)
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        model=model,
        max_iterations=40,
        context_window_tokens=65536,
        web_search_config=web_search_config,
        exec_config=exec_config,
        cron_service=None,
        mcp_servers={},
        timezone="UTC",
        hooks=hooks,
    )

    # Rocket.Chat channel
    rc_config = Config(
        base_url=os.environ.get("RC_URL", "http://rocketchat:3000"),
        username=os.environ.get("RC_USERNAME", "agent"),
        password=os.environ.get("RC_PASSWORD", "agent_pass_2026"),
        allow_from=["*"],
        streaming=False,
    )
    rc_channel = RocketChatWSChannel(config=rc_config, bus=bus)

    # Email channel
    email_config = Config(
        imap_host=os.environ.get("IMAP_HOST", "mailserver"),
        imap_port=int(os.environ.get("IMAP_PORT", "143")),
        smtp_host=os.environ.get("SMTP_HOST", "mailserver"),
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        username=os.environ.get("EMAIL_USER", "agent@ase.local"),
        password=os.environ.get("EMAIL_PASS", "agent_pass_2026"),
        allow_from=["*"],
        streaming=False,
    )
    email_channel = EmailChannel(config=email_config, bus=bus)

    channels = {"rocketchat": rc_channel, "email": email_channel}

    logger.info("Starting full nanobot agent (ASE sandbox)...")
    logger.info(f"  Model: {model}")
    logger.info(f"  API Base: {api_base}")
    logger.info(f"  Workspace: {workspace}")
    logger.info(f"  Tools: exec, read_file, write_file, edit_file, list_dir, web_search, web_fetch, message, spawn")

    await asyncio.gather(
        rc_channel.start(),
        email_channel.start(),
        agent_loop.run(),
        dispatch_outbound(bus, channels, recorder=recorder if not replay_mode else None),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent stopped")
