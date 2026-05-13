"""
Multi-AI Communication Hub — CLI entry point.

Usage:
  python main.py interactive          # Start REPL
  python main.py ask gemini "..."     # One-shot direct message
  python main.py broadcast "..."      # Send to all AIs
  python main.py chain gemini codex "..."  # Sequential pipeline
  python main.py roundtable "Topic" gemini codex --rounds 3
  python main.py agents               # List agents
"""
import sys

from ai_hub.hub import AIHub


def main():
    hub = AIHub()
    args = sys.argv[1:]
    if not args:
        hub.interactive()
    else:
        hub.cli(args)


if __name__ == "__main__":
    main()
