"""Rocket.Chat channel implementation."""

import asyncio
import json
from typing import Any

import httpx
import websockets
from loguru import logger

from agent.bus.events import OutboundMessage
from agent.channels.base import BaseChannel


class RocketChatChannel(BaseChannel):
    """Rocket.Chat channel using REST API and WebSocket."""

    name = "rocketchat"
    display_name = "Rocket.Chat"

    def __init__(self, config: Any, bus):
        super().__init__(config, bus)
        self.base_url = getattr(config, "base_url", "http://localhost:3000")
        self.username = getattr(config, "username", "")
        self.password = getattr(config, "password", "")
        self.auth_token = None
        self.user_id = None
        self.ws = None
        self._listen_task = None

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
        """Start listening for messages via WebSocket."""
        if not await self._login():
            return

        self._running = True
        ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/websocket"

        try:
            async with websockets.connect(ws_url) as ws:
                self.ws = ws
                await self._ws_login()
                await self._subscribe_messages()
                self._listen_task = asyncio.create_task(self._listen_loop())
                await self._listen_task
        except Exception as e:
            logger.error("{}: WebSocket error: {}", self.name, e)
        finally:
            self._running = False

    async def _ws_login(self) -> None:
        """Authenticate WebSocket connection."""
        msg = {
            "msg": "method",
            "method": "login",
            "id": "1",
            "params": [{"resume": self.auth_token}],
        }
        await self.ws.send(json.dumps(msg))

    async def _subscribe_messages(self) -> None:
        """Subscribe to message stream."""
        msg = {"msg": "sub", "id": "2", "name": "stream-room-messages", "params": ["__my_messages__", False]}
        await self.ws.send(json.dumps(msg))

    async def _listen_loop(self) -> None:
        """Listen for incoming messages."""
        async for message in self.ws:
            try:
                data = json.loads(message)
                if data.get("msg") == "changed" and data.get("collection") == "stream-room-messages":
                    await self._handle_ws_message(data)
            except Exception as e:
                logger.error("{}: message handling error: {}", self.name, e)

    async def _handle_ws_message(self, data: dict) -> None:
        """Process WebSocket message."""
        fields = data.get("fields", {})
        args = fields.get("args", [])
        if not args:
            return

        msg_data = args[0]
        if msg_data.get("u", {}).get("_id") == self.user_id:
            return  # Skip own messages

        sender_id = msg_data.get("u", {}).get("_id", "")
        chat_id = msg_data.get("rid", "")
        content = msg_data.get("msg", "")

        await self._handle_message(sender_id, chat_id, content)

    async def send(self, msg: OutboundMessage) -> None:
        """Send message via REST API."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/api/v1/chat.sendMessage",
                    headers={
                        "X-Auth-Token": self.auth_token,
                        "X-User-Id": self.user_id,
                    },
                    json={"message": {"rid": msg.chat_id, "msg": msg.content}},
                )
                resp.raise_for_status()
        except Exception as e:
            logger.error("{}: send failed: {}", self.name, e)
            raise

    async def stop(self) -> None:
        """Stop the channel."""
        self._running = False
        if self._listen_task:
            self._listen_task.cancel()
        if self.ws:
            await self.ws.close()

