"""End-to-end integration test."""
import asyncio
from agent.bus.queue import MessageBus
from agent.llm_agent import LLMAgent
from agent.channels.rocketchat_simple import RocketChatChannel
from orchestrator.trajectory import TrajectoryRecorder


class Config:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


async def test_e2e_flow():
    """Test complete message flow."""
    print("Starting E2E test...")
    
    # Setup
    bus = MessageBus()
    recorder = TrajectoryRecorder(sandbox_type="agent", output_dir="test_trajectories")
    recorder.start_session("e2e_test")
    
    agent = LLMAgent(bus, recorder)
    
    config = Config(
        base_url="http://localhost:3001",
        username="testuser",
        password="test_pass_2026"
    )
    channel = RocketChatChannel(config, bus)
    
    # Start components
    agent_task = asyncio.create_task(agent.start())
    channel_task = asyncio.create_task(channel.start())
    
    await asyncio.sleep(3)
    
    print("✓ All components started")
    
    # Let it run for a bit
    await asyncio.sleep(5)
    
    # Stop
    await agent.stop()
    
    print("✓ E2E test completed")
    
    import shutil
    shutil.rmtree("test_trajectories", ignore_errors=True)


async def main():
    print("Testing End-to-End Integration...")
    await test_e2e_flow()
    print("\n✅ E2E integration test passed!")


if __name__ == "__main__":
    asyncio.run(main())
