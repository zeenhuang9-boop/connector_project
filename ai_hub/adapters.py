"""AI Adapters — standardized wrappers around existing bridge clients."""
import json
from pathlib import Path

from bridge.gemini_client import GeminiClient
from bridge.codex_client import CodexClient
from .message import Message
from .security import TokenBucket

ROLES = {
    "architect": "You are a software architect. Design systems, choose patterns, define interfaces.",
    "coder": "You are an expert software engineer. Write clean, production-ready code with error handling.",
    "reviewer": "You are a code reviewer. Find bugs, suggest improvements, check for security issues.",
    "critic": "You are a constructive critic. Identify weaknesses and propose concrete improvements.",
    "moderator": "You are a discussion moderator. Synthesize viewpoints, resolve conflicts, guide toward consensus.",
}

ROOT = Path(__file__).parent.parent


class AIAdapter:
    def __init__(self, name: str, client, role: str = "coder", rate_limit: float = 1.0):
        self.name = name
        self.client = client
        self.role = role
        self.rate_limiter = TokenBucket(capacity=rate_limit * 10, refill_rate=rate_limit)
        if role in ROLES and hasattr(self.client, 'system_prompt'):
            self.client.system_prompt = ROLES[role]

    def set_role(self, role: str) -> None:
        self.role = role
        if role in ROLES and hasattr(self.client, 'system_prompt'):
            self.client.system_prompt = ROLES[role]

    def receive(self, msg: Message) -> Message:
        if not self.rate_limiter.consume():
            return Message(
                sender=self.name, recipient=msg.sender,
                content=f"[Rate limited] {self.name} is temporarily unavailable.",
                pattern="direct", role=self.role, thread_id=msg.thread_id,
            )
        try:
            response_text = self.client.chat(msg.to_prompt())
        except Exception as e:
            response_text = f"[Error calling {self.name} API: {e}]"
        return Message(
            sender=self.name, recipient=msg.sender,
            content=response_text, pattern="direct",
            role=self.role, thread_id=msg.thread_id,
        )

    def clear_context(self) -> None:
        self.client.clear_context()


class GeminiAdapter(AIAdapter):
    def __init__(self, name: str = "gemini", model: str | None = None,
                 role: str = "coder", rate_limit: float = 1.0):
        if model is None:
            model = _load_model("gemini", "gemini-2.5-flash")
        client = GeminiClient(model=model)
        super().__init__(name=name, client=client, role=role, rate_limit=rate_limit)


class CodexAdapter(AIAdapter):
    def __init__(self, name: str = "codex", model: str | None = None,
                 role: str = "coder", rate_limit: float = 1.0):
        if model is None:
            model = _load_model("codex", "gpt-4o")
        client = CodexClient(model=model)
        super().__init__(name=name, client=client, role=role, rate_limit=rate_limit)


def _load_model(key: str, default: str) -> str:
    config_path = ROOT / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f).get("agents", {}).get(key, {}).get("model", default)
    return default
