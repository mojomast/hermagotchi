"""Write-transaction helper local to the shop slice."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def write_transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """Own a BEGIN IMMEDIATE transaction, or join one already in progress."""
    started_here = not conn.in_transaction
    if started_here:
        conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        if started_here:
            conn.rollback()
        raise
    else:
        if started_here:
            conn.commit()
