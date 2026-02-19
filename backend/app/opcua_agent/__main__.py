"""Entry point: python -m app.opcua_agent"""

from __future__ import annotations

import asyncio
import sys

from app.opcua_agent.main import run_agent


def main() -> None:
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
