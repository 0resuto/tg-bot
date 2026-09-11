"""Production Web Dashboard and Control Panel launcher."""

from __future__ import annotations

import argparse

from bot.web.config import WebConfig
from bot.web.server import run_web_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Telegram Memory Bot - Production Control Panel")
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to bind (default: 127.0.0.1)"
    )
    parser.add_argument("--port", type=int, default=8080, help="Port to run on (default: 8080)")
    parser.add_argument(
        "--enable-simulator",
        "--simulator",
        dest="enable_simulator",
        action="store_true",
        default=False,
        help="Explicitly enable the chat simulator in dashboard",
    )
    args = parser.parse_args()

    config = WebConfig(
        host=args.host,
        port=args.port,
        enable_simulator=args.enable_simulator,
    )
    run_web_server(config)


if __name__ == "__main__":
    main()
