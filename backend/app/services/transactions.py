from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def transaction_boundary(db: Session) -> Generator[None, None, None]:
    try:
        yield
    except Exception:
        db.rollback()
        raise
    else:
        db.commit()
