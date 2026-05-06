import json
import os
from typing import AsyncIterator, Iterator
import httpx

OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3:8b")


def chat_stream(messages: list[dict], model: str = DEFAULT_MODEL) -> Iterator[str]:
    """Synchronous streaming chat — yields text chunks as they arrive."""
    with httpx.Client(timeout=120) as client:
        with client.stream(
            "POST",
            f"{OLLAMA_BASE}/api/chat",
            json={"model": model, "messages": messages, "stream": True},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
                if data.get("done"):
                    break


async def chat_stream_async(messages: list[dict], model: str = DEFAULT_MODEL) -> AsyncIterator[str]:
    """Async streaming chat — yields text chunks as they arrive."""
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{OLLAMA_BASE}/api/chat",
            json={"model": model, "messages": messages, "stream": True},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
                if data.get("done"):
                    break


def list_models() -> list[str]:
    with httpx.Client(timeout=10) as client:
        r = client.get(f"{OLLAMA_BASE}/api/tags")
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]


def is_ollama_running() -> bool:
    try:
        with httpx.Client(timeout=3) as client:
            client.get(f"{OLLAMA_BASE}/api/tags").raise_for_status()
        return True
    except Exception:
        return False
