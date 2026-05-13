"""Conversation management — threads with shared and private context."""
import time
import uuid
from dataclasses import dataclass, field

from .message import Message


@dataclass
class Thread:
    topic: str
    participants: set[str] = field(default_factory=set)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    history: list[Message] = field(default_factory=list)
    private_context: dict[str, dict] = field(default_factory=dict)
    max_history: int = 20
    created_at: float = field(default_factory=time.time)

    def to_summary(self) -> str:
        duration = time.time() - self.created_at
        mins = int(duration // 60)
        secs = int(duration % 60)
        return (
            f"Thread [{self.id}]: {self.topic}\n"
            f"  Participants: {', '.join(sorted(self.participants))}\n"
            f"  Messages: {len(self.history)}\n"
            f"  Duration: {mins}m {secs}s"
        )


class ConversationManager:
    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.threads: dict[str, Thread] = {}

    def create(self, topic: str, participants: list[str]) -> Thread:
        thread = Thread(
            topic=topic,
            participants=set(participants),
            max_history=self.max_history,
        )
        self.threads[thread.id] = thread
        return thread

    def get(self, thread_id: str) -> Thread | None:
        return self.threads.get(thread_id)

    def list_all(self) -> list[Thread]:
        return list(self.threads.values())

    def record(self, thread_id: str, msg: Message) -> None:
        thread = self.threads.get(thread_id)
        if not thread:
            return
        thread.history.append(msg)
        if len(thread.history) > thread.max_history:
            thread.history = thread.history[-thread.max_history:]

    def build_context(self, thread_id: str, for_agent: str, last_n: int = 10) -> str:
        thread = self.threads.get(thread_id)
        if not thread:
            return ""
        recent = thread.history[-last_n:]
        lines = []
        private = thread.private_context.get(for_agent, {})
        for key, value in private.items():
            lines.append(f"[Private: {key}] {value}")
        if lines:
            lines.append("")
        for msg in recent:
            preview = msg.content[:200].replace("\n", " ")
            lines.append(f"[{msg.sender}]: {preview}")
        return "\n".join(lines)

    def set_private(self, thread_id: str, agent: str, key: str, value: str) -> None:
        thread = self.threads.get(thread_id)
        if thread:
            if agent not in thread.private_context:
                thread.private_context[agent] = {}
            thread.private_context[agent][key] = value

    def get_private(self, thread_id: str, agent: str, key: str) -> str | None:
        thread = self.threads.get(thread_id)
        if thread:
            return thread.private_context.get(agent, {}).get(key)
        return None

    def delete(self, thread_id: str) -> bool:
        if thread_id in self.threads:
            del self.threads[thread_id]
            return True
        return False
