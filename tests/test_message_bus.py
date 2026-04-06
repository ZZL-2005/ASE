"""Test message bus functionality."""
import asyncio
from agent.bus.queue import MessageBus
from agent.bus.events import InboundMessage, OutboundMessage


async def test_inbound_queue():
    """Test inbound message queue."""
    bus = MessageBus()
    
    # Publish message
    msg = InboundMessage(
        channel="test",
        chat_id="chat1",
        sender_id="user1",
        content="Hello"
    )
    await bus.publish_inbound(msg)
    
    # Consume message
    received = await bus.consume_inbound()
    assert received.content == "Hello"
    assert received.sender_id == "user1"
    print("✓ Inbound queue test passed")


async def test_outbound_queue():
    """Test outbound message queue."""
    bus = MessageBus()
    
    # Publish message
    msg = OutboundMessage(
        channel="test",
        chat_id="chat1",
        content="Response"
    )
    await bus.publish_outbound(msg)
    
    # Consume message
    received = await bus.consume_outbound()
    assert received.content == "Response"
    print("✓ Outbound queue test passed")


async def test_multiple_messages():
    """Test multiple messages in queue."""
    bus = MessageBus()
    
    # Publish 3 messages
    for i in range(3):
        msg = InboundMessage(
            channel="test",
            chat_id="chat1",
            sender_id=f"user{i}",
            content=f"Message {i}"
        )
        await bus.publish_inbound(msg)
    
    # Consume all
    for i in range(3):
        received = await bus.consume_inbound()
        assert received.content == f"Message {i}"
    
    print("✓ Multiple messages test passed")


async def main():
    print("Testing Message Bus...")
    await test_inbound_queue()
    await test_outbound_queue()
    await test_multiple_messages()
    print("\n✅ All message bus tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
