"""Entry point: python -m app.opcua_agent"""

from __future__ import annotations

import asyncio
import contextlib
import sys

from app.opcua_agent.main import run_agent


def main() -> None:
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_agent())
    sys.exit(0)


if __name__ == "__main__":
    main()
