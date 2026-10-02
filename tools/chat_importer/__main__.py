"""Direct module execution entrypoint: python -m tools.chat_importer."""

from __future__ import annotations

import sys

from tools.chat_importer.cli import main

if __name__ == "__main__":
    sys.exit(main())
