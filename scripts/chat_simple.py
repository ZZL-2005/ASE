#!/usr/bin/env python3
"""Simple script to chat with agent via Rocket.Chat."""

import requests
import sys
import time

BASE_URL = "http://localhost:3001"

# Login as testuser
resp = requests.post(f"{BASE_URL}/api/v1/login", json={"user": "testuser", "password": "test_pass_2026"})
auth = resp.json()["data"]
headers = {"X-Auth-Token": auth["authToken"], "X-User-Id": auth["userId"]}

# Get DM with agent
resp = requests.post(f"{BASE_URL}/api/v1/im.create", json={"username": "agent"}, headers=headers)
room_id = resp.json()["room"]["_id"]

# Send message
message = sys.argv[1] if len(sys.argv) > 1 else "Hello agent!"
resp = requests.post(
    f"{BASE_URL}/api/v1/chat.sendMessage",
    headers=headers,
    json={"message": {"rid": room_id, "msg": message}}
)

print(f"You: {message}")
print("Waiting for agent reply...")
time.sleep(6)

# Get reply
resp = requests.get(
    f"{BASE_URL}/api/v1/im.history",
    headers=headers,
    params={"roomId": room_id, "count": 3}
)
messages = resp.json().get("messages", [])
agent_msgs = [m for m in messages if m.get("u", {}).get("username") == "agent"]
if agent_msgs:
    print(f"\nAgent: {agent_msgs[0]['msg']}")
else:
    print("No reply yet")
