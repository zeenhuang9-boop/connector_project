"""
Codex Client — OpenAI API wrapper for Claude <-> Codex collaboration.
"""
import json
import os
from pathlib import Path
import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def _create_http_client() -> httpx.Client | None:
    proxy_url = os.getenv("OPENAI_PROXY", "")
    if proxy_url:
        return httpx.Client(proxy=proxy_url)
    return None


class CodexClient:
    def __init__(self, model: str = "gpt-4o", system_prompt: str = ""):
        http_client = _create_http_client()
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            http_client=http_client,
        )
        self.model = model
        self.system_prompt = system_prompt
        self.history: list[dict] = []
        if system_prompt:
            self.history.append({"role": "system", "content": system_prompt})

    def chat(self, message: str, role: str = "user") -> str:
        self.history.append({"role": role, "content": message})
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.history,
            temperature=0.3,
        )
        reply = response.choices[0].message.content or ""
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def clear_context(self):
        self.history = []
        if self.system_prompt:
            self.history.append({"role": "system", "content": self.system_prompt})

    def get_history(self) -> list[dict]:
        return list(self.history)

    def save_context(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def load_context(self, filepath: str):
        with open(filepath, "r", encoding="utf-8") as f:
            self.history = json.load(f)
