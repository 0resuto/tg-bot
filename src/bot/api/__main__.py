"""CLI entry point for running the API server and dashboard via python -m bot.api."""

from __future__ import annotations

import argparse

from bot.api.server import run_web_server
from bot.config import Settings, WebConfig


def main() -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(
        description="Telegram Memory Bot Web Dashboard & Control Panel"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind (default: WEB_HOST or 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to run on (default: WEB_PORT or 8080)",
    )
    parser.add_argument(
        "--simulator",
        action="store_true",
        default=None,
        help="Enable interactive chat simulator testing sandbox (default: WEB_ENABLE_SIMULATOR)",
    )
    args = parser.parse_args()

    config = settings.to_web_config(enable_simulator=args.simulator)
    if args.host is not None or args.port is not None:
        config = WebConfig(
            host=args.host or config.host,
            port=args.port or config.port,
            enable_simulator=config.enable_simulator,
        )
    run_web_server(config)


if __name__ == "__main__":
    main()
