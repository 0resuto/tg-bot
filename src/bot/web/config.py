"""Configuration parameters for the web dashboard server."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WebConfig:
    """Settings specifically governing the web dashboard server."""

    host: str = os.getenv("WEB_HOST", "127.0.0.1")
    port: int = int(os.getenv("WEB_PORT", "8080"))
    enable_simulator: bool = False
    api_key: str = os.getenv("WEB_API_KEY", "")
    static_dir: Path = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
    dev_static_dir: Path = Path(__file__).resolve().parent.parent.parent.parent / "frontend"
