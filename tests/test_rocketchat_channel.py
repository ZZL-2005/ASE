"""Test Rocket.Chat channel."""
import asyncio
from agent.bus.queue import MessageBus
from agent.channels.rocketchat_simple import RocketChatChannel


class Config:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


async def test_login():
    """Test Rocket.Chat login."""
    bus = MessageBus()
    config = Config(
        base_url="http://localhost:3001",
        username="testuser",
        password="test_pass_2026"
    )
    channel = RocketChatChannel(config, bus)
    
    success = await channel._login()
    assert success, "Login failed"
    assert channel.auth_token is not None
    assert channel.user_id is not None
    
    print("✓ Login test passed")


async def test_polling():
    """Test message polling."""
    bus = MessageBus()
    config = Config(
        base_url="http://localhost:3001",
        username="testuser",
        password="test_pass_2026"
    )
    channel = RocketChatChannel(config, bus)
    
    await channel._login()
    
    # Poll once
    await channel._poll_messages()
    
    print("✓ Polling test passed")


async def main():
    print("Testing Rocket.Chat Channel...")
    await test_login()
    await test_polling()
    print("\n✅ All Rocket.Chat channel tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
