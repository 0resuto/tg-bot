"""CLI entry point for running the web dashboard via python -m bot.web."""

from __future__ import annotations

import argparse

from bot.web.config import WebConfig
from bot.web.server import run_web_server


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Telegram Memory Bot Web Dashboard & Control Panel"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to bind (default: 127.0.0.1)"
    )
    parser.add_argument("--port", type=int, default=8080, help="Port to run on (default: 8080)")
    parser.add_argument(
        "--simulator",
        action="store_true",
        default=False,
        help="Enable interactive chat simulator testing sandbox",
    )
    args = parser.parse_args()

    config = WebConfig(
        host=args.host,
        port=args.port,
        enable_simulator=args.simulator,
    )
    run_web_server(config)


if __name__ == "__main__":
    main()
