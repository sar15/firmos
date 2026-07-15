import asyncio
from core.database import init_db_pool

async def main():
    pool = await init_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM connections WHERE connector_id = 'c1'")
        print("Zoho connection wiped from DB.")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
