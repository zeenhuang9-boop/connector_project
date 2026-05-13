# Connector Project

A lightweight orchestrator that lets Claude collaborate with other AI coding assistants (OpenAI Codex & Google Gemini) through a task-driven workflow.

## How It Works

```
Claude (orchestrator)          Codex / Gemini (code generators)
      │                                    │
      ├─ 1. Create task spec (JSON)        │
      ├─ 2. Dispatch via CLI ──────────────►
      │                                    ├─ 3. Generate code
      ◄────────────────────────────────────┤
      ├─ 4. Review & integrate ────────────►
```

1. **Define** — Create a task spec in `tasks/` with a system role and prompt
2. **Dispatch** — Run `python main.py --run task.json` to send it to the chosen AI backend
3. **Generate** — The backend (Codex or Gemini) produces code saved to `workspace/`
4. **Review** — Claude reviews, edits, and integrates the generated output

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys (copy .env.example → .env and fill in your keys)
cp .env.example .env

# Create a task
python main.py new my_task.json "Write a Python function that sorts a list of dicts by a given key"

# List all tasks
python main.py list

# Run a task (default: gemini)
python main.py run my_task.json

# Run with a specific backend
python main.py run my_task.json --backend codex
```

## Project Structure

```
connector_project/
├── main.py                  # Orchestrator CLI
├── config.json              # Model & context settings
├── bridge/
│   ├── claude_bridge.py     # CLI bridge between Claude and AI backends
│   ├── codex_client.py      # OpenAI API wrapper
│   └── gemini_client.py     # Google Gemini API wrapper
├── tasks/                   # JSON task specifications
│   └── example_reverse_api.json
└── workspace/               # Generated code output
```

## Supported Backends

| Backend | Model (configurable) | Key Required |
|---------|---------------------|--------------|
| Gemini  | `gemini-2.5-flash`  | `GEMINI_API_KEY` |
| Codex   | `gpt-4o`            | `OPENAI_API_KEY` |

Both backends support HTTP proxies via the `*_PROXY` environment variables.

## Configuration

Edit `config.json` to change models or context behavior:

```json
{
  "models": {
    "codex": "gpt-4o",
    "gemini": "gemini-2.5-flash"
  },
  "context": {
    "max_history": 20,
    "save_context": true
  }
}
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for Codex backend |
| `OPENAI_PROXY` | Optional HTTP proxy for OpenAI |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_PROXY` | Optional HTTP proxy for Gemini |

## Task Spec Format

```json
{
  "role": "You are an expert software engineer.",
  "prompt": "What you want the AI to build",
  "output_file": "result.py",
  "context_file": "session_context.json"
}
```
