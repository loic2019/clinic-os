"""
Atomic document number generator (spec section 56).

Uses a single INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING
statement so the increment is atomic at the database level — safe under
concurrent requests from multiple users without any application-level
locking. Must be called with the SAME session/transaction that will
persist the entity the number is for, so a rolled-back creation does
not "burn" a number silently (a small gap in numbering on rollback is
acceptable and standard practice; a duplicate number is not).
"""

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def generate_number(db: AsyncSession, *, key: str, prefix: str, digits: int = 6) -> str:
    year = datetime.now(timezone.utc).year

    result = await db.execute(
        text(
            """
            INSERT INTO numbering_sequences (id, key, year, last_value)
            VALUES (gen_random_uuid(), :key, :year, 1)
            ON CONFLICT (key, year)
            DO UPDATE SET last_value = numbering_sequences.last_value + 1
            RETURNING last_value
            """
        ),
        {"key": key, "year": year},
    )
    next_value = result.scalar_one()
    return f"{prefix}-{year}-{next_value:0{digits}d}"
