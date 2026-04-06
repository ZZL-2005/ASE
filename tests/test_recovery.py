"""Test state recovery."""
import json
from pathlib import Path
from orchestrator.recovery import StateRecovery
from orchestrator.trajectory import TrajectoryRecorder


def test_load_trajectories():
    """Test loading trajectories."""
    # Create test trajectories
    Path("test_trajectories").mkdir(exist_ok=True)
    
    # Agent trajectory
    with open("test_trajectories/agent_test123.jsonl", "w") as f:
        f.write(json.dumps({"timestamp": "2026-01-01T00:00:00", "type": "llm.call", "data": {}}) + "\n")
    
    # User trajectory
    with open("test_trajectories/user_test123.jsonl", "w") as f:
        f.write(json.dumps({"timestamp": "2026-01-01T00:00:01", "type": "user.action", "data": {}}) + "\n")
    
    recovery = StateRecovery(trajectory_dir="test_trajectories")
    trajectories = recovery.load_trajectories("test123")
    
    assert len(trajectories["agent"]) == 1
    assert len(trajectories["user"]) == 1
    
    print("✓ Load trajectories test passed")
    
    import shutil
    shutil.rmtree("test_trajectories")


def test_merge_trajectories():
    """Test merging trajectories."""
    trajectories = {
        "agent": [
            {"timestamp": "2026-01-01T00:00:02", "type": "llm.call"}
        ],
        "user": [
            {"timestamp": "2026-01-01T00:00:01", "type": "user.action"}
        ]
    }
    
    recovery = StateRecovery()
    merged = recovery.merge_trajectories(trajectories)
    
    assert len(merged) == 2
    assert merged[0]["type"] == "user.action"
    assert merged[1]["type"] == "llm.call"
    
    print("✓ Merge trajectories test passed")


def test_get_state():
    """Test getting state at step."""
    Path("test_trajectories").mkdir(exist_ok=True)
    
    with open("test_trajectories/agent_test456.jsonl", "w") as f:
        for i in range(5):
            f.write(json.dumps({"timestamp": f"2026-01-01T00:00:0{i}", "type": "llm.call"}) + "\n")
    
    recovery = StateRecovery(trajectory_dir="test_trajectories")
    state = recovery.get_state_at_step("test456", step=3)
    
    assert state["step"] == 3
    assert state["total_events"] == 3
    
    print("✓ Get state test passed")
    
    import shutil
    shutil.rmtree("test_trajectories")


if __name__ == "__main__":
    print("Testing State Recovery...")
    test_load_trajectories()
    test_merge_trajectories()
    test_get_state()
    print("\n✅ All recovery tests passed!")
