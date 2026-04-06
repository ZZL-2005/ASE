"""Simple test script for channels."""

import asyncio
from agent.bus.queue import MessageBus
from agent.channels.rocketchat import RocketChatChannel
from agent.channels.email import EmailChannel


class SimpleConfig:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


async def test_rocketchat():
    """Test Rocket.Chat channel."""
    print("Testing Rocket.Chat channel...")
    bus = MessageBus()

    config = SimpleConfig(
        base_url="http://localhost:3000",
        username="agent",
        password="agent_pass_2026",
        allow_from=["*"],
        streaming=False,
    )

    channel = RocketChatChannel(config, bus)

    try:
        # Test login
        if await channel._login():
            print("✓ Rocket.Chat login successful")
        else:
            print("✗ Rocket.Chat login failed")
    except Exception as e:
        print(f"✗ Rocket.Chat error: {e}")


async def test_email():
    """Test Email channel."""
    print("\nTesting Email channel...")
    # Email test will be added after mailserver is configured
    print("Email test skipped (needs account setup)")


async def main():
    await test_rocketchat()
    await test_email()


if __name__ == "__main__":
    asyncio.run(main())
