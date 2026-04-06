"""LLM-powered agent."""

import asyncio
from typing import Optional, List, Dict
from loguru import logger

from agent.bus.queue import MessageBus
from agent.bus.events import OutboundMessage
from agent.llm_client import LLMClient
from orchestrator.trajectory import TrajectoryRecorder
from config import LLM_API_BASE, LLM_API_KEY, LLM_MODEL, LLM_TEMPERATURE


class LLMAgent:
    """Agent powered by LLM."""

    def __init__(self, bus: MessageBus, recorder: Optional[TrajectoryRecorder] = None):
        self.bus = bus
        self.recorder = recorder
        self.llm = LLMClient(LLM_API_BASE, LLM_API_KEY, LLM_MODEL, LLM_TEMPERATURE)
        self._running = False
        self._replay_mode = False
        self._forced_responses = asyncio.Queue()
        self.conversation_history: List[Dict] = []

    async def start(self):
        """Start processing messages."""
        self._running = True
        logger.info("LLMAgent started")

        while self._running:
            try:
                msg = await self.bus.consume_inbound()
                logger.info(f"Received: {msg.content} from {msg.sender_id}")

                if self.recorder:
                    self.recorder.record_event("message.inbound", {
                        "channel": msg.channel,
                        "sender_id": msg.sender_id,
                        "chat_id": msg.chat_id,
                        "content": msg.content,
                    })

                if self._replay_mode:
                    response_data = await self._forced_responses.get()
                    content = response_data["content"]
                else:
                    content = await self._process_with_llm(msg.content)

                response = OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=content,
                )

                await self.bus.publish_outbound(response)
                logger.info(f"Sent response to {msg.chat_id}")

                if self.recorder:
                    self.recorder.record_event("message.outbound", {
                        "channel": msg.channel,
                        "chat_id": msg.chat_id,
                        "content": content,
                    })
                    self.recorder.save_session()

            except Exception as e:
                logger.error(f"Agent error: {e}")

    async def _process_with_llm(self, user_message: str) -> str:
        """Process message with LLM."""
        self.conversation_history.append({"role": "user", "content": user_message})

        response = await self.llm.chat(self.conversation_history)

        if self.recorder:
            self.recorder.record_llm_call(
                prompt=user_message,
                response=response,
                model=LLM_MODEL
            )

        self.conversation_history.append({"role": "assistant", "content": response})
        return response

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

    async def stop(self):
        """Stop the agent."""
        self._running = False

