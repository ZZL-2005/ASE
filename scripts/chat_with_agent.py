#!/usr/bin/env python3
"""Chat with agent via Rocket.Chat."""
import asyncio
import httpx


async def send_message(url, token, user_id, room_id, message):
    """Send message to Rocket.Chat."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{url}/api/v1/chat.postMessage",
            headers={
                "X-Auth-Token": token,
                "X-User-Id": user_id
            },
            json={"roomId": room_id, "text": message}
        )
        return resp.json()


async def get_messages(url, token, user_id, room_id):
    """Get recent messages."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{url}/api/v1/channels.messages",
            headers={
                "X-Auth-Token": token,
                "X-User-Id": user_id
            },
            params={"roomId": room_id, "count": 5}
        )
        return resp.json()


async def main():
    url = "http://localhost:3001"
    username = "testuser"
    password = "test_pass_2026"
    
    # Login
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{url}/api/v1/login",
            json={"user": username, "password": password}
        )
        data = resp.json()
        token = data["data"]["authToken"]
        user_id = data["data"]["userId"]
    
    # Get GENERAL room
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{url}/api/v1/channels.list",
            headers={"X-Auth-Token": token, "X-User-Id": user_id}
        )
        channels = resp.json()["channels"]
        general = [c for c in channels if c["name"] == "general"][0]
        room_id = general["_id"]
    
    print("Connected! Type your messages (Ctrl+C to exit):")
    print("-" * 50)
    
    try:
        while True:
            message = input("You: ")
            if message.strip():
                await send_message(url, token, user_id, room_id, message)
                
                # Wait for response
                await asyncio.sleep(3)
                
                # Get messages
                msgs = await get_messages(url, token, user_id, room_id)
                for msg in msgs["messages"][:2]:
                    if msg["u"]["username"] == "testuser":
                        print(f"Agent: {msg['msg']}")
                        break
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    asyncio.run(main())
