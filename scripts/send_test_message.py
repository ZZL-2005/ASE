"""Send test message to Rocket.Chat."""

import requests

BASE_URL = "http://localhost:3001"

# Login as agent
login_data = {
    "user": "agent",
    "password": "agent_pass_2026"
}

resp = requests.post(f"{BASE_URL}/api/v1/login", json=login_data)
if resp.status_code != 200:
    print(f"Login failed: {resp.status_code}")
    exit(1)

auth = resp.json()["data"]
headers = {
    "X-Auth-Token": auth["authToken"],
    "X-User-Id": auth["userId"]
}

# Get or create a DM with self
resp = requests.post(
    f"{BASE_URL}/api/v1/im.create",
    json={"username": "agent"},
    headers=headers
)

if resp.status_code == 200:
    room_id = resp.json()["room"]["_id"]
    print(f"Room ID: {room_id}")

    # Send test message
    resp = requests.post(
        f"{BASE_URL}/api/v1/chat.sendMessage",
        headers=headers,
        json={"message": {"rid": room_id, "msg": "Hello from test!"}}
    )

    if resp.status_code == 200:
        print("✓ Test message sent!")
    else:
        print(f"Send failed: {resp.status_code}")
else:
    print(f"Room creation failed: {resp.status_code}")
