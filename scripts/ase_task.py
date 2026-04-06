#!/usr/bin/env python3
"""ASE Task CLI — manage experiment tasks.

Usage:
    python scripts/ase_task.py create [--name NAME] [--mode interactive|simulated]
    python scripts/ase_task.py start TASK_ID
    python scripts/ase_task.py stop TASK_ID
    python scripts/ase_task.py destroy TASK_ID
    python scripts/ase_task.py list
    python scripts/ase_task.py status TASK_ID
    python scripts/ase_task.py logs TASK_ID [SERVICE] [--tail N]
    python scripts/ase_task.py monitor [TASK_ID...]
    python scripts/ase_task.py trajectories TASK_ID
    python scripts/ase_task.py stop-all
"""

import sys
import os
import json
import argparse

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from orchestrator.task_manager import TaskManager
from orchestrator.task import TaskConfig
from orchestrator.task_monitor import TaskMonitor, print_task_table
from orchestrator.recovery import StateRecovery


def main():
    parser = argparse.ArgumentParser(description="ASE Task Manager")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # create
    p_create = sub.add_parser("create", help="Create a new task")
    p_create.add_argument("--name", default="", help="Task name")
    p_create.add_argument("--mode", default="interactive", choices=["interactive", "simulated"],
                          help="User mode: interactive (human) or simulated (LLM)")
    p_create.add_argument("--model", default=None, help="LLM model override")
    p_create.add_argument("--api-base", default=None, help="LLM API base URL override")
    p_create.add_argument("--description", default="", help="Task description")

    # start
    p_start = sub.add_parser("start", help="Start a task")
    p_start.add_argument("task_id", help="Task ID")

    # stop
    p_stop = sub.add_parser("stop", help="Stop a task")
    p_stop.add_argument("task_id", help="Task ID")

    # destroy
    p_destroy = sub.add_parser("destroy", help="Destroy a task and its data")
    p_destroy.add_argument("task_id", help="Task ID")

    # list
    sub.add_parser("list", help="List all tasks")

    # status
    p_status = sub.add_parser("status", help="Show task status")
    p_status.add_argument("task_id", help="Task ID")

    # logs
    p_logs = sub.add_parser("logs", help="Show task logs")
    p_logs.add_argument("task_id", help="Task ID")
    p_logs.add_argument("service", nargs="?", default=None, help="Service name (agent, rocketchat, etc.)")
    p_logs.add_argument("--tail", type=int, default=50, help="Number of lines")

    # monitor
    p_monitor = sub.add_parser("monitor", help="Real-time log monitor")
    p_monitor.add_argument("task_ids", nargs="*", default=None, help="Task IDs to monitor (default: all running)")

    # trajectories
    p_traj = sub.add_parser("trajectories", help="Show task trajectories")
    p_traj.add_argument("task_id", help="Task ID")

    # stop-all
    sub.add_parser("stop-all", help="Stop all running tasks")

    # run (create + start shortcut)
    p_run = sub.add_parser("run", help="Create and start a task in one step")
    p_run.add_argument("--name", default="", help="Task name")
    p_run.add_argument("--mode", default="interactive", choices=["interactive", "simulated"])
    p_run.add_argument("--model", default=None, help="LLM model override")
    p_run.add_argument("--description", default="", help="Task description")

    # replay
    p_replay = sub.add_parser("replay", help="Execution-level replay: start new containers and replay to step N")
    p_replay.add_argument("task_id", help="Source task ID whose trajectory to replay")
    p_replay.add_argument("--step", type=int, default=None, help="Step to replay to (default: all)")
    p_replay.add_argument("--show", action="store_true", help="Only show trajectory (no execution)")

    # inspect (non-executing trajectory viewer, the old replay)
    p_inspect = sub.add_parser("inspect", help="Show trajectory events without executing")
    p_inspect.add_argument("task_id", help="Task ID")
    p_inspect.add_argument("--step", type=int, default=None, help="Step to show up to")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    mgr = TaskManager()

    if args.command == "create":
        llm_config = {}
        if args.model:
            llm_config["model"] = args.model
        if args.api_base:
            llm_config["api_base"] = args.api_base

        config = TaskConfig(
            name=args.name,
            user_mode=args.mode,
            llm_config=llm_config,
            description=args.description,
        )
        task = mgr.create_task(config)
        print(f"Created: {task.task_id}")
        print(f"  RC port: {task.ports['rocketchat']}")
        print(f"  Web port: {task.ports['web']}")
        print(f"\nTo start: python scripts/ase_task.py start {task.task_id}")

    elif args.command == "start":
        mgr.start_task(args.task_id)

    elif args.command == "stop":
        mgr.stop_task(args.task_id)

    elif args.command == "destroy":
        mgr.destroy_task(args.task_id)
        print(f"Destroyed: {args.task_id}")

    elif args.command == "list":
        tasks = mgr.list_tasks()
        print_task_table(tasks)

    elif args.command == "status":
        task = mgr.get_task(args.task_id)
        status = task.status()
        import json
        print(json.dumps(status, indent=2, default=str))

    elif args.command == "logs":
        task = mgr.get_task(args.task_id)
        logs = task.get_logs(service=args.service, tail=args.tail)
        print(logs)

    elif args.command == "monitor":
        monitor = TaskMonitor(mgr)
        task_ids = args.task_ids if args.task_ids else None
        monitor.start(task_ids=task_ids)

    elif args.command == "trajectories":
        task = mgr.get_task(args.task_id)
        trajs = task.get_trajectories()
        print(f"\nTrajectories for {args.task_id}:")
        for side, files in trajs.items():
            print(f"\n  {side}:")
            if files:
                for f in files:
                    import os
                    size = os.path.getsize(f)
                    lines = sum(1 for _ in open(f))
                    print(f"    {f.name} ({lines} events, {size} bytes)")
            else:
                print(f"    (none)")

    elif args.command == "stop-all":
        mgr.stop_all()
        print("All tasks stopped.")

    elif args.command == "run":
        llm_config = {}
        if args.model:
            llm_config["model"] = args.model

        config = TaskConfig(
            name=args.name,
            user_mode=args.mode,
            llm_config=llm_config,
            description=args.description,
        )
        task = mgr.create_task(config)
        print(f"Created: {task.task_id}")
        print(f"Starting...")
        mgr.start_task(task.task_id)

    elif args.command == "replay":
        if args.show:
            _show_trajectory(mgr, args.task_id, args.step)
            return
        _execute_replay(mgr, args.task_id, args.step)

    elif args.command == "inspect":
        _show_trajectory(mgr, args.task_id, args.step)


def _show_trajectory(mgr, task_id, step):
    """Display trajectory events (non-executing)."""
    task = mgr.get_task(task_id)
    recovery = StateRecovery.from_task_dir(str(task.task_dir))
    trajectories = recovery.load_trajectories()
    merged = recovery.merge_trajectories(trajectories)
    total = len(merged)

    if total == 0:
        print(f"No trajectory data found for {task_id}")
        return

    target = step if step else total
    if target > total:
        target = total

    print(f"\nTrajectory for {task_id}")
    print(f"Total events: {total}, showing to step: {target}")
    print("-" * 70)

    for i, event in enumerate(merged[:target]):
        ts = event["timestamp"]
        etype = event["type"]
        sandbox = event["sandbox"]
        data = event["data"]

        if etype == "llm.call":
            prompt_preview = data.get("prompt", "")[-60:]
            response_preview = data.get("response", "")[:60].strip()
            model = data.get("model", "?")
            usage = data.get("metadata", {}).get("usage", {})
            tokens = f"in={usage.get('prompt_tokens', '?')}, out={usage.get('completion_tokens', '?')}"
            print(f"  [{i+1}] {ts} | {sandbox}.{etype}")
            print(f"       model={model} ({tokens})")
            print(f"       prompt: ...{prompt_preview!r}")
            print(f"       response: {response_preview!r}")
        elif etype == "tool.call":
            tool = data.get("tool", data.get("tool_name", "?"))
            print(f"  [{i+1}] {ts} | {sandbox}.{etype}: {tool}")
        elif "message" in etype:
            content = data.get("content", "")[:60]
            print(f"  [{i+1}] {ts} | {sandbox}.{etype}: {content!r}")
        else:
            print(f"  [{i+1}] {ts} | {sandbox}.{etype}")
        print()

    state = recovery.get_state_at_step(target)
    s = state["summary"]
    print("-" * 70)
    print(f"State at step {target}: {s['llm_calls']} LLM, {s['tool_calls']} tool, {s['messages_sent']} msg, {s['user_actions']} user")


def _execute_replay(mgr, source_task_id, step):
    """Execution-level replay: start new containers and replay trajectory."""
    import shutil
    import time
    import httpx

    # 1. Load source trajectory
    source_task = mgr.get_task(source_task_id)
    recovery = StateRecovery.from_task_dir(str(source_task.task_dir))
    trajectories = recovery.load_trajectories()
    merged = recovery.merge_trajectories(trajectories)

    if not merged:
        print(f"No trajectory data found for {source_task_id}")
        return

    total = len(merged)
    target = step if step else total
    if target > total:
        target = total

    # Extract inbound messages to inject
    events_to_replay = merged[:target]
    inbound_messages = []
    for ev in events_to_replay:
        if ev["type"] == "message.inbound":
            data = ev["data"]
            content = data.get("content", "")
            chat_id = data.get("chat_id", "")
            # Strip Runtime Context prefix if present (old-style recording)
            if content.startswith("[Runtime Context"):
                parts = content.rsplit("\n\n", 1)
                content = parts[-1].strip() if len(parts) > 1 else content
            if content:
                inbound_messages.append({
                    "content": content,
                    "chat_id": chat_id,
                    "channel": data.get("channel", "rocketchat"),
                })

    if not inbound_messages:
        # Fallback: extract from llm.call prompts (trajectories without message.inbound)
        seen = set()
        for ev in events_to_replay:
            if ev["type"] == "llm.call":
                prompt = ev["data"].get("prompt", "")
                parts = prompt.rsplit("\n\n", 1)
                user_msg = parts[-1].strip() if len(parts) > 1 else ""
                if user_msg and user_msg not in seen:
                    seen.add(user_msg)
                    chat_id = ""
                    for line in prompt.split("\n"):
                        if line.startswith("Chat ID:"):
                            chat_id = line.split(":", 1)[1].strip()
                    inbound_messages.append({
                        "content": user_msg,
                        "chat_id": chat_id,
                        "channel": "rocketchat",
                    })

    print(f"\nExecution-level replay of {source_task_id} (step {target}/{total})")
    print(f"  Inbound messages to inject: {len(inbound_messages)}")

    # 2. Find source trajectory file
    traj_files = sorted((source_task.task_dir / "trajectories" / "agent").glob("*.jsonl"))
    if not traj_files:
        print("No agent trajectory file found")
        return
    source_traj_path = traj_files[-1]

    # 3. Create new task with replay config
    config = TaskConfig(
        name=f"replay-{source_task_id}",
        user_mode="interactive",
        llm_config=source_task.config.llm_config,
        replay_config={
            "trajectory_path": str(source_traj_path),
            "steps": target,
        },
    )
    replay_task = mgr.create_task(config)
    print(f"  Created replay task: {replay_task.task_id}")

    # Copy trajectory file into replay dir
    replay_dir = replay_task.task_dir / "replay"
    replay_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_traj_path, replay_dir / "source.jsonl")

    # 4. Start the replay task (containers + wait for RC)
    print(f"  Starting containers (this may take a few minutes)...")
    try:
        mgr.start_task(replay_task.task_id)
    except Exception as e:
        print(f"  Start failed: {e}")
        return

    rc_port = replay_task.ports["rocketchat"]
    rc_url = f"http://localhost:{rc_port}"
    print(f"  Rocket.Chat ready at {rc_url}")

    # 5. Login as testuser
    try:
        resp = httpx.post(f"{rc_url}/api/v1/login",
                          json={"user": "testuser", "password": "test_pass_2026"}, timeout=15)
        auth = resp.json()["data"]
        headers = {"X-Auth-Token": auth["authToken"], "X-User-Id": auth["userId"]}
    except Exception as e:
        print(f"  testuser login failed: {e}")
        return

    # 6. Inject inbound messages one by one
    print(f"\n  Injecting messages...")
    for i, msg in enumerate(inbound_messages):
        content = msg["content"]
        chat_id = msg.get("chat_id", "")

        # Determine target room
        if chat_id and chat_id != "GENERAL" and len(chat_id) > 10:
            # DM - create/get DM with agent
            try:
                dm_resp = httpx.post(f"{rc_url}/api/v1/im.create",
                                     headers=headers, json={"username": "agent"}, timeout=15)
                room_id = dm_resp.json()["room"]["rid"]
            except Exception:
                room_id = None
        else:
            # Channel message - use GENERAL
            room_id = "GENERAL"

        if not room_id:
            print(f"    [{i+1}] Skipped (no room): {content[:40]}")
            continue

        try:
            httpx.post(f"{rc_url}/api/v1/chat.sendMessage",
                       headers=headers,
                       json={"message": {"rid": room_id, "msg": content}},
                       timeout=15)
            print(f"    [{i+1}/{len(inbound_messages)}] Sent: {content[:50]}")
        except Exception as e:
            print(f"    [{i+1}] Send failed: {e}")
            continue

        # Wait for agent to process (agent in replay mode is fast, no real LLM call)
        time.sleep(3)

    print(f"\n{'='*60}")
    print(f"Replay complete!")
    print(f"  Task: {replay_task.task_id}")
    print(f"  Rocket.Chat: {rc_url}")
    print(f"  Login: testuser / test_pass_2026")
    print(f"  Web Env: http://localhost:{replay_task.ports['web']}")
    print(f"\nThe environment is now at step {target}. You can:")
    print(f"  - Open RC in browser to see replayed messages")
    print(f"  - Continue interacting with the agent (will use real LLM)")
    print(f"  - Stop: python scripts/ase_task.py stop {replay_task.task_id}")


if __name__ == "__main__":
    main()
