"""Test trajectory recording."""
import json
from pathlib import Path
from orchestrator.trajectory import TrajectoryRecorder


def test_llm_call_recording():
    """Test LLM call recording."""
    recorder = TrajectoryRecorder(sandbox_type="agent", output_dir="test_trajectories")
    recorder.start_session("test_session")
    
    recorder.record_llm_call(
        prompt="What is 2+2?",
        response="4",
        model="gpt-4o"
    )
    
    recorder.save_session()
    
    files = list(Path("test_trajectories").glob("agent_*.jsonl"))
    assert len(files) == 1
    
    with open(files[0]) as f:
        event = json.loads(f.readline())
        assert event["type"] == "llm.call"
        assert event["data"]["prompt"] == "What is 2+2?"
    
    print("✓ LLM call recording test passed")
    
    import shutil
    shutil.rmtree("test_trajectories")


def test_tool_call_recording():
    """Test tool call recording."""
    recorder = TrajectoryRecorder(sandbox_type="agent", output_dir="test_trajectories")
    recorder.start_session("test_session")
    
    recorder.record_tool_call(
        tool_name="search",
        params={"query": "test"},
        result={"results": []}
    )
    
    recorder.save_session()
    
    files = list(Path("test_trajectories").glob("agent_*.jsonl"))
    with open(files[0]) as f:
        event = json.loads(f.readline())
        assert event["type"] == "tool.call"
        assert event["data"]["tool"] == "search"
    
    print("✓ Tool call recording test passed")
    
    import shutil
    shutil.rmtree("test_trajectories")


def test_user_action_recording():
    """Test user action recording."""
    recorder = TrajectoryRecorder(sandbox_type="user", output_dir="test_trajectories")
    recorder.start_session("test_session")
    
    recorder.record_user_action(
        action_type="send_message",
        details={"target": "agent", "message": "Hi"}
    )
    
    recorder.save_session()
    
    files = list(Path("test_trajectories").glob("user_*.jsonl"))
    with open(files[0]) as f:
        event = json.loads(f.readline())
        assert event["type"] == "user.action"
        assert event["data"]["action_type"] == "send_message"
    
    print("✓ User action recording test passed")
    
    import shutil
    shutil.rmtree("test_trajectories")


def test_multiple_events():
    """Test recording multiple events."""
    recorder = TrajectoryRecorder(sandbox_type="agent", output_dir="test_trajectories")
    recorder.start_session("test_session")
    
    recorder.record_llm_call("Q1", "A1", "gpt-4o")
    recorder.record_tool_call("tool1", {}, {})
    recorder.record_llm_call("Q2", "A2", "gpt-4o")
    
    recorder.save_session()
    
    files = list(Path("test_trajectories").glob("agent_*.jsonl"))
    with open(files[0]) as f:
        events = [json.loads(line) for line in f]
        assert len(events) == 3
    
    print("✓ Multiple events test passed")
    
    import shutil
    shutil.rmtree("test_trajectories")


if __name__ == "__main__":
    print("Testing Trajectory Recording...")
    test_llm_call_recording()
    test_tool_call_recording()
    test_user_action_recording()
    test_multiple_events()
    print("\n✅ All trajectory tests passed!")
