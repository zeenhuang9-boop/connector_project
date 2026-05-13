"""
Gemini Client — Google Gemini API wrapper (free tier).
"""
import json
import os
from pathlib import Path
import httpx
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


class GeminiClient:
    def __init__(self, model: str = "gemini-2.5-flash", system_prompt: str = ""):
        proxy_url = os.getenv("GEMINI_PROXY", "")
        http_client = httpx.Client(proxy=proxy_url) if proxy_url else None

        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY"),
            http_options={"httpx_client": http_client} if http_client else None,
        )
        self.model = model
        self.system_prompt = system_prompt
        self.history: list[types.Content] = []

    def chat(self, message: str) -> str:
        config = None
        if self.system_prompt:
            config = types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                temperature=0.3,
            )

        self.history.append(types.Content(
            role="user",
            parts=[types.Part(text=message)],
        ))

        response = self.client.models.generate_content(
            model=self.model,
            contents=self.history,
            config=config,
        )
        reply = response.text or ""

        self.history.append(types.Content(
            role="model",
            parts=[types.Part(text=reply)],
        ))
        return reply

    def clear_context(self):
        self.history = []

    def get_history(self) -> list[dict]:
        return [h.model_dump() for h in self.history]

    def save_context(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.get_history(), f, ensure_ascii=False, indent=2)

    def load_context(self, filepath: str):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.history = [types.Content(**item) for item in data]
