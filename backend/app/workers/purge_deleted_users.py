from __future__ import annotations

from app.workers.tasks.purge_deleted_users import purge_deleted_users

__all__ = ["purge_deleted_users"]


if __name__ == "__main__":
    print(purge_deleted_users())
