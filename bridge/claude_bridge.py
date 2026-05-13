"""
Claude Bridge — CLI tool for Claude to call AI coding assistants (Codex/Gemini).
Usage:
  python bridge/claude_bridge.py --backend gemini "Write a Python function..."
  python bridge/claude_bridge.py --backend codex --task task_spec.json
  echo "implement X" | python bridge/claude_bridge.py --backend gemini
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from codex_client import CodexClient
from gemini_client import GeminiClient

ROOT = Path(__file__).parent.parent


def load_config():
    with open(ROOT / "config.json", "r", encoding="utf-8") as f:
        return json.load(f)


def load_task(task_file: str) -> dict:
    with open(ROOT / "tasks" / task_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_client(backend: str):
    config = load_config()
    if backend == "gemini":
        model = config.get("models", {}).get("gemini", "gemini-2.5-flash")
        return GeminiClient(model=model)
    else:
        model = config.get("models", {}).get("codex", "gpt-4o")
        return CodexClient(model=model)


def main():
    parser = argparse.ArgumentParser(description="Claude -> AI Bridge")
    parser.add_argument("prompt", nargs="?", help="Prompt to send")
    parser.add_argument(
        "--backend", "-b", choices=["codex", "gemini"], default="gemini",
        help="AI backend to use (default: gemini)"
    )
    parser.add_argument(
        "--task", "-t", help="Task spec JSON file (in tasks/ directory)"
    )
    parser.add_argument(
        "--save", "-s", help="Save response to file (in workspace/)"
    )
    parser.add_argument(
        "--context-file", "-c",
        help="Load/save conversation context from context.json",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Clear conversation context before sending"
    )
    parser.add_argument(
        "--system", help="Override system prompt"
    )
    args = parser.parse_args()

    client = get_client(args.backend)

    # Determine prompt
    prompt = None
    if args.task:
        task = load_task(args.task)
        role = task.get("role", "You are an expert software engineer.")
        client.system_prompt = role
        prompt = task.get("prompt", "")
    elif args.prompt:
        prompt = args.prompt
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()

    if not prompt:
        print("Error: No prompt provided. Use --task, positional arg, or stdin.")
        sys.exit(1)

    if args.system:
        client.system_prompt = args.system

    # Load previous context
    if args.context_file:
        ctx_path = ROOT / "workspace" / args.context_file
        if ctx_path.exists():
            client.load_context(str(ctx_path))

    if args.clear:
        client.clear_context()

    # Send
    print(f"[{args.backend}] {prompt[:80]}...")
    response = client.chat(prompt)
    print(response)

    # Save response
    if args.save:
        save_path = ROOT / "workspace" / args.save
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(response, encoding="utf-8")
        print(f"-> Saved to {save_path}")

    # Save context
    if args.context_file:
        ctx_path = ROOT / "workspace" / args.context_file
        client.save_context(str(ctx_path))
        print(f"-> Context saved to {ctx_path}")


if __name__ == "__main__":
    main()
