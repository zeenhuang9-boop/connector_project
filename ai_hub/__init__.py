"""AI Hub — Multi-AI Communication Framework v1.0.0.

Enables local message routing between Claude, Gemini, OpenAI Codex, and other AI backends.
All routing is in-process — no network sockets between agents.
"""

__version__ = "1.0.0"

from .message import Message, MessageBus
from .adapters import AIAdapter, GeminiAdapter, CodexAdapter, ROLES
from .conversation import Thread, ConversationManager
from .security import SecurityGuard, TokenBucket
from .hub import AIHub
