"""The stored embedding vector width.

Fixed to bge-m3's 1024. This is deliberately a constant rather than a setting:
changing it is a new migration plus a full re-embed by construction (ADR-0002),
so a runtime knob could only ever be set to one valid value -- and setting it to
anything else would produce vectors the column cannot store.

The ORM column and the client's response validation both read it from here so
they cannot disagree. The Alembic migration repeats the literal on purpose:
migrations are frozen snapshots and must not import application code.
"""

EMBEDDING_DIMENSIONS = 1024
