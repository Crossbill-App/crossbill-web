from sqlalchemy.ext.asyncio import AsyncSession

LIKE_ESCAPE_CHAR = "\\"


def is_postgres(db: AsyncSession) -> bool:
    """Whether this session talks to PostgreSQL rather than the SQLite test DB.

    Several adapters keep a Python or JSON fallback so the suite can run off
    Postgres; this is the one place that spells out how the dialect is detected.
    """
    return db.bind.dialect.name == "postgresql"


def escape_like_pattern(text: str) -> str:
    """Escape LIKE/ILIKE wildcard characters in user-supplied search text.

    Pair with ``.ilike(pattern, escape=LIKE_ESCAPE_CHAR)`` so ``%`` and ``_`` in
    user input match literally instead of acting as wildcards.
    """
    return (
        text.replace(LIKE_ESCAPE_CHAR, LIKE_ESCAPE_CHAR * 2)
        .replace("%", LIKE_ESCAPE_CHAR + "%")
        .replace("_", LIKE_ESCAPE_CHAR + "_")
    )


async def commit_or_rollback(session: AsyncSession) -> None:
    """Commit, rolling the session back if the commit fails.

    A caller that carries on after a failed write -- a compensation, or a derived-data
    write allowed to fail -- would otherwise hit PendingRollbackError on its next statement.
    """
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
