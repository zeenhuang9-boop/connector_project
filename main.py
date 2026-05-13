"""
Orchestrator - manages the Claude <-> Codex collaboration workflow.

# Workflow
1. Claude creates task specs in tasks/ directory
2. Claude calls `python main.py --run task_name.json` to send to Codex
3. Codex generates code -> saved to workspace/
4. Claude reviews, edits, and integrates the result
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


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
    parser = argparse.ArgumentParser(description="Claude <-> Codex Orchestrator")
    sub = parser.add_subparsers(dest="command")

    list_parser = sub.add_parser("list", help="List all tasks")

    run_parser = sub.add_parser("run", help="Run a task through the AI backend")
    run_parser.add_argument("task", help="Task JSON filename")
    run_parser.add_argument("--backend", "-b", choices=["codex", "gemini"], default="gemini", help="AI backend (default: gemini)")
    run_parser.add_argument("--clear", action="store_true", help="Clear context first")

    new_parser = sub.add_parser("new", help="Create a new task")
    new_parser.add_argument("name", help="Task filename (e.g. implement_auth.json)")
    new_parser.add_argument("prompt", nargs="+", help="The task prompt")
    new_parser.add_argument("--role", help="System role for Codex", default="")

    args = parser.parse_args()

    if args.command == "list":
        list_tasks()
    elif args.command == "run":
        run_task(args.task, clear=args.clear, backend=args.backend)
    elif args.command == "new":
        new_task(args.name, " ".join(args.prompt), args.role)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
