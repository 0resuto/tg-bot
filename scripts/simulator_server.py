"""Interactive Web Testing Simulator launcher (dev sandbox mode)."""

from __future__ import annotations

import argparse

from bot.api.server import run_web_server
from bot.config import WebConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Telegram Memory Bot - Dev Simulator (Real Production Stack)"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to bind (default: 127.0.0.1)"
    )
    parser.add_argument("--port", type=int, default=8080, help="Port to run on (default: 8080)")
    args = parser.parse_args()

    config = WebConfig(
        host=args.host,
        port=args.port,
        enable_simulator=True,
    )
    run_web_server(config)


if __name__ == "__main__":
    main()
