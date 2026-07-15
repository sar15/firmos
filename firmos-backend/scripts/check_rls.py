"""Fail when an application table in the public schema lacks RLS."""

import asyncio
import sys

import asyncpg


async def check(database_url: str) -> None:
    connection = await asyncpg.connect(database_url)
    try:
        rows = await connection.fetch(
            """SELECT c.relname FROM pg_class c
               JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE n.nspname='public' AND c.relkind='r'
                 AND NOT c.relrowsecurity
               ORDER BY c.relname"""
        )
    finally:
        await connection.close()
    if rows:
        names = ", ".join(row["relname"] for row in rows)
        raise SystemExit(f"Public tables without RLS: {names}")
    print("All public application tables have RLS enabled.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_rls.py postgresql://...")
    asyncio.run(check(sys.argv[1]))
