"""User sandbox with trajectory recording."""

import asyncio
from loguru import logger

from orchestrator.trajectory import TrajectoryRecorder


class UserSandbox:
    """User sandbox that interacts with agent via Rocket.Chat."""

    def __init__(self, recorder: TrajectoryRecorder, rocketchat_url: str, username: str, password: str):
        self.recorder = recorder
        self.rocketchat_url = rocketchat_url
        self.username = username
        self.password = password
        self.auth_token = None
        self.user_id = None

    async def login(self):
        """Login to Rocket.Chat."""
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.rocketchat_url}/api/v1/login",
                json={"user": self.username, "password": self.password}
            )
            data = resp.json()["data"]
            self.auth_token = data["authToken"]
            self.user_id = data["userId"]

        logger.info(f"User sandbox logged in as {self.username}")

    async def send_message(self, target_username: str, message: str):
        """Send message to another user and record the action."""
        import httpx

        # Record user action
        self.recorder.record_user_action("send_message", {
            "target": target_username,
            "message": message,
            "channel": "rocketchat"
        })

        headers = {
            "X-Auth-Token": self.auth_token,
            "X-User-Id": self.user_id
        }

        async with httpx.AsyncClient() as client:
            # Create DM
            resp = await client.post(
                f"{self.rocketchat_url}/api/v1/im.create",
                json={"username": target_username},
                headers=headers
            )
            room_id = resp.json()["room"]["_id"]

            # Send message
            await client.post(
                f"{self.rocketchat_url}/api/v1/chat.sendMessage",
                headers=headers,
                json={"message": {"rid": room_id, "msg": message}}
            )

        logger.info(f"User sent: {message}")

    async def send_email(self, to_address: str, subject: str, body: str):
        """Send email and record the action."""
        import aiosmtplib
        from email.mime.text import MIMEText

        # Record user action
        self.recorder.record_user_action("send_email", {
            "to": to_address,
            "subject": subject,
            "body": body
        })

        email_msg = MIMEText(body)
        email_msg["Subject"] = subject
        email_msg["From"] = f"{self.username}@ase.local"
        email_msg["To"] = to_address

        await aiosmtplib.send(
            email_msg,
            hostname="localhost",
            port=1587,
            username=f"{self.username}@ase.local",
            password=self.password
        )

        logger.info(f"User sent email to {to_address}")


