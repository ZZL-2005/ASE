"""State recovery example."""

import asyncio
from orchestrator.recovery import StateRecovery
from user.sandbox import UserSandbox
from agent.replay_agent import ReplayAgent
from agent.bus.queue import MessageBus
from orchestrator.trajectory import TrajectoryRecorder


async def main():
    """Example: recover state from trajectories."""
    recovery = StateRecovery()

    # Load session
    session_id = "20260402_001234"  # Replace with actual session ID

    # Get state at step 10
    state = recovery.get_state_at_step(session_id, step=10)

    print(f"State at step {state['step']}:")
    print(f"Total events: {state['total_events']}")
    print(f"Summary: {state['summary']}")

    if state['last_event']:
        print(f"Last event: {state['last_event']['type']}")

    # Replay events
    print("\nReplaying events...")
    events = recovery.replay_to_step(session_id, step=10)

    # Create agent sandbox
    bus = MessageBus()
    agent_recorder = TrajectoryRecorder(sandbox_type="agent")
    agent = ReplayAgent(bus=bus, recorder=agent_recorder)

    # Create user sandbox
    user_recorder = TrajectoryRecorder(sandbox_type="user")
    user_sandbox = UserSandbox(
        recorder=user_recorder,
        rocketchat_url="http://localhost:3001",
        username="testuser",
        password="test_pass_2026"
    )

    await user_sandbox.login()
    await recovery.replay_events(events, agent_sandbox=agent, user_sandbox=user_sandbox)
    print("Replay complete!")


if __name__ == "__main__":
    asyncio.run(main())
