from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.product import Product, ProductStatus
from app.services.audit import record_audit_log

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AutoArchiveRule:
    source_status: ProductStatus
    after_days: int
    target_status: ProductStatus = ProductStatus.archived
    label: str | None = None

    @property
    def name(self) -> str:
        return self.label or f"{self.source_status.value}_to_{self.target_status.value}"


AUTO_ARCHIVE_RULES: list[AutoArchiveRule] = []
if settings.AUTO_ARCHIVE_SOLD_AFTER_DAYS > 0:
    AUTO_ARCHIVE_RULES.append(
        AutoArchiveRule(
            source_status=ProductStatus.sold,
            target_status=ProductStatus.archived,
            after_days=settings.AUTO_ARCHIVE_SOLD_AFTER_DAYS,
            label="sold_after_days",
        )
    )


def apply_auto_archive_rules(db: Session, *, now: datetime | None = None) -> dict[str, Any]:
    """Apply configured auto-archive rules inside the provided session."""
    now = now or datetime.now(timezone.utc)
    summary: dict[str, Any] = {
        "run_at": now.isoformat(),
        "total_archived": 0,
        "rules": [],
    }

    if not AUTO_ARCHIVE_RULES:
        return summary

    for rule in AUTO_ARCHIVE_RULES:
        cutoff = now - timedelta(days=rule.after_days)
        candidates = (
            db.query(Product)
            .filter(Product.status == rule.source_status)
            .filter(Product.status_changed_at <= cutoff)
            .all()
        )

        archived_ids: list[str] = []
        for product in candidates:
            product.status = rule.target_status
            product.status_changed_at = now
            archived_ids.append(str(product.id))
            record_audit_log(
                db,
                actor=None,
                actor_label="system:auto-archive",
                action="product.auto_archive",
                entity_type="product",
                entity_id=str(product.id),
                description=f"Auto-archived after {rule.after_days} days in status {rule.source_status.value}",
                before={"status": rule.source_status.value},
                after={"status": rule.target_status.value},
                metadata={"rule": rule.name},
            )

        if archived_ids:
            summary["total_archived"] += len(archived_ids)

        summary["rules"].append(
            {
                "name": rule.name,
                "source_status": rule.source_status.value,
                "target_status": rule.target_status.value,
                "after_days": rule.after_days,
                "affected": len(archived_ids),
                "ids": archived_ids,
            }
        )

    if summary["total_archived"]:
        db.commit()
    return summary


def run_auto_archive_once() -> dict[str, Any]:
    db = SessionLocal()
    try:
        result = apply_auto_archive_rules(db)
        if result.get("total_archived") == 0:
            db.rollback()
        return result
    finally:
        db.close()


async def auto_archive_daemon(
    interval_minutes: int | None = None,
    initial_delay_seconds: int = 30,
) -> None:
    """Background loop that periodically applies auto-archive rules."""
    if interval_minutes is None:
        interval_minutes = settings.AUTO_ARCHIVE_INTERVAL_MINUTES
    interval_seconds = max(300, interval_minutes * 60)

    await asyncio.sleep(max(0, initial_delay_seconds))

    while True:
        try:
            result = await asyncio.to_thread(run_auto_archive_once)
            archived = result.get("total_archived", 0)
            if archived:
                logger.info("Auto-archive: archived %s product(s)", archived)
            else:
                logger.debug("Auto-archive: nothing to archive this run")
        except asyncio.CancelledError:
            logger.info("Auto-archive daemon cancelled")
            raise
        except Exception:
            logger.exception("Auto-archive run failed")
        await asyncio.sleep(interval_seconds)
