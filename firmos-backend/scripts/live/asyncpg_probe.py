import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect('postgresql://test:test@localhost:5432/test')
        row = await conn.fetchrow('SELECT 1 as id')
        try:
            print("id:", row['id'])
            print("client_id:", row.get('client_id', 'unknown'))
        except Exception as e:
            print(f"Error accessing client_id: {type(e).__name__}: {e}")
        await conn.close()
    except Exception as e:
        print(f"Connection error: {e}")

asyncio.run(main())
