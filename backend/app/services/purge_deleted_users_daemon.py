"""
Daemon to periodically purge deleted users who requested deletion 30+ days ago.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.workers.tasks.purge_deleted_users import purge_deleted_users

logger = logging.getLogger(__name__)


async def purge_deleted_users_daemon() -> None:
    """
    Background daemon that periodically purges deleted users.
    Runs every 6 hours by default (configurable via PURGE_DELETED_USERS_INTERVAL_HOURS).
    """
    interval_hours = getattr(settings, "PURGE_DELETED_USERS_INTERVAL_HOURS", 6)
    interval_seconds = interval_hours * 3600

    logger.info(f"Starting purge_deleted_users_daemon. Will run every {interval_hours} hours.")

    while True:
        try:
            await asyncio.sleep(interval_seconds)

            logger.info("Starting scheduled purge of deleted users...")
            try:
                result = purge_deleted_users(grace_period_days=30)
                logger.info(f"Purge completed. Stats: {result}")
            except Exception as e:
                logger.error(f"Error running purge_deleted_users: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.info("purge_deleted_users_daemon cancelled")
            break
        except Exception as e:
            logger.error(f"Unexpected error in purge_deleted_users_daemon: {e}", exc_info=True)
            # Sleep for a short interval before retrying to avoid rapid failure loops
            await asyncio.sleep(60)
