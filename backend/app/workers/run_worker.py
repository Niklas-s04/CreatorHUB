from __future__ import annotations

import os
from rq import Worker
from app.workers.queue import redis_conn

if __name__ == "__main__":
    # Standard-Queue verarbeiten.
    Worker(["default"], connection=redis_conn).work(with_scheduler=True)
