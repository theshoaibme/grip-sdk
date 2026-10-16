"""Grip CLI: Command-line interface for Grip AI Search & Web Agent."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from ..client import Grip
from .._version import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="grip",
        description="Grip Platform: Dynamic AI Search & Multi-Agent SDK (https://grip.theshoaib.me/)",
    )
    parser.add_argument("--version", "-v", action="version", version=f"Grip Platform v{__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Search sub-command
    search_parser = subparsers.add_parser("search", aliases=["query"], help="Execute an AI search query")
    search_parser.add_argument("query", help="Search query string")
    search_parser.add_argument("--json", action="store_true", help="Output raw JSON response")
    search_parser.add_argument("--session-id", help="Attach query to existing session ID")
    search_parser.add_argument("--provider", default="google", help="Search AI provider (google, openai, etc.)")
    search_parser.add_argument("--no-stream", action="store_true", help="Disable streaming and wait for full response")

    # Interactive chat sub-command
    chat_parser = subparsers.add_parser("chat", aliases=["session"], help="Start an interactive multi-turn session in terminal")
    chat_parser.add_argument("--title", default="Grip Chat", help="Session title")
    chat_parser.add_argument("--provider", default="google", help="Search AI provider (google, openai, etc.)")

    # Providers sub-command
    subparsers.add_parser("providers", help="List available AI search providers")

    # Serve sub-command
    serve_parser = subparsers.add_parser("serve", help="Start the Grip AI web server and UI")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    serve_parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    # Rules sub-command
    rules_parser = subparsers.add_parser("rules", help="Manage custom system rules and persona")
    rules_parser.add_argument("--identity", help="Set assistant identity/persona")
    rules_parser.add_argument("--format", help="Set response format specification")
    rules_parser.add_argument("--add", help="Add a behavioral constraint rule")
    rules_parser.add_argument("--list", action="store_true", help="List active rules")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "providers":
        from grip_engine.providers.registry import default_provider_registry
        providers = default_provider_registry.list_providers()
        print("\nRegistered AI Search Providers:")
        for p in providers:
            print(f"• {p}")
        return 0

    if args.command == "serve":
        try:
            import uvicorn
            from services.api.app.main import app
            print(f"🚀 Starting Grip AI Platform on http://{args.host}:{args.port}")
            uvicorn.run(app, host=args.host, port=args.port)
            return 0
        except Exception:
            # Fallback to app.server
            from app.server import create_app
            from google_ai_search.config import get_config
            cfg = get_config()
            cfg.port = args.port
            cfg.debug = args.debug
            flask_app = create_app(cfg)
            print(f"🚀 Starting Grip AI Search server on http://{args.host}:{args.port}")
            flask_app.run(host=args.host, port=args.port, debug=args.debug)
            return 0

    if args.command in ("search", "query"):
        client = Grip(provider=args.provider)
        if args.json:
            res = client.query(args.query, session_id=args.session_id, provider=args.provider)
            print(json.dumps(res.to_dict(), indent=2))
            return 0

        if args.no_stream:
            res = client.query(args.query, session_id=args.session_id, provider=args.provider)
            print(res.answer)
            return 0

        try:
            thought_printed = False
            for chunk in client.stream(args.query, session_id=args.session_id, provider=args.provider):
                if chunk.event == "thinking" and chunk.thinking and not thought_printed:
                    thought_printed = True
                    print(f"💭 [{chunk.thinking}]", flush=True)
                elif chunk.event == "delta" and chunk.delta:
                    sys.stdout.write(chunk.delta)
                    sys.stdout.flush()
            sys.stdout.write("\n")
            return 0
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.command in ("chat", "session"):
        client = Grip(provider=args.provider)
        session = client.create_session(title=args.title)
        print(f"✨ Started Grip interactive session ({session.session_id}) [Provider: {args.provider}]")
        print("Type your questions below. Type 'exit' or 'quit' to end.\n")

        while True:
            try:
                query = input("\n[You] > ").strip()
                if not query:
                    continue
                if query.lower() in ("exit", "quit"):
                    print("Goodbye!")
                    break
                print("\n[Grip AI] > ", end="", flush=True)
                for chunk in client.stream(query, session_id=session.session_id, provider=args.provider):
                    if chunk.event == "delta" and chunk.delta:
                        sys.stdout.write(chunk.delta)
                        sys.stdout.flush()
                sys.stdout.write("\n")
            except (KeyboardInterrupt, EOFError):
                print("\nSession ended.")
                break
            except Exception as exc:
                print(f"Error: {exc}", file=sys.stderr)
        return 0

    if args.command == "rules":
        client = Grip()
        if args.identity:
            client.rules.set_identity(args.identity)
            print(f"✅ Set identity: {args.identity}")
        if args.format:
            client.rules.set_response_format(args.format)
            print(f"✅ Set response format: {args.format}")
        if args.add:
            r = client.rules.add(args.add)
            print(f"✅ Added rule: {r.name}")
        if args.list or (not args.identity and not args.format and not args.add):
            active_rules = client.rules.list(enabled_only=True)
            print("\nActive System Rules:")
            for rule in active_rules:
                print(f"• [P{rule.priority}] {rule.name}: {rule.content}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
