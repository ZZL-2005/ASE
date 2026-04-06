"""LLM client for OpenAI-compatible APIs."""

import httpx
from typing import List, Dict, Optional
from loguru import logger


class LLMClient:
    """OpenAI-compatible LLM client."""

    def __init__(self, api_base: str, api_key: str, model: str, temperature: float = 0.7):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

    async def chat(self, messages: List[Dict[str, str]], tools: Optional[List] = None) -> str:
        """Send chat completion request."""
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature
        }

        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            logger.info(f"LLM response: {content[:100]}...")
            return content
