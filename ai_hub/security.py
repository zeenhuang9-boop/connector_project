"""Security layer — rate limiting, input validation, output sanitization."""
import re
import sys
import time


class TokenBucket:
    def __init__(self, capacity: float = 10.0, refill_rate: float = 1.0):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + self.refill_rate * elapsed)
        self.last_refill = now

    def consume(self, tokens: float = 1.0) -> bool:
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class SecurityGuard:
    _SECRET_PATTERNS = [
        re.compile(r'sk-[a-zA-Z0-9]{20,}'),
        re.compile(r'AIza[a-zA-Z0-9_\-]{30,}'),
        re.compile(r'sk-ant-[a-zA-Z0-9_\-]{20,}'),
        re.compile(r'Bearer\s+[a-zA-Z0-9_\-\.]{20,}'),
    ]

    _DEFAULT_BANNED = [
        re.compile(r'</?system>', re.IGNORECASE),
        re.compile(r'\[SYSTEM\]', re.IGNORECASE),
        re.compile(r'ignore previous instructions', re.IGNORECASE),
        re.compile(r'<\|im_start\|>', re.IGNORECASE),
        re.compile(r'<\|im_end\|>', re.IGNORECASE),
    ]

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.max_message_length: int = cfg.get("max_message_length", 8000)
        self.banned_patterns: list[re.Pattern] = list(self._DEFAULT_BANNED)
        for pat_str in cfg.get("banned_patterns", []):
            self.banned_patterns.append(re.compile(pat_str, re.IGNORECASE))
        self.rate_limiters: dict[str, TokenBucket] = {}
        self.audit_log: list[str] = []
        self.default_refill_rate: float = cfg.get("rate_limit_per_second", 1.0)

    def validate(self, msg) -> tuple[bool, str]:
        if not msg.content or not msg.content.strip():
            return False, "Empty message content"
        if len(msg.content) > self.max_message_length:
            return False, f"Content too long ({len(msg.content)} > {self.max_message_length})"
        if not msg.sender or not msg.sender.strip():
            return False, "Empty sender"
        for pat in self.banned_patterns:
            if pat.search(msg.content):
                return False, f"Banned pattern matched: {pat.pattern}"
        return True, ""

    def sanitize(self, content: str) -> str:
        cleaned = content
        for pat in self._SECRET_PATTERNS:
            cleaned = pat.sub('[REDACTED]', cleaned)
        cleaned = ''.join(c for c in cleaned if ord(c) >= 32 or c in ('\n', '\t'))
        if len(cleaned) > self.max_message_length:
            cleaned = cleaned[:self.max_message_length]
        return cleaned

    def check_rate(self, agent_name: str, tokens_per_msg: float = 1.0) -> bool:
        if agent_name not in self.rate_limiters:
            self.rate_limiters[agent_name] = TokenBucket(
                capacity=self.default_refill_rate * 10,
                refill_rate=self.default_refill_rate
            )
        return self.rate_limiters[agent_name].consume(tokens_per_msg)

    def audit(self, msg, action: str) -> None:
        entry = (f"[AUDIT] {msg.timestamp:.0f} {action} {msg.id[:8]} "
                 f"{msg.sender}->{msg.recipient} [{msg.pattern}]")
        self.audit_log.append(entry)
        print(entry, file=sys.stderr)
