"""AIHub — Multi-AI communication orchestrator with CLI and REPL."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

from .message import Message, MessageBus, SecurityError, RateLimitError
from .security import SecurityGuard
from .adapters import AIAdapter, GeminiAdapter, CodexAdapter
from .conversation import ConversationManager, Thread


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
        self.agents: dict[str, AIAdapter] = {}
        self._init_agents()

    def _init_agents(self) -> None:
        agents_cfg = self.config.get("agents", {})
        for name, cfg in agents_cfg.items():
            backend = cfg.get("backend", "gemini")
            role = cfg.get("role", "coder")
            rate = float(cfg.get("rate_limit", 1.0))
            if backend == "gemini":
                adapter = GeminiAdapter(name=name, role=role, rate_limit=rate)
            elif backend == "codex":
                adapter = CodexAdapter(name=name, role=role, rate_limit=rate)
            else:
                print(f"[WARN] Unknown backend '{backend}' for agent '{name}', skipping")
                continue
            self.agents[name] = adapter
            self.bus.register(adapter)

    # ── high-level API ────────────────────────────────────────────

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
            sender=sender, recipient=chain_order[0],
            content=content, pattern="chain", role=role,
            thread_id=thread_id,
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
        all_responses = []
        seed = Message(
            sender="claude", recipient=participants[0],
            content=f"Discuss: {topic}", pattern="round_robin",
            role="moderator", thread_id=thread.id,
            metadata={"participants": participants, "rounds": rounds},
        )
        responses = self.bus.route(seed)
        for r in responses:
            self.conversations.record(thread.id, r)
        all_responses.extend(responses)
        return all_responses

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

    # ── thread helpers ─────────────────────────────────────────────

    def new_thread(self, topic: str, participants: list[str]) -> str:
        return self.conversations.create(topic, participants).id

    def thread_summary(self, thread_id: str) -> str:
        thread = self.conversations.get(thread_id)
        if not thread:
            return f"Thread {thread_id} not found."
        return thread.to_summary()

    def thread_history(self, thread_id: str) -> list[Message]:
        thread = self.conversations.get(thread_id)
        if not thread:
            return []
        return list(thread.history)

    # ── interactive REPL ──────────────────────────────────────────

    def interactive(self) -> None:
        print("AI Hub — Multi-AI Communication Framework v1.0.0")
        print(f"Available agents: {', '.join(self.bus.list_agents())}")
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
                print("Registered agents:")
                for name, agent in self.agents.items():
                    print(f"  {name} ({agent.role})")
            elif cmd == "ask" and len(parts) >= 3:
                agent_name = parts[1]
                content = " ".join(parts[2:])
                if agent_name not in self.agents:
                    print(f"Unknown agent: {agent_name}")
                    continue
                print(f"[claude -> {agent_name}] {content[:80]}...")
                try:
                    responses = self.send("claude", agent_name, content)
                    for r in responses:
                        print(f"\n[{r.sender}]: {r.content}\n")
                except (SecurityError, RateLimitError) as e:
                    print(f"Error: {e}")
            elif cmd == "broadcast" and len(parts) >= 2:
                content = " ".join(parts[1:])
                print(f"[broadcast] {content[:80]}...")
                try:
                    responses = self.broadcast("claude", content)
                    for r in responses:
                        print(f"\n[{r.sender}]: {r.content}\n")
                except (SecurityError, RateLimitError) as e:
                    print(f"Error: {e}")
            elif cmd == "chain" and len(parts) >= 3:
                chain_order = []
                rest = parts[1:]
                for i, p in enumerate(rest):
                    if p not in self.agents:
                        chain_order = rest[:i]
                        content = " ".join(rest[i:])
                        break
                else:
                    print("Usage: chain <agent1> <agent2> [...] <message>")
                    continue
                if not chain_order or not content:
                    print("Usage: chain <agent1> <agent2> [...] <message>")
                    continue
                print(f"[chain: {' -> '.join(chain_order)}] {content[:60]}...")
                try:
                    responses = self.chain("claude", chain_order, content)
                    for r in responses:
                        print(f"\n[{r.sender}]: {r.content}\n")
                except (SecurityError, RateLimitError) as e:
                    print(f"Error: {e}")
            elif cmd == "roundtable" and len(parts) >= 3:
                topic_parts = []
                participants = []
                in_participants = True
                rounds = 2
                i = 1
                while i < len(parts):
                    if parts[i] == "--rounds" and i + 1 < len(parts):
                        rounds = int(parts[i + 1])
                        i += 2
                        in_participants = False
                    elif in_participants and parts[i] in self.agents:
                        participants.append(parts[i])
                        i += 1
                    else:
                        in_participants = False
                        topic_parts.append(parts[i])
                        i += 1
                topic = " ".join(topic_parts) if topic_parts else "Discussion"
                if not participants:
                    print("Usage: roundtable <topic> <agent1> <agent2> [...] [--rounds N]")
                    continue
                print(f"[roundtable] {topic} | {', '.join(participants)} | {rounds} rounds")
                try:
                    responses = self.roundtable(topic, participants, rounds)
                    for r in responses:
                        print(f"\n[{r.sender}] (round {r.metadata.get('round', '?')}): {r.content}\n")
                except (SecurityError, RateLimitError) as e:
                    print(f"Error: {e}")
            elif cmd == "moderated":
                if len(parts) < 4:
                    print("Usage: moderated <moderator> <agent1> <agent2> [...] <topic>")
                    continue
                moderator = parts[1]
                topic_parts = []
                agent_list = []
                in_agents = True
                for p in parts[2:]:
                    if in_agents and p in self.agents:
                        agent_list.append(p)
                    else:
                        in_agents = False
                        topic_parts.append(p)
                topic = " ".join(topic_parts) if topic_parts else "Discussion"
                if not agent_list:
                    print("Usage: moderated <moderator> <agent1> [...] <topic>")
                    continue
                print(f"[moderated by {moderator}] {topic}")
                try:
                    responses = self.moderated_discussion(moderator, agent_list, topic)
                    for r in responses:
                        print(f"\n[{r.sender}]: {r.content}\n")
                except (SecurityError, RateLimitError) as e:
                    print(f"Error: {e}")
            elif cmd == "thread":
                if len(parts) < 2:
                    print("Usage: thread list|show <id>|delete <id>")
                    continue
                sub = parts[1]
                if sub == "list":
                    threads = self.conversations.list_all()
                    if not threads:
                        print("No threads.")
                    else:
                        for t in threads:
                            print(t.to_summary())
                            print()
                elif sub == "show" and len(parts) >= 3:
                    tid = parts[2]
                    print(self.thread_summary(tid))
                    print()
                    for msg in self.thread_history(tid):
                        print(f"  [{msg.sender} -> {msg.recipient}] {msg.content[:200]}")
                elif sub == "delete" and len(parts) >= 3:
                    tid = parts[2]
                    ok = self.conversations.delete(tid)
                    print(f"Deleted: {ok}")
                else:
                    print("Usage: thread list|show <id>|delete <id>")
            else:
                print(f"Unknown command: {cmd}. Type 'help'.")

    # ── one-shot CLI ───────────────────────────────────────────────

    def cli(self, args: list[str]) -> None:
        if not args:
            self.interactive()
            return
        cmd = args[0].lower()
        if cmd == "interactive":
            self.interactive()
        elif cmd == "ask" and len(args) >= 3:
            responses = self.send("claude", args[1], " ".join(args[2:]))
            for r in responses:
                print(f"[{r.sender}]: {r.content}")
        elif cmd == "broadcast" and len(args) >= 2:
            responses = self.broadcast("claude", " ".join(args[1:]))
            for r in responses:
                print(f"[{r.sender}]: {r.content}")
        elif cmd == "roundtable":
            self._cli_roundtable(args[1:])
        elif cmd == "chain" and len(args) >= 3:
            self._cli_chain(args[1:])
        elif cmd == "agents":
            for name, agent in self.agents.items():
                print(f"{name}: {agent.role}")
        else:
            print(f"Unknown command: {cmd}")
            print("Commands: interactive, ask, broadcast, roundtable, chain, agents")

    def _cli_roundtable(self, args: list[str]) -> None:
        topic_parts = []
        participants = []
        rounds = 2
        in_participants = True
        i = 0
        while i < len(args):
            if args[i] == "--rounds" and i + 1 < len(args):
                rounds = int(args[i + 1])
                i += 2
                in_participants = False
            elif in_participants and args[i] in self.agents:
                participants.append(args[i])
                i += 1
            else:
                in_participants = False
                topic_parts.append(args[i])
                i += 1
        topic = " ".join(topic_parts) if topic_parts else "Discussion"
        if not participants:
            print("Need at least one participant. Usage: roundtable <agent1> [...] <topic> [--rounds N]")
            return
        print(f"[roundtable] {topic} | {', '.join(participants)} | {rounds} rounds")
        responses = self.roundtable(topic, participants, rounds)
        for r in responses:
            print(f"\n[{r.sender}]: {r.content}")

    def _cli_chain(self, args: list[str]) -> None:
        chain_order = []
        rest = args
        for i, p in enumerate(rest):
            if p in self.agents:
                chain_order.append(p)
            else:
                content = " ".join(rest[i:])
                break
        else:
            print("Usage: chain <agent1> <agent2> [...] <message>")
            return
        if not chain_order or not content:
            print("Usage: chain <agent1> <agent2> [...] <message>")
            return
        print(f"[chain: {' -> '.join(chain_order)}]")
        responses = self.chain("claude", chain_order, content)
        for r in responses:
            print(f"[{r.sender}]: {r.content}")


def _load_config(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _print_help() -> None:
    print("""Commands:
  ask <agent> <message>           Send a direct message to an agent
  broadcast <message>             Send a message to all agents
  chain <a1> <a2> [...] <msg>     Chain agents sequentially
  roundtable <a1> <a2> [...] <topic> [--rounds N]  Round-robin discussion
  moderated <mod> <a1> [...] <topic>  Moderated discussion
  thread list                     List all conversation threads
  thread show <id>                Show thread details and history
  thread delete <id>              Delete a thread
  agents                          List registered agents
  help                            Show this help
  quit / exit                     Exit""")


def main():
    hub = AIHub()
    if len(sys.argv) > 1:
        hub.cli(sys.argv[1:])
    else:
        hub.interactive()


if __name__ == "__main__":
    main()
