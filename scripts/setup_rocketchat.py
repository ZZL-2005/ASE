#!/usr/bin/env python3
"""Initialize Rocket.Chat with test accounts."""

import httpx
import time
from loguru import logger


def setup_rocketchat():
    """Setup Rocket.Chat with admin and test users."""
    base_url = "http://localhost:3001"

    # Wait for Rocket.Chat to be ready
    logger.info("Waiting for Rocket.Chat...")
    for i in range(30):
        try:
            resp = httpx.get(f"{base_url}/api/info", timeout=5)
            if resp.status_code == 200:
                logger.info("Rocket.Chat is ready")
                break
        except:
            pass
        time.sleep(2)

    # Setup admin user
    logger.info("Setting up admin user...")
    try:
        resp = httpx.post(
            f"{base_url}/api/v1/setup/wizard",
            json={
                "username": "admin",
                "email": "admin@ase.local",
                "password": "admin_pass_2026",
                "name": "Admin"
            },
            timeout=10
        )
        logger.info(f"Admin setup: {resp.status_code}")
    except Exception as e:
        logger.warning(f"Admin setup failed (may already exist): {e}")

    # Login as admin
    logger.info("Logging in as admin...")
    resp = httpx.post(
        f"{base_url}/api/v1/login",
        json={"user": "admin", "password": "admin_pass_2026"}
    )

    if resp.status_code != 200:
        logger.error("Admin login failed")
        return False

    data = resp.json()
    auth_token = data["data"]["authToken"]
    user_id = data["data"]["userId"]
    headers = {
        "X-Auth-Token": auth_token,
        "X-User-Id": user_id
    }

    # Create testuser
    logger.info("Creating testuser...")
    resp = httpx.post(
        f"{base_url}/api/v1/users.create",
        headers=headers,
        json={
            "username": "testuser",
            "email": "testuser@ase.local",
            "password": "test_pass_2026",
            "name": "Test User"
        }
    )
    logger.info(f"testuser created: {resp.status_code}")

    logger.info("Rocket.Chat setup complete!")
    return True


if __name__ == "__main__":
    setup_rocketchat()
