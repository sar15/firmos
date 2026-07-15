"""Run the durable worker and retry scheduler in one Render worker."""

import asyncio

from automation.scheduler import serve as serve_scheduler
from automation.worker import serve as serve_worker
from core.database import Database


async def main() -> None:
    await Database.connect()
    try:
        await asyncio.gather(
            serve_worker(Database.pool),
            serve_scheduler(Database.pool),
        )
    finally:
        await Database.close()


if __name__ == "__main__":
    asyncio.run(main())
