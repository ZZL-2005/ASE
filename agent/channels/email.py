"""Email channel implementation using IMAP and SMTP."""

import asyncio
import email
from email.mime.text import MIMEText
from typing import Any

import aiosmtplib
from aioimaplib import aioimaplib
from loguru import logger

from agent.bus.events import OutboundMessage
from agent.channels.base import BaseChannel


class EmailChannel(BaseChannel):
    """Email channel using IMAP for receiving and SMTP for sending."""

    name = "email"
    display_name = "Email"

    def __init__(self, config: Any, bus):
        super().__init__(config, bus)
        self.imap_host = getattr(config, "imap_host", "localhost")
        self.imap_port = getattr(config, "imap_port", 143)
        self.smtp_host = getattr(config, "smtp_host", "localhost")
        self.smtp_port = getattr(config, "smtp_port", 587)
        self.username = getattr(config, "username", "")
        self.password = getattr(config, "password", "")
        self.imap_client = None
        self._poll_task = None

    async def start(self) -> None:
        """Start IMAP polling for new emails."""
        self._running = True
        try:
            self.imap_client = aioimaplib.IMAP4(host=self.imap_host, port=self.imap_port)
            await self.imap_client.wait_hello_from_server()
            resp = await self.imap_client.login(self.username, self.password)
            logger.info("{}: IMAP login: {}", self.name, resp.result)
            resp = await self.imap_client.select("INBOX")
            logger.info("{}: INBOX selected: {}", self.name, resp.result)

            self._poll_task = asyncio.create_task(self._poll_loop())
            await self._poll_task
        except Exception as e:
            logger.error("{}: IMAP error: {}", self.name, e)
        finally:
            self._running = False

    async def _poll_loop(self) -> None:
        """Poll for new emails."""
        while self._running:
            try:
                await self._check_new_emails()
                await asyncio.sleep(5)
            except Exception as e:
                logger.error("{}: poll error: {}", self.name, e)
                await asyncio.sleep(10)

    async def _check_new_emails(self) -> None:
        """Check for unseen emails."""
        # Need to re-examine INBOX to see new messages
        await self.imap_client.select("INBOX")
        response = await self.imap_client.search("UNSEEN")
        if response.result != "OK":
            logger.warning("{}: IMAP search failed: {}", self.name, response.result)
            return

        # aioimaplib returns lines as list; first line has space-separated IDs
        raw = response.lines[0]
        if isinstance(raw, bytes):
            raw = raw.decode()
        raw = raw.strip()
        if not raw:
            return

        msg_ids = raw.split()
        logger.info("{}: found {} unseen email(s)", self.name, len(msg_ids))
        for msg_id in msg_ids:
            if msg_id:
                await self._process_email(msg_id)

    async def _process_email(self, msg_id: str) -> None:
        """Process a single email."""
        logger.info("{}: fetching email {}", self.name, msg_id)
        response = await self.imap_client.fetch(msg_id, "(RFC822)")
        if response.result != "OK":
            logger.warning("{}: fetch failed for {}: {}", self.name, msg_id, response.result)
            return

        # aioimaplib returns lines; find the one that contains the email body
        # The body can be bytes or bytearray
        email_body = None
        for line in response.lines:
            if isinstance(line, (bytes, bytearray)) and len(line) > 50:
                email_body = bytes(line)
                break

        if not email_body:
            logger.warning("{}: no email body found in fetch response", self.name)
            return

        msg = email.message_from_bytes(email_body)

        sender = msg.get("From", "")
        subject = msg.get("Subject", "")
        content = self._get_email_content(msg)

        logger.info("{}: processing email from {} subject '{}'", self.name, sender, subject)
        chat_id = sender  # Use sender as chat_id
        await self._handle_message(sender, chat_id, f"Subject: {subject}\n\n{content}")

    def _get_email_content(self, msg) -> str:
        """Extract text content from email."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode()
        else:
            return msg.get_payload(decode=True).decode()
        return ""

    async def send(self, msg: OutboundMessage) -> None:
        """Send email via SMTP."""
        try:
            email_msg = MIMEText(msg.content)
            email_msg["Subject"] = "Reply from Agent"
            email_msg["From"] = self.username
            email_msg["To"] = msg.chat_id

            await aiosmtplib.send(
                email_msg,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.username,
                password=self.password,
            )
        except Exception as e:
            logger.error("{}: send failed: {}", self.name, e)
            raise

    async def stop(self) -> None:
        """Stop the channel."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
        if self.imap_client:
            await self.imap_client.logout()

