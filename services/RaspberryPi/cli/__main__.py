"""Entry point: `python -m cli ...`."""

import asyncio
import sys

from .cli import main


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
