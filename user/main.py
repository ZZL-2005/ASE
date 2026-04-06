"""User sandbox main entry."""

import asyncio
from orchestrator.trajectory import TrajectoryRecorder
from user.sandbox import UserSandbox


async def main():
    """Run user sandbox."""
    recorder = TrajectoryRecorder(sandbox_type="user")

    user = UserSandbox(
        recorder=recorder,
        rocketchat_url="http://localhost:3001",
        username="testuser",
        password="test_pass_2026"
    )

    await user.login()

    # Example: send message to agent
    await user.send_message("agent", "Hello from user sandbox!")

    # Save trajectory
    recorder.save_session()


if __name__ == "__main__":
    asyncio.run(main())
