"""Interactive user sandbox."""

import asyncio
from orchestrator.trajectory import TrajectoryRecorder
from user.sandbox import UserSandbox


async def interactive_mode():
    """Interactive chat with agent."""
    recorder = TrajectoryRecorder(sandbox_type="user")

    user = UserSandbox(
        recorder=recorder,
        rocketchat_url="http://localhost:3001",
        username="testuser",
        password="test_pass_2026"
    )

    await user.login()
    print("Connected! Type your messages (Ctrl+C to exit):")

    try:
        while True:
            message = input("> ")
            if message.strip():
                await user.send_message("agent", message)
    except KeyboardInterrupt:
        print("\nSaving trajectory...")
        recorder.save_session()
        print("Goodbye!")


if __name__ == "__main__":
    asyncio.run(interactive_mode())
