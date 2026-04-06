"""Test User Sandbox."""
import asyncio
from user.sandbox import UserSandbox
from orchestrator.trajectory import TrajectoryRecorder


async def test_user_sandbox_init():
    """Test user sandbox initialization."""
    recorder = TrajectoryRecorder(sandbox_type="user", output_dir="test_trajectories")
    
    user = UserSandbox(
        recorder=recorder,
        rocketchat_url="http://localhost:3001",
        username="testuser",
        password="test_pass_2026"
    )
    
    await user.login()
    assert user.auth_token is not None
    
    print("✓ User sandbox init test passed")
    
    import shutil
    shutil.rmtree("test_trajectories", ignore_errors=True)


async def main():
    print("Testing User Sandbox...")
    await test_user_sandbox_init()
    print("\n✅ All User Sandbox tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
