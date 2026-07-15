"""Small scheduler that releases retry jobs; run as a separate service."""
import asyncio


async def tick(pool) -> int:
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute(
            """UPDATE finance_actions a SET status='QUEUED'
               FROM automation_jobs j WHERE j.aggregate_id=a.id::text
               AND j.status='RETRY_SCHEDULED' AND j.available_at<=NOW()
               AND a.status='RETRY_SCHEDULED'"""
        )
        result = await conn.execute(
            """UPDATE automation_jobs SET status='QUEUED',updated_at=NOW()
               WHERE status='RETRY_SCHEDULED' AND available_at<=NOW()"""
        )
    return int(result.rsplit(" ", 1)[-1])


async def serve(pool):
    while True:
        await tick(pool)
        await asyncio.sleep(30)


async def main():
    from core.database import Database
    await Database.connect()
    try: await serve(Database.pool)
    finally: await Database.close()


if __name__ == "__main__": asyncio.run(main())
