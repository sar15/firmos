import asyncio
import asyncpg
import os

async def main():
    db_url = os.environ.get("DATABASE_URL", "postgresql://firmos:firmos_pass@localhost:5432/firmos")
    conn = await asyncpg.connect(db_url)
    await conn.execute("DELETE FROM connections WHERE connector_id = 'c1'")
    print("Deleted Zoho connection")
    await conn.close()

asyncio.run(main())
