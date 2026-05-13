# AI Connect Skill

Connect and orchestrate multiple AI models in a local communication hub. Enables Claude, Gemini, OpenAI Codex, and other AIs to collaborate in real-time conversations.

## Description

This skill provides a local multi-AI communication framework. It allows Claude to:
- Send direct messages to other AI models (Gemini, GPT/Codex)
- Broadcast messages to all connected AIs simultaneously  
- Create sequential AI pipelines (chain: A -> B -> C)
- Host round-robin discussions where AIs take turns building on each other's ideas
- Run moderated discussions with an AI moderator approving messages
- Manage persistent conversation threads with shared and private context

All routing happens **in-process locally** — no data leaves your machine except the API calls to the respective AI services. API keys stay in `.env` and are never logged or exposed in messages.

## Usage

Invoke with `/ai-connect` to start an interactive multi-AI REPL session.

### Interactive Commands

| Command | Description |
|---------|-------------|
| `ask <agent> <msg>` | Send direct message to an agent |
| `broadcast <msg>` | Send to all agents |
| `chain <a1> <a2> [...] <msg>` | Sequential pipeline |
| `roundtable <a1> <a2> [...] <topic> [--rounds N]` | Round-robin discussion |
| `moderated <mod> <a1> [...] <topic>` | Moderated discussion |
| `thread list` | List all threads |
| `thread show <id>` | View thread history |
| `agents` | List registered agents |
| `help` | Show help |
| `quit` | Exit |

### One-shot CLI

```bash
python main.py ask gemini "Write a sorting function"
python main.py chain gemini codex "Design then review an API"
python main.py roundtable "Auth design" gemini codex --rounds 3
python main.py broadcast "Review this architecture: ..."
```

### Integration with Claude Code

Claude can use this skill to delegate work to other AIs, get code reviews, or run multi-AI brainstorming sessions. Example workflow:

1. `/ai-connect` — start the REPL
2. `ask gemini "Write a Python implementation for X"`
3. Review Gemini's output
4. `ask codex "Review this code for bugs: [Gemini's code]"`
5. Use feedback to improve the solution

## Security

- API keys stored only in `.env`, never in code or config
- Message content sanitized — API key patterns redacted from all output
- Rate limiting at both hub and per-agent levels
- Injection detection blocks system prompt manipulation attempts
- All routing in-process, no network listeners

## Configuration

Edit `config.json` to add/remove agents and adjust security settings:

```json
{
  "agents": {
    "gemini": { "backend": "gemini", "role": "coder", "rate_limit": 1.0 },
    "codex": { "backend": "codex", "role": "reviewer", "rate_limit": 1.0 }
  },
  "security": {
    "max_message_length": 8000,
    "rate_limit_per_second": 1.0
  }
}
```
