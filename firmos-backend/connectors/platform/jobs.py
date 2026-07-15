"""Durable cursor-based sync job state."""
async def checkpoint(conn, job_id: str, *, cursor: str | None, processed_count: int,
                     processed_total_paise: int, partial: bool) -> None:
    await conn.execute(
        """UPDATE connector_sync_jobs SET cursor=$1,processed_count=$2,processed_total_paise=$3,
           completeness=$4,status=$5 WHERE id=$6""",
        cursor, processed_count, processed_total_paise, "PARTIAL" if partial else "COMPLETE",
        "QUEUED" if partial else "SUCCEEDED", job_id,
    )


def totals_match(expected_count: int | None, processed_count: int,
                 expected_total_paise: int | None, processed_total_paise: int) -> bool:
    return (expected_count is None or expected_count == processed_count) and (
        expected_total_paise is None or expected_total_paise == processed_total_paise)
