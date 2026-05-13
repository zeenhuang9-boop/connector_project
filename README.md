# Connector Project

Local multi-AI communication hub — enables Claude, Gemini, OpenAI Codex, and other AI models to communicate with each other in real-time. All message routing is in-process; no data leaves your machine except the API calls to each AI service.

## Communication Patterns

| Pattern | Description |
|---------|-------------|
| **direct** | One-to-one message between any two AIs |
| **broadcast** | One AI sends to all others simultaneously |
| **chain** | Sequential pipeline (A → B → C → D), each response forwarded as input to the next |
| **round_robin** | Multi-round discussion where AIs take turns building on each other's ideas |
| **moderated** | A moderator AI reviews messages before they reach other participants |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env    # then edit .env with your real keys

# Start interactive REPL
python main.py interactive

# One-shot commands
python main.py ask gemini "Write a Python sort function"
python main.py chain gemini codex "Design then review a REST API"
python main.py roundtable "Auth architecture" gemini codex --rounds 3
python main.py broadcast "Review this code: ..."
```

### REPL Commands

```
> ask gemini "Write a sorting function"
> broadcast "Review this architecture"
> chain gemini codex "Design then review"
> roundtable gemini codex "Auth design" --rounds 3
> moderated gemini codex "Database schema"
> thread list
> thread show <id>
> agents
> help
> quit
```

## Project Structure

```
connector_project/
├── main.py                  # CLI entry point
├── config.json              # Agent & security configuration
├── ai_hub/
│   ├── hub.py               # AIHub orchestrator + REPL/CLI
│   ├── message.py           # Message dataclass + MessageBus router
│   ├── adapters.py          # AIAdapter + GeminiAdapter + CodexAdapter
│   ├── conversation.py      # Thread + ConversationManager
│   └── security.py          # TokenBucket + SecurityGuard
├── bridge/
│   ├── gemini_client.py     # Google Gemini API wrapper
│   └── codex_client.py      # OpenAI API wrapper
├── .claude/skills/
│   └── ai-connect.md        # Claude Code skill definition
├── .env.example             # Environment template
└── requirements.txt
```

## Claude Code Skill

Invoke with `/ai-connect` in Claude Code to start the multi-AI REPL. Claude acts as the orchestrator, delegating tasks to other AIs and moderating discussions.

## Configuration

Edit `config.json` to add agents or adjust security:

```json
{
  "agents": {
    "gemini": { "backend": "gemini", "role": "coder", "rate_limit": 1.0 },
    "codex": { "backend": "codex", "role": "reviewer", "rate_limit": 1.0 }
  },
  "security": {
    "max_message_length": 8000,
    "rate_limit_per_second": 1.0,
    "banned_patterns": ["</?system>", "ignore previous instructions"]
  },
  "context": {
    "max_history": 20,
    "save_context": true
  }
}
```

### Agent Roles

| Role | Description |
|------|-------------|
| `coder` | Writes production-ready code |
| `reviewer` | Finds bugs and suggests improvements |
| `architect` | Designs systems and chooses patterns |
| `critic` | Identifies weaknesses, proposes improvements |
| `moderator` | Synthesizes viewpoints, guides toward consensus |

## Supported Backends

| Backend | Default Model | Key Required |
|---------|--------------|--------------|
| Gemini | `gemini-2.5-flash` | `GEMINI_API_KEY` |
| Codex | `gpt-4o` | `OPENAI_API_KEY` |

Both backends support HTTP proxies via `GEMINI_PROXY` / `OPENAI_PROXY` environment variables.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_PROXY` | Optional HTTP proxy for Gemini |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_PROXY` | Optional HTTP proxy for OpenAI |

## Security

- API keys stored only in `.env`, never in code, config, or git
- Message content sanitized — API key patterns auto-redacted from all output
- Two-layer rate limiting (hub-level + per-agent)
- Injection detection blocks system prompt manipulation
- All routing in-process — no network sockets between agents
