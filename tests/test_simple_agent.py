"""Test SimpleAgent functionality."""
import asyncio
from agent.bus.queue import MessageBus
from agent.bus.events import InboundMessage
from agent.simple_agent import SimpleAgent


async def test_echo_response():
    """Test agent echo response."""
    bus = MessageBus()
    agent = SimpleAgent(bus)
    
    # Start agent
    agent_task = asyncio.create_task(agent.start())
    await asyncio.sleep(0.5)
    
    # Send message
    msg = InboundMessage(
        channel="test",
        chat_id="chat1",
        sender_id="user1",
        content="Test message"
    )
    await bus.publish_inbound(msg)
    
    # Get response
    response = await bus.consume_outbound()
    assert response.content == "Echo: Test message"
    assert response.chat_id == "chat1"
    
    await agent.stop()
    print("✓ Echo response test passed")


async def test_multiple_messages():
    """Test multiple message handling."""
    bus = MessageBus()
    agent = SimpleAgent(bus)
    
    agent_task = asyncio.create_task(agent.start())
    await asyncio.sleep(0.5)
    
    # Send 3 messages
    for i in range(3):
        msg = InboundMessage(
            channel="test",
            chat_id="chat1",
            sender_id="user1",
            content=f"Message {i}"
        )
        await bus.publish_inbound(msg)
    
    # Check responses
    for i in range(3):
        response = await bus.consume_outbound()
        assert response.content == f"Echo: Message {i}"
    
    await agent.stop()
    print("✓ Multiple messages test passed")


async def main():
    print("Testing SimpleAgent...")
    await test_echo_response()
    await test_multiple_messages()
    print("\n✅ All SimpleAgent tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
