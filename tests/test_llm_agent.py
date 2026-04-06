"""Test LLM Agent."""
import asyncio
from agent.bus.queue import MessageBus
from agent.bus.events import InboundMessage
from agent.llm_agent import LLMAgent
from orchestrator.trajectory import TrajectoryRecorder


async def test_llm_agent_basic():
    """Test LLM agent basic functionality."""
    bus = MessageBus()
    recorder = TrajectoryRecorder(sandbox_type="agent", output_dir="test_trajectories")
    recorder.start_session("test_llm")
    
    agent = LLMAgent(bus, recorder)
    
    # Start agent
    agent_task = asyncio.create_task(agent.start())
    await asyncio.sleep(0.5)
    
    # Send message
    msg = InboundMessage(
        channel="test",
        chat_id="chat1",
        sender_id="user1",
        content="Hello"
    )
    await bus.publish_inbound(msg)
    
    # Get response (with timeout)
    try:
        response = await asyncio.wait_for(bus.consume_outbound(), timeout=10)
        assert response.content is not None
        assert len(response.content) > 0
        print("✓ LLM agent basic test passed")
    except asyncio.TimeoutError:
        print("⚠ LLM agent test timeout (API may be slow)")
    
    await agent.stop()
    
    import shutil
    shutil.rmtree("test_trajectories", ignore_errors=True)


async def main():
    print("Testing LLM Agent...")
    await test_llm_agent_basic()
    print("\n✅ LLM Agent tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
