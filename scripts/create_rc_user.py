#!/usr/bin/env python3
"""Create a new Rocket.Chat user account."""

import requests
import sys

BASE_URL = "http://localhost:3001"

# Login as admin
resp = requests.post(f"{BASE_URL}/api/v1/login", json={"user": "aseadmin", "password": "admin_pass_2026"})
if resp.status_code != 200:
    print(f"Admin login failed: {resp.status_code}")
    sys.exit(1)

auth = resp.json()["data"]
headers = {"X-Auth-Token": auth["authToken"], "X-User-Id": auth["userId"]}

# Get username and password
username = sys.argv[1] if len(sys.argv) > 1 else input("Username: ")
password = sys.argv[2] if len(sys.argv) > 2 else input("Password: ")
email = f"{username}@ase.local"
name = username.capitalize()

# Create user
resp = requests.post(
    f"{BASE_URL}/api/v1/users.create",
    headers=headers,
    json={
        "username": username,
        "email": email,
        "password": password,
        "name": name
    }
)

if resp.status_code == 200:
    print(f"✓ User created: {username}")
    print(f"  Email: {email}")
    print(f"  Password: {password}")
    print(f"\nYou can now login at: {BASE_URL}")
else:
    result = resp.json()
    if "already in use" in str(result):
        print(f"✓ User '{username}' already exists, you can login directly")
    else:
        print(f"✗ Failed: {result}")
