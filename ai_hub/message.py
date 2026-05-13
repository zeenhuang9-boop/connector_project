"""Message dataclass and MessageBus — the core of the AI communication hub."""
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Message:
    sender: str
    recipient: str
    content: str
    pattern: str = "direct"
    role: str = ""
    thread_id: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def to_prompt(self) -> str:
        return f"[From: {self.sender}, Role: {self.role}] {self.content}"


class MessageBus:
    def __init__(self, security):
        self.security = security
        self.agents: dict[str, "AIAdapter"] = {}
        self.log: list[Message] = []

    def register(self, agent: "AIAdapter") -> None:
        self.agents[agent.name] = agent

    def unregister(self, name: str) -> None:
        self.agents.pop(name, None)

    def list_agents(self) -> list[str]:
        return list(self.agents)

    def route(self, msg: Message) -> list[Message]:
        valid, reason = self.security.validate(msg)
        if not valid:
            self.security.audit(msg, f"REJECTED: {reason}")
            raise SecurityError(f"Message rejected: {reason}")

        if not self.security.check_rate(msg.sender):
            self.security.audit(msg, "RATE_LIMITED")
            raise RateLimitError(f"Rate limit exceeded for {msg.sender}")

        msg.content = self.security.sanitize(msg.content)
        self.security.audit(msg, "ACCEPTED")

        responses = []
        if msg.pattern == "direct":
            responses = [self._direct(msg)]
        elif msg.pattern == "broadcast":
            responses = self._broadcast(msg)
        elif msg.pattern == "chain":
            responses = self._chain(msg)
        elif msg.pattern == "round_robin":
            responses = self._round_robin(msg)
        elif msg.pattern == "moderated":
            responses = self._moderated(msg)
        else:
            raise ValueError(f"Unknown pattern: {msg.pattern}")

        sanitized = []
        for r in responses:
            if r:
                r.content = self.security.sanitize(r.content)
                sanitized.append(r)
                self.security.audit(r, "RESPONSE")

        self.log.append(msg)
        self.log.extend(sanitized)
        return sanitized

    def _direct(self, msg: Message) -> "Message | None":
        agent = self.agents.get(msg.recipient)
        if not agent:
            raise LookupError(f"Agent not found: {msg.recipient}")
        return agent.receive(msg)

    def _broadcast(self, msg: Message) -> list[Message]:
        responses = []
        for name, agent in self.agents.items():
            if name != msg.sender:
                try:
                    bcast_msg = Message(
                        sender=msg.sender, recipient=name,
                        content=msg.content, pattern="direct",
                        role=msg.role, thread_id=msg.thread_id,
                        metadata=dict(msg.metadata),
                    )
                    responses.append(agent.receive(bcast_msg))
                except Exception as e:
                    responses.append(Message(
                        sender=name, recipient=msg.sender,
                        content=f"[Error: {e}]", pattern="direct",
                        thread_id=msg.thread_id,
                    ))
        return responses

    def _chain(self, msg: Message) -> list[Message]:
        chain_order = msg.metadata.get("chain_order", [])
        if not chain_order:
            raise ValueError("chain pattern requires metadata.chain_order")
        responses = []
        previous_content = msg.content
        previous_sender = msg.sender
        for agent_name in chain_order:
            agent = self.agents.get(agent_name)
            if not agent:
                continue
            chain_msg = Message(
                sender=previous_sender, recipient=agent_name,
                content=previous_content, pattern="direct",
                role=msg.role, thread_id=msg.thread_id,
            )
            try:
                response = agent.receive(chain_msg)
                responses.append(response)
                previous_content = response.content
                previous_sender = agent_name
            except Exception as e:
                responses.append(Message(
                    sender=agent_name, recipient=msg.sender,
                    content=f"[Chain broken at {agent_name}: {e}]",
                    pattern="direct", thread_id=msg.thread_id,
                ))
                break
        return responses

    def _round_robin(self, msg: Message) -> list[Message]:
        participants = msg.metadata.get("participants", [])
        rounds = int(msg.metadata.get("rounds", 2))
        if not participants:
            raise ValueError("round_robin pattern requires metadata.participants")
        responses = []
        previous_content = msg.content
        for r in range(rounds):
            for agent_name in participants:
                agent = self.agents.get(agent_name)
                if not agent:
                    continue
                rr_msg = Message(
                    sender=msg.sender, recipient=agent_name,
                    content=previous_content, pattern="direct",
                    role=msg.role, thread_id=msg.thread_id,
                    metadata={"round": r + 1},
                )
                try:
                    response = agent.receive(rr_msg)
                    responses.append(response)
                    previous_content = response.content
                except Exception as e:
                    responses.append(Message(
                        sender=agent_name, recipient=msg.sender,
                        content=f"[Error in round {r + 1} at {agent_name}: {e}]",
                        pattern="direct", thread_id=msg.thread_id,
                    ))
        return responses

    def _moderated(self, msg: Message) -> list[Message]:
        moderator_name = msg.metadata.get("moderator", "")
        if not moderator_name:
            raise ValueError("moderated pattern requires metadata.moderator")
        moderator = self.agents.get(moderator_name)
        if not moderator:
            raise LookupError(f"Moderator not found: {moderator_name}")

        mod_response = moderator.receive(Message(
            sender=msg.sender, recipient=moderator_name,
            content=msg.content, pattern="direct",
            role="moderator", thread_id=msg.thread_id,
        ))

        if "APPROVE" in mod_response.content.upper():
            recipients = msg.metadata.get("recipients", [])
            responses = [mod_response]
            for name in recipients:
                agent = self.agents.get(name)
                if agent:
                    responses.append(agent.receive(Message(
                        sender=msg.sender, recipient=name,
                        content=msg.content, pattern="direct",
                        role=msg.role, thread_id=msg.thread_id,
                        metadata={"approved_by": moderator_name},
                    )))
            return responses
        return [mod_response]


class SecurityError(Exception):
    pass


class RateLimitError(Exception):
    pass
