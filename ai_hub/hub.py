"""AIHub — Multi-AI communication orchestrator with CLI and REPL."""
import json
import sys
from pathlib import Path

from .message import Message, MessageBus, SecurityError, RateLimitError
from .security import SecurityGuard
from .adapters import GeminiAdapter, CodexAdapter
from .conversation import ConversationManager

ROOT = Path(__file__).parent.parent


class AIHub:
    def __init__(self, config_path: Path | None = None):
        self.config = _load_config(config_path or ROOT / "config.json")
        security_cfg = self.config.get("security", {})
        context_cfg = self.config.get("context", {})

        self.security = SecurityGuard(security_cfg)
        self.bus = MessageBus(self.security)
        self.conversations = ConversationManager(
            max_history=context_cfg.get("max_history", 20)
        )
        self.agents: dict[str, "AIAdapter"] = {}
        self._init_agents()

    def _init_agents(self) -> None:
        agents_cfg = self.config.get("agents", {})
        for name, cfg in agents_cfg.items():
            backend = cfg.get("backend", "gemini")
            role = cfg.get("role", "coder")
            rate = float(cfg.get("rate_limit", 1.0))
            try:
                if backend == "gemini":
                    adapter = GeminiAdapter(name=name, role=role, rate_limit=rate)
                elif backend == "codex":
                    adapter = CodexAdapter(name=name, role=role, rate_limit=rate)
                else:
                    continue
                self.agents[name] = adapter
                self.bus.register(adapter)
            except Exception as e:
                print(f"[WARN] Agent '{name}' ({backend}) failed to init: {e}")

    def send(self, sender: str, recipient: str, content: str,
             thread_id: str = "", role: str = "") -> list[Message]:
        msg = Message(
            sender=sender, recipient=recipient, content=content,
            pattern="direct", role=role, thread_id=thread_id,
        )
        responses = self.bus.route(msg)
        if thread_id:
            self.conversations.record(thread_id, msg)
            for r in responses:
                self.conversations.record(thread_id, r)
        return responses

    def broadcast(self, sender: str, content: str,
                  thread_id: str = "", role: str = "") -> list[Message]:
        msg = Message(
            sender=sender, recipient="all", content=content,
            pattern="broadcast", role=role, thread_id=thread_id,
        )
        responses = self.bus.route(msg)
        if thread_id:
            self.conversations.record(thread_id, msg)
            for r in responses:
                self.conversations.record(thread_id, r)
        return responses

    def chain(self, sender: str, chain_order: list[str], content: str,
              thread_id: str = "", role: str = "") -> list[Message]:
        msg = Message(
            sender=sender, recipient=chain_order[0], content=content,
            pattern="chain", role=role, thread_id=thread_id,
            metadata={"chain_order": chain_order},
        )
        responses = self.bus.route(msg)
        if thread_id:
            self.conversations.record(thread_id, msg)
            for r in responses:
                self.conversations.record(thread_id, r)
        return responses

    def roundtable(self, topic: str, participants: list[str],
                   rounds: int = 2) -> list[Message]:
        thread = self.conversations.create(topic, participants)
        msg = Message(
            sender="claude", recipient=participants[0],
            content=f"Discuss: {topic}", pattern="round_robin",
            role="moderator", thread_id=thread.id,
            metadata={"participants": participants, "rounds": rounds},
        )
        responses = self.bus.route(msg)
        for r in responses:
            self.conversations.record(thread.id, r)
        return responses

    def moderated_discussion(self, moderator: str, participants: list[str],
                             topic: str) -> list[Message]:
        thread = self.conversations.create(topic, [moderator] + participants)
        msg = Message(
            sender="claude", recipient="all", content=f"Discuss: {topic}",
            pattern="moderated", role="moderator", thread_id=thread.id,
            metadata={"moderator": moderator, "recipients": participants},
        )
        responses = self.bus.route(msg)
        for r in responses:
            self.conversations.record(thread.id, r)
        return responses

    def new_thread(self, topic: str, participants: list[str]) -> str:
        return self.conversations.create(topic, participants).id

    def thread_summary(self, thread_id: str) -> str:
        thread = self.conversations.get(thread_id)
        return thread.to_summary() if thread else f"Thread {thread_id} not found."

    def thread_history(self, thread_id: str) -> list[Message]:
        thread = self.conversations.get(thread_id)
        return list(thread.history) if thread else []

    def interactive(self) -> None:
        print(f"AI Hub v1.0 | Agents: {', '.join(self.bus.list_agents())}")
        print("Type 'help' for commands, 'quit' to exit.\n")
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye.")
                break
            if not line:
                continue
            parts = line.split()
            cmd = parts[0].lower()
            if cmd in ("quit", "exit"):
                print("Goodbye.")
                break
            elif cmd == "help":
                _print_help()
            elif cmd == "agents":
                for name, agent in self.agents.items():
                    print(f"  {name} ({agent.role})")
            elif cmd == "ask" and len(parts) >= 3:
                self._repl_ask(parts[1], " ".join(parts[2:]))
            elif cmd == "broadcast" and len(parts) >= 2:
                self._repl_broadcast(" ".join(parts[1:]))
            elif cmd == "chain" and len(parts) >= 3:
                self._repl_chain(parts[1:])
            elif cmd == "roundtable" and len(parts) >= 3:
                self._repl_roundtable(parts[1:])
            elif cmd == "moderated" and len(parts) >= 4:
                self._repl_moderated(parts[1:])
            elif cmd == "thread":
                self._repl_thread(parts[1:])
            else:
                print(f"Unknown: {cmd}. Type 'help'.")

    def _repl_ask(self, agent: str, content: str) -> None:
        if agent not in self.agents:
            print(f"Unknown agent: {agent}")
            return
        print(f"[claude -> {agent}] {content[:80]}...")
        try:
            for r in self.send("claude", agent, content):
                print(f"\n[{r.sender}]: {r.content}\n")
        except (SecurityError, RateLimitError) as e:
            print(f"Error: {e}")

    def _repl_broadcast(self, content: str) -> None:
        print(f"[broadcast] {content[:80]}...")
        try:
            for r in self.broadcast("claude", content):
                print(f"\n[{r.sender}]: {r.content}\n")
        except (SecurityError, RateLimitError) as e:
            print(f"Error: {e}")

    def _repl_chain(self, args: list[str]) -> None:
        chain_order, content = _parse_agent_list(args, self.agents)
        if not chain_order or not content:
            print("Usage: chain <agent1> <agent2> [...] <message>")
            return
        print(f"[chain: {' -> '.join(chain_order)}] {content[:60]}...")
        try:
            for r in self.chain("claude", chain_order, content):
                print(f"\n[{r.sender}]: {r.content}\n")
        except (SecurityError, RateLimitError) as e:
            print(f"Error: {e}")

    def _repl_roundtable(self, args: list[str]) -> None:
        participants, topic, rounds = _parse_roundtable(args, self.agents)
        if not participants:
            print("Usage: roundtable <agent1> <agent2> [...] <topic> [--rounds N]")
            return
        print(f"[roundtable] {topic} | {', '.join(participants)} | {rounds} rounds")
        try:
            for r in self.roundtable(topic, participants, rounds):
                print(f"\n[{r.sender}] (round {r.metadata.get('round', '?')}): {r.content}\n")
        except (SecurityError, RateLimitError) as e:
            print(f"Error: {e}")

    def _repl_moderated(self, args: list[str]) -> None:
        moderator = args[0]
        agent_list, topic = _parse_agent_list(args[1:], self.agents)
        if not agent_list:
            print("Usage: moderated <moderator> <agent1> [...] <topic>")
            return
        print(f"[moderated by {moderator}] {topic}")
        try:
            for r in self.moderated_discussion(moderator, agent_list, topic):
                print(f"\n[{r.sender}]: {r.content}\n")
        except (SecurityError, RateLimitError) as e:
            print(f"Error: {e}")

    def _repl_thread(self, args: list[str]) -> None:
        if not args:
            print("Usage: thread list|show <id>|delete <id>")
            return
        sub = args[0]
        if sub == "list":
            threads = self.conversations.list_all()
            if not threads:
                print("No threads.")
            else:
                for t in threads:
                    print(t.to_summary())
                    print()
        elif sub == "show" and len(args) >= 2:
            tid = args[1]
            print(self.thread_summary(tid))
            print()
            for msg in self.thread_history(tid):
                print(f"  [{msg.sender} -> {msg.recipient}] {msg.content[:200]}")
        elif sub == "delete" and len(args) >= 2:
            print(f"Deleted: {self.conversations.delete(args[1])}")
        else:
            print("Usage: thread list|show <id>|delete <id>")

    def cli(self, args: list[str]) -> None:
        if not args:
            self.interactive()
            return
        cmd = args[0].lower()
        if cmd == "interactive":
            self.interactive()
        elif cmd == "ask" and len(args) >= 3:
            for r in self.send("claude", args[1], " ".join(args[2:])):
                print(f"[{r.sender}]: {r.content}")
        elif cmd == "broadcast" and len(args) >= 2:
            for r in self.broadcast("claude", " ".join(args[1:])):
                print(f"[{r.sender}]: {r.content}")
        elif cmd == "chain" and len(args) >= 3:
            chain_order, content = _parse_agent_list(args[1:], self.agents)
            if chain_order and content:
                for r in self.chain("claude", chain_order, content):
                    print(f"[{r.sender}]: {r.content}")
        elif cmd == "roundtable":
            participants, topic, rounds = _parse_roundtable(args[1:], self.agents)
            if participants:
                for r in self.roundtable(topic, participants, rounds):
                    print(f"[{r.sender}]: {r.content}")
        elif cmd == "agents":
            for name, agent in self.agents.items():
                print(f"{name}: {agent.role}")
        else:
            print(f"Unknown: {cmd}")


def _parse_agent_list(args: list[str], agents: dict) -> tuple[list[str], str]:
    chain_order = []
    for i, p in enumerate(args):
        if p in agents:
            chain_order.append(p)
        else:
            return chain_order, " ".join(args[i:])
    return chain_order, ""


def _parse_roundtable(args: list[str], agents: dict) -> tuple[list[str], str, int]:
    participants = []
    topic_parts = []
    rounds = 2
    in_participants = True
    i = 0
    while i < len(args):
        if args[i] == "--rounds" and i + 1 < len(args):
            rounds = int(args[i + 1])
            i += 2
            in_participants = False
        elif in_participants and args[i] in agents:
            participants.append(args[i])
            i += 1
        else:
            in_participants = False
            topic_parts.append(args[i])
            i += 1
    topic = " ".join(topic_parts) if topic_parts else "Discussion"
    return participants, topic, rounds


def _load_config(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _print_help() -> None:
    print("""Commands:
  ask <agent> <message>           Send a direct message
  broadcast <message>             Send to all agents
  chain <a1> <a2> [...] <msg>     Sequential pipeline
  roundtable <a1> <a2> [...] <topic> [--rounds N]
  moderated <mod> <a1> [...] <topic>
  thread list | show <id> | delete <id>
  agents                          List agents
  help                            Show this help
  quit / exit                     Exit""")


def main():
    hub = AIHub()
    if len(sys.argv) > 1:
        hub.cli(sys.argv[1:])
    else:
        hub.interactive()
