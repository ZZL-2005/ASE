"""Create test user and send message."""

import requests
import time

BASE_URL = "http://localhost:3001"

# Create test user
print("Creating test user...")
test_data = {
    "username": "testuser",
    "email": "test@ase.local",
    "pass": "test_pass_2026",
    "name": "Test User"
}

resp = requests.post(f"{BASE_URL}/api/v1/users.register", json=test_data)
print(f"User creation: {resp.status_code}")

# Login as test user
time.sleep(1)
resp = requests.post(f"{BASE_URL}/api/v1/login", json={"user": "testuser", "password": "test_pass_2026"})
if resp.status_code != 200:
    print(f"Login failed: {resp.status_code}")
    exit(1)

auth = resp.json()["data"]
headers = {"X-Auth-Token": auth["authToken"], "X-User-Id": auth["userId"]}

# Create DM with agent
resp = requests.post(f"{BASE_URL}/api/v1/im.create", json={"username": "agent"}, headers=headers)
room_id = resp.json()["room"]["_id"]
print(f"Room ID: {room_id}")

# Send message
resp = requests.post(
    f"{BASE_URL}/api/v1/chat.sendMessage",
    headers=headers,
    json={"message": {"rid": room_id, "msg": "Hello Agent!"}}
)

print(f"✓ Message sent: {resp.status_code}")
