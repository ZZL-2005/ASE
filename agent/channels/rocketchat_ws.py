"""Rocket.Chat channel using WebSocket (realtime API)."""

import asyncio
import json
from typing import Any
import hashlib

import httpx
import websockets
from loguru import logger

from agent.bus.events import OutboundMessage
from agent.channels.base import BaseChannel


class RocketChatWSChannel(BaseChannel):
    """Rocket.Chat channel using WebSocket realtime API."""

    name = "rocketchat"
    display_name = "Rocket.Chat"

    def __init__(self, config: Any, bus):
        super().__init__(config, bus)
        self.base_url = getattr(config, "base_url", "http://localhost:3001")
        self.username = getattr(config, "username", "")
        self.password = getattr(config, "password", "")
        self.ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://") + "/websocket"
        self.ws = None
        self.msg_id = 0
        self.auth_token = None
        self.user_id = None
        self._seen_msg_ids: set[str] = set()  # dedup message IDs

    def _next_id(self) -> str:
        """Generate next message ID."""
        self.msg_id += 1
        return str(self.msg_id)

    async def _send_ws(self, msg: dict):
        """Send message via WebSocket."""
        if self.ws:
            await self.ws.send(json.dumps(msg))

    async def _login_ws(self) -> bool:
        """Login via WebSocket."""
        try:
            # Send login request
            login_msg = {
                "msg": "method",
                "method": "login",
                "id": self._next_id(),
                "params": [{
                    "user": {"username": self.username},
                    "password": {
                        "digest": hashlib.sha256(self.password.encode()).hexdigest(),
                        "algorithm": "sha-256"
                    }
                }]
            }
            await self._send_ws(login_msg)
            logger.info("{}: sent login request", self.name)
            return True
        except Exception as e:
            logger.error("{}: login failed: {}", self.name, e)
            return False

    async def start(self) -> None:
        """Start WebSocket connection."""
        self._running = True
        logger.info("{}: connecting to {}", self.name, self.ws_url)

        while self._running:
            try:
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=25,
                    ping_timeout=10,
                ) as ws:
                    self.ws = ws

                    # Send connect message
                    await self._send_ws({
                        "msg": "connect",
                        "version": "1",
                        "support": ["1"]
                    })

                    # Login and wait for result
                    await self._login_ws()
                    if not await self._wait_for_login(ws, timeout=15):
                        logger.warning("{}: login failed, will retry in 10s", self.name)
                        await asyncio.sleep(10)
                        continue

                    # Subscribe to DMs
                    await self._send_ws({
                        "msg": "sub",
                        "id": self._next_id(),
                        "name": "stream-room-messages",
                        "params": ["__my_messages__", False]
                    })

                    # Subscribe to all joined rooms (general, etc.)
                    await self._subscribe_joined_rooms()

                    # Start Rocket.Chat-level ping task
                    ping_task = asyncio.create_task(self._rc_ping_loop())

                    try:
                        # Receive messages
                        async for message in ws:
                            await self._handle_ws_message(message)
                    finally:
                        ping_task.cancel()

            except Exception as e:
                logger.error("{}: WebSocket error: {}", self.name, e)
                await asyncio.sleep(5)

    async def _wait_for_login(self, ws, timeout: float = 15) -> bool:
        """Consume messages until we get the login result or timeout."""
        import asyncio
        try:
            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                data = json.loads(raw)
                msg_type = data.get("msg")

                if msg_type == "connected":
                    logger.info("{}: WebSocket connected", self.name)
                elif msg_type == "ping":
                    await self._send_ws({"msg": "pong"})
                elif msg_type == "result":
                    if "result" in data and "token" in data["result"]:
                        self.auth_token = data["result"]["token"]
                        self.user_id = data["result"]["id"]
                        logger.info("{}: logged in as {}", self.name, self.username)
                        return True
                    elif "error" in data:
                        logger.warning("{}: login error: {}", self.name, data["error"])
                        return False
        except asyncio.TimeoutError:
            logger.warning("{}: login timeout", self.name)
        return False

    async def _subscribe_joined_rooms(self):
        """Subscribe to messages in all rooms the agent has joined (e.g. general)."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.base_url}/api/v1/channels.list.joined?count=50",
                    headers={
                        "X-Auth-Token": self.auth_token,
                        "X-User-Id": self.user_id,
                    },
                    timeout=10,
                )
                if resp.status_code != 200:
                    return
                channels = resp.json().get("channels", [])
                for ch in channels:
                    rid = ch["_id"]
                    await self._send_ws({
                        "msg": "sub",
                        "id": self._next_id(),
                        "name": "stream-room-messages",
                        "params": [rid, False]
                    })
                    logger.info("{}: subscribed to #{}", self.name, ch.get("name", rid))
        except Exception as e:
            logger.warning("{}: failed to subscribe to joined rooms: {}", self.name, e)

    async def _rc_ping_loop(self):
        """Send Rocket.Chat DDP-level pings to keep the connection alive."""
        while self._running:
            try:
                await asyncio.sleep(25)
                await self._send_ws({"msg": "ping"})
            except Exception:
                break

    async def _handle_ws_message(self, raw_msg: str):
        """Handle incoming WebSocket message (post-login: only pings and new messages)."""
        try:
            data = json.loads(raw_msg)
            msg_type = data.get("msg")

            if msg_type == "ping":
                await self._send_ws({"msg": "pong"})

            elif msg_type == "changed":
                # New message event
                fields = data.get("fields", {})
                args = fields.get("args", [])
                if args:
                    msg_data = args[0]
                    msg_id = msg_data.get("_id", "")
                    # Dedup: skip if already seen or sent by self
                    if msg_id in self._seen_msg_ids:
                        return
                    self._seen_msg_ids.add(msg_id)
                    # Cap dedup set size
                    if len(self._seen_msg_ids) > 500:
                        self._seen_msg_ids = set(list(self._seen_msg_ids)[-200:])

                    if msg_data.get("u", {}).get("_id") != self.user_id:
                        await self._handle_message(
                            msg_data["u"]["_id"],
                            msg_data["rid"],
                            msg_data["msg"]
                        )
                        logger.info("{}: received message from {}", self.name, msg_data["u"]["username"])

        except Exception as e:
            logger.error("{}: handle message error: {}", self.name, e)

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
        if self.ws:
            await self.ws.close()
