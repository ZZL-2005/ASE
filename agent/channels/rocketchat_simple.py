"""Simplified Rocket.Chat channel using polling."""

import asyncio
import json
from typing import Any

import httpx
from loguru import logger

from agent.bus.events import OutboundMessage
from agent.channels.base import BaseChannel


class RocketChatChannel(BaseChannel):
    """Rocket.Chat channel using REST API polling."""

    name = "rocketchat"
    display_name = "Rocket.Chat"

    def __init__(self, config: Any, bus):
        super().__init__(config, bus)
        self.base_url = getattr(config, "base_url", "http://localhost:3001")
        self.username = getattr(config, "username", "")
        self.password = getattr(config, "password", "")
        self.auth_token = None
        self.user_id = None
        self.last_ts = None

    async def _login(self) -> bool:
        """Login to Rocket.Chat and get auth token."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/api/v1/login",
                    json={"user": self.username, "password": self.password},
                )
                resp.raise_for_status()
                data = resp.json()
                self.auth_token = data["data"]["authToken"]
                self.user_id = data["data"]["userId"]
                logger.info("{}: logged in as {}", self.name, self.username)
                return True
        except Exception as e:
            logger.error("{}: login failed: {}", self.name, e)
            return False

    async def start(self) -> None:
        """Start polling for messages and sending responses."""
        if not await self._login():
            return

        self._running = True
        logger.info("{}: started polling", self.name)

        # Start outbound message sender
        sender_task = asyncio.create_task(self._send_loop())

        while self._running:
            try:
                await self._poll_messages()
                await asyncio.sleep(10)  # Increased from 2 to 10 seconds
            except Exception as e:
                logger.error("{}: poll error: {}", self.name, e)
                await asyncio.sleep(15)

    async def _send_loop(self):
        """Consume outbound messages and send them."""
        while self._running:
            try:
                msg = await self.bus.consume_outbound()
                await self.send(msg)
            except Exception as e:
                logger.error("{}: send error: {}", self.name, e)
                await asyncio.sleep(1)

    async def _poll_messages(self) -> None:
        """Poll for new messages."""
        headers = {
            "X-Auth-Token": self.auth_token,
            "X-User-Id": self.user_id,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/subscriptions.get",
                    headers=headers,
                )

                if resp.status_code != 200:
                    logger.warning("{}: subscriptions failed: {}", self.name, resp.status_code)
                    return

                subs = resp.json().get("update", [])
                for sub in subs:
                    if sub.get("unread", 0) > 0:
                        logger.info("{}: found unread in room {}", self.name, sub["rid"])
                        await self._fetch_room_messages(sub["rid"], headers)
        except Exception as e:
            logger.error("{}: poll error: {}", self.name, e)

    async def _fetch_room_messages(self, room_id: str, headers: dict) -> None:
        """Fetch messages from a room (supports both channels and DMs)."""
        async with httpx.AsyncClient() as client:
            # Try channels first
            resp = await client.get(
                f"{self.base_url}/api/v1/channels.messages",
                headers=headers,
                params={"roomId": room_id, "count": 10},
            )

            # If not a channel, try DM
            if resp.status_code != 200:
                resp = await client.get(
                    f"{self.base_url}/api/v1/im.messages",
                    headers=headers,
                    params={"roomId": room_id, "count": 10},
                )

            if resp.status_code != 200:
                return

            messages = resp.json().get("messages", [])
            for msg in reversed(messages):
                if msg["u"]["_id"] != self.user_id:
                    await self._handle_message(
                        msg["u"]["_id"],
                        room_id,
                        msg["msg"]
                    )
                    logger.info("{}: received message from {}", self.name, msg["u"]["username"])

    async def send(self, msg: OutboundMessage) -> None:
        """Send message via REST API."""
        headers = {
            "X-Auth-Token": self.auth_token,
            "X-User-Id": self.user_id,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/chat.sendMessage",
                headers=headers,
                json={"message": {"rid": msg.chat_id, "msg": msg.content}},
            )
            if resp.status_code == 200:
                logger.info("{}: sent message to {}", self.name, msg.chat_id)

    async def stop(self) -> None:
        """Stop the channel."""
        self._running = False

