"""Model interface — all communication with the LLM goes through here."""

from __future__ import annotations

import httpx

from .config import get_config


async def ask(system_prompt: str, user_message: str) -> str:
    """Single-turn call: system + user -> text response."""
    cfg = get_config()
    payload = {
        "model": cfg.model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.0,
    }
    async with httpx.AsyncClient(timeout=cfg.model_timeout) as client:
        resp = await client.post(cfg.model_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


async def chat(messages: list, tools: list | None = None) -> dict:
    """Multi-turn call with optional tool definitions. Returns raw API response."""
    cfg = get_config()
    payload = {
        "model": cfg.model_name,
        "messages": messages,
        "temperature": 0.0,
    }

    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=cfg.model_timeout) as client:
        resp = await client.post(cfg.model_url, json=payload)

        if resp.status_code != 200:
            print(f"\n[HTTP ERROR] {resp.status_code}: {resp.text}\n")

        resp.raise_for_status()
        return resp.json()
