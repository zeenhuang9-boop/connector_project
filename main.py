"""
Orchestrator — Claude <-> Codex/Gemini collaboration with multi-AI hub support.

Usage:
  python main.py interactive          # Start the multi-AI REPL
  python main.py ask gemini "..."     # One-shot direct message
  python main.py broadcast "..."      # Send to all AIs
  python main.py chain gemini codex "..."  # Sequential AI pipeline
  python main.py roundtable "Topic" gemini codex --rounds 3  # Round-robin
  python main.py list                 # List legacy tasks
  python main.py run task.json        # Run legacy task (single AI)
  python main.py new name.json "..."  # Create legacy task
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def _hub_dispatch(args: list[str]) -> None:
    from ai_hub.hub import AIHub
    hub = AIHub()
    if not args:
        hub.interactive()
    else:
        hub.cli(args)


def list_tasks():
    tasks_dir = ROOT / "tasks"
    if not tasks_dir.exists():
        print("No tasks/ directory found.")
        return
    tasks = sorted(tasks_dir.glob("*.json"))
    if not tasks:
        print("No task files found in tasks/")
        return
    print("Available tasks:")
    for t in tasks:
        with open(t, "r", encoding="utf-8") as f:
            task = json.load(f)
        prompt_preview = task.get("prompt", "")[:80].replace("\n", " ")
        print(f"  {t.name:40s} -> {prompt_preview}...")


def run_task(task_name: str, clear: bool = False, backend: str = "gemini"):
    task_path = ROOT / "tasks" / task_name
    if not task_path.exists():
        print(f"Task not found: {task_path}")
        sys.exit(1)

    with open(task_path, "r", encoding="utf-8") as f:
        task = json.load(f)

    output_file = task.get("output_file", task_name.replace(".json", ".py"))
    ctx_file = task.get("context_file", "codex_context.json")

    cmd = [
        sys.executable,
        str(ROOT / "bridge" / "claude_bridge.py"),
        "--backend", backend,
        "--task", task_name,
        "--save", output_file,
        "--context-file", ctx_file,
    ]
    if clear:
        cmd.append("--clear")

    print(f"[{backend}] {task['prompt'][:100]}...")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)


def new_task(name: str, prompt: str, role: str = ""):
    tasks_dir = ROOT / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    task = {
        "role": role or "You are an expert software engineer. Write clean, production-ready code.",
        "prompt": prompt,
        "output_file": f"{name.replace('.json', '')}.py",
        "context_file": "codex_context.json",
    }
    path = tasks_dir / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(task, f, ensure_ascii=False, indent=2)
    print(f"[OK] Created task: {path}")


def main():
    parser = argparse.ArgumentParser(description="Claude <-> Multi-AI Orchestrator")
    parser.add_argument(
        "hub_cmd", nargs="?", default="interactive",
        help="Hub command: interactive, ask, broadcast, chain, roundtable, list, run, new"
    )
    parser.add_argument(
        "hub_args", nargs="*",
        help="Additional arguments for the hub command"
    )
    args, unknown = parser.parse_known_args()

    cmd = args.hub_cmd

    if cmd == "interactive":
        _hub_dispatch([])
    elif cmd == "ask":
        _hub_dispatch(["ask"] + args.hub_args)
    elif cmd == "broadcast":
        _hub_dispatch(["broadcast"] + args.hub_args)
    elif cmd == "chain":
        _hub_dispatch(["chain"] + args.hub_args)
    elif cmd == "roundtable":
        _hub_dispatch(["roundtable"] + args.hub_args)
    elif cmd == "moderated":
        _hub_dispatch(["moderated"] + args.hub_args)
    elif cmd == "list":
        list_tasks()
    elif cmd == "run":
        backend = "gemini"
        clear = False
        task_name = None
        uargs = args.hub_args + unknown
        i = 0
        while i < len(uargs):
            if uargs[i] in ("--backend", "-b") and i + 1 < len(uargs):
                backend = uargs[i + 1]
                i += 2
            elif uargs[i] == "--clear":
                clear = True
                i += 1
            else:
                task_name = uargs[i]
                i += 1
        if task_name:
            run_task(task_name, clear=clear, backend=backend)
        else:
            print("Usage: python main.py run <task.json> [--backend gemini|codex] [--clear]")
    elif cmd == "new":
        if len(args.hub_args) >= 2:
            new_task(args.hub_args[0], " ".join(args.hub_args[1:]))
        else:
            print("Usage: python main.py new <name.json> <prompt>")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
