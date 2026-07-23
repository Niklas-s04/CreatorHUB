from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Depends, Query
from sqlalchemy import (
    Integer,
    String,
    and_,
    case,
    cast,
    false,
    func,
    literal,
    literal_column,
    or_,
)
from sqlalchemy.orm import Query as SAQuery
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.api.deps import get_current_user, get_db
from app.core.authorization import Permission, has_permission
from app.models.asset import Asset, AssetOwnerType, AssetReviewState
from app.models.content import ContentItem, ContentTask, TaskPriority, TaskStatus
from app.models.deal import DealDraft, DealDraftStatus
from app.models.email import EmailDraft
from app.models.product import Product
from app.models.registration_request import RegistrationRequest, RegistrationRequestStatus
from app.models.user import User, UserRole
from app.schemas.operations import (
    OperationDueFilter,
    OperationInboxItem,
    OperationInboxOut,
    OperationPriority,
)
from app.services.deal_checklists import missing_required_items

router = APIRouter()

_PRIORITY_RANK: dict[OperationPriority, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}
_DEFAULT_SOURCE_BATCH_SIZE = 100


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_aware_datetime(value: datetime | date | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)


@dataclass(frozen=True)
class _OperationFilters:
    now: datetime
    today: date
    search: str | None
    assignee_user: str | None
    role: UserRole | None
    priority: OperationPriority | None
    due: OperationDueFilter


@dataclass(frozen=True)
class _OperationSource:
    total: int
    load_page: Callable[[int, int], list[OperationInboxItem]]


@dataclass
class _OperationSourceCursor:
    source: _OperationSource
    fetched: int = 0
    position: int = 0
    buffer: list[OperationInboxItem] = field(default_factory=list)

    def next_item(self, *, batch_size: int) -> OperationInboxItem | None:
        if self.position >= len(self.buffer):
            if self.fetched >= self.source.total:
                return None
            requested = min(batch_size, self.source.total - self.fetched)
            self.buffer = self.source.load_page(self.fetched, requested)
            self.position = 0
            self.fetched += len(self.buffer)
            if not self.buffer:
                # Concurrent deletes may make the preceding count stale. Stop instead
                # of repeatedly querying the same empty page.
                self.fetched = self.source.total
                return None

        item = self.buffer[self.position]
        self.position += 1
        return item


def _normalize_optional_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _concat_sql_text(*parts: Any) -> ColumnElement[str]:
    expression: ColumnElement[str] = cast(literal(""), String)
    for index, part in enumerate(parts):
        if index:
            expression = expression + literal(" ")
        expression = expression + cast(func.coalesce(part, ""), String)
    return expression


def _apply_search(
    query: SAQuery,
    *,
    search: str | None,
    parts: tuple[Any, ...],
) -> SAQuery:
    if not search:
        return query
    haystack = func.lower(_concat_sql_text(*parts))
    return query.filter(haystack.like(_like_pattern(search), escape="\\"))


def _fixed_source_matches(
    filters: _OperationFilters,
    *,
    responsible_role: UserRole,
    priority: OperationPriority | None = None,
) -> bool:
    if filters.role is not None and filters.role != responsible_role:
        return False
    if filters.assignee_user is not None and filters.assignee_user != "unassigned":
        return False
    if priority is not None and filters.priority is not None and filters.priority != priority:
        return False
    return True


def _apply_datetime_due_filter(
    query: SAQuery,
    *,
    column: Any,
    offset_days: int,
    filters: _OperationFilters,
) -> SAQuery:
    if filters.due == "all":
        return query
    if filters.due == "none":
        return query.filter(column.is_(None))

    today_start = datetime.combine(filters.today, time.min, tzinfo=timezone.utc)
    base_start = today_start - timedelta(days=offset_days)
    if filters.due == "overdue":
        return query.filter(column.isnot(None), column < base_start)
    if filters.due == "today":
        return query.filter(
            column.isnot(None),
            column >= base_start,
            column < base_start + timedelta(days=1),
        )
    return query.filter(
        column.isnot(None),
        column >= base_start,
        column < base_start + timedelta(days=8),
    )


def _apply_date_due_filter(
    query: SAQuery,
    *,
    column: Any,
    filters: _OperationFilters,
) -> SAQuery:
    if filters.due == "all":
        return query
    if filters.due == "none":
        return query.filter(column.is_(None))
    if filters.due == "overdue":
        return query.filter(column.isnot(None), column < filters.today)
    if filters.due == "today":
        return query.filter(column == filters.today)
    return query.filter(
        column.isnot(None),
        column >= filters.today,
        column <= filters.today + timedelta(days=7),
    )


def _risk_count_expression(db: Session) -> ColumnElement[int]:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        return literal_column(
            """
            CASE
                WHEN email_drafts.risk_flags IS JSON ARRAY
                THEN jsonb_array_length(email_drafts.risk_flags::jsonb)
                ELSE 0
            END
            """,
            type_=Integer(),
        )
    if dialect == "sqlite":
        return literal_column(
            """
            CASE
                WHEN json_valid(email_drafts.risk_flags)
                THEN CASE
                    WHEN json_type(email_drafts.risk_flags) = 'array'
                    THEN json_array_length(email_drafts.risk_flags)
                    ELSE 0
                END
                ELSE 0
            END
            """,
            type_=Integer(),
        )
    return cast(literal(0), Integer)


def _deal_missing_keys_expression(db: Session) -> ColumnElement[str]:
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        return literal_column(
            """
            (
                SELECT string_agg(
                    COALESCE(NULLIF(deal_item.value->>'key', ''), 'unknown'),
                    ', ' ORDER BY deal_item.ordinality
                )
                FROM json_array_elements(
                    COALESCE(deal_drafts.checklist, '[]'::json)
                ) WITH ORDINALITY AS deal_item(value, ordinality)
                WHERE COALESCE((deal_item.value->>'required')::boolean, false)
                  AND NOT COALESCE((deal_item.value->>'done')::boolean, false)
            )
            """,
            type_=String(),
        )
    return literal_column(
        """
        (
            SELECT group_concat(
                COALESCE(NULLIF(json_extract(deal_item.value, '$.key'), ''), 'unknown'),
                ', '
            )
            FROM json_each(
                CASE
                    WHEN json_valid(deal_drafts.checklist)
                    THEN deal_drafts.checklist
                    ELSE '[]'
                END
            ) AS deal_item
            WHERE COALESCE(json_extract(deal_item.value, '$.required'), 0) != 0
              AND COALESCE(json_extract(deal_item.value, '$.done'), 0) = 0
        )
        """,
        type_=String(),
    )


def _overdue_days_expression(db: Session, *, today: date) -> ColumnElement[int]:
    if db.get_bind().dialect.name == "postgresql":
        return cast(literal(today) - ContentTask.due_date, Integer)
    return cast(
        func.julianday(literal(today.isoformat())) - func.julianday(ContentTask.due_date),
        Integer,
    )


def _operation_sort_key(
    item: OperationInboxItem,
) -> tuple[int, datetime, str]:
    return (
        _PRIORITY_RANK[item.priority],
        _to_aware_datetime(item.due_at) or datetime.max.replace(tzinfo=timezone.utc),
        item.id,
    )


def _make_source(
    query: SAQuery,
    *,
    order_by: tuple[Any, ...],
    mapper: Callable[[Any], OperationInboxItem],
) -> _OperationSource | None:
    total = int(query.order_by(None).count())
    if total <= 0:
        return None

    def _load_page(page_offset: int, page_limit: int) -> list[OperationInboxItem]:
        rows = query.order_by(None).order_by(*order_by).offset(page_offset).limit(page_limit).all()
        return [mapper(row) for row in rows]

    return _OperationSource(total=total, load_page=_load_page)


def _merge_sources(
    sources: list[_OperationSource],
    *,
    offset: int,
    limit: int,
) -> list[OperationInboxItem]:
    cursors = [_OperationSourceCursor(source=source) for source in sources]
    batch_size = max(1, min(_DEFAULT_SOURCE_BATCH_SIZE, max(limit, 25)))
    heap: list[tuple[tuple[int, datetime, str], int, OperationInboxItem]] = []

    for source_index, cursor in enumerate(cursors):
        item = cursor.next_item(batch_size=batch_size)
        if item is not None:
            heapq.heappush(heap, (_operation_sort_key(item), source_index, item))

    consumed = 0
    result: list[OperationInboxItem] = []
    while heap and len(result) < limit:
        _, source_index, item = heapq.heappop(heap)
        if consumed >= offset:
            result.append(item)
        consumed += 1

        next_item = cursors[source_index].next_item(batch_size=batch_size)
        if next_item is not None:
            heapq.heappush(heap, (_operation_sort_key(next_item), source_index, next_item))

    return result


def _asset_source(
    db: Session,
    *,
    filters: _OperationFilters,
) -> _OperationSource | None:
    if not _fixed_source_matches(filters, responsible_role=UserRole.editor):
        return None

    states = [
        AssetReviewState.quarantine,
        AssetReviewState.pending_review,
        AssetReviewState.needs_review,
        AssetReviewState.pending,
    ]
    old_cutoff = filters.now - timedelta(days=3)
    is_critical = Asset.review_state == AssetReviewState.quarantine
    is_high = and_(
        Asset.review_state != AssetReviewState.quarantine,
        Asset.created_at <= old_cutoff,
    )
    priority_rank = case((is_critical, 0), (is_high, 1), else_=2)

    query = db.query(Asset).filter(Asset.review_state.in_(states))
    if filters.priority == "critical":
        query = query.filter(is_critical)
    elif filters.priority == "high":
        query = query.filter(is_high)
    elif filters.priority == "medium":
        query = query.filter(
            Asset.review_state != AssetReviewState.quarantine,
            or_(Asset.created_at > old_cutoff, Asset.created_at.is_(None)),
        )
    elif filters.priority == "low":
        query = query.filter(false())

    query = _apply_datetime_due_filter(
        query,
        column=Asset.created_at,
        offset_days=2,
        filters=filters,
    )
    query = _apply_search(
        query,
        search=filters.search,
        parts=(
            func.coalesce(Asset.title, "Asset ohne Titel"),
            literal("Review erforderlich (") + cast(Asset.review_state, String) + literal(")"),
            literal(""),
            literal("asset_review"),
        ),
    )

    def _map(asset: Asset) -> OperationInboxItem:
        due_at = asset.created_at + timedelta(days=2) if asset.created_at else None
        created_at = _to_aware_datetime(asset.created_at)
        is_old = bool(created_at is not None and created_at <= old_cutoff)
        priority_value: OperationPriority = (
            "critical"
            if asset.review_state == AssetReviewState.quarantine
            else ("high" if is_old else "medium")
        )
        return OperationInboxItem(
            id=f"asset:{asset.id}",
            kind="asset_review",
            title=asset.title or "Asset ohne Titel",
            description=f"Review erforderlich ({asset.review_state.value})",
            source_route="/assets",
            source_id=str(asset.id),
            priority=priority_value,
            escalation=priority_value in {"high", "critical"},
            due_at=due_at,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
            assignee_username=None,
            responsible_role="editor",
        )

    return _make_source(
        query,
        order_by=(
            priority_rank.asc(),
            Asset.created_at.is_(None),
            Asset.created_at.asc(),
            Asset.id.asc(),
        ),
        mapper=_map,
    )


def _registration_source(
    db: Session,
    *,
    filters: _OperationFilters,
) -> _OperationSource | None:
    if not _fixed_source_matches(filters, responsible_role=UserRole.admin):
        return None

    escalation_cutoff = filters.now - timedelta(hours=48)
    is_high = RegistrationRequest.created_at <= escalation_cutoff
    priority_rank = case((is_high, 1), else_=2)
    query = db.query(RegistrationRequest).filter(
        RegistrationRequest.status == RegistrationRequestStatus.pending
    )
    if filters.priority == "high":
        query = query.filter(is_high)
    elif filters.priority == "medium":
        query = query.filter(
            or_(
                RegistrationRequest.created_at > escalation_cutoff,
                RegistrationRequest.created_at.is_(None),
            )
        )
    elif filters.priority in {"critical", "low"}:
        query = query.filter(false())

    query = _apply_datetime_due_filter(
        query,
        column=RegistrationRequest.created_at,
        offset_days=1,
        filters=filters,
    )
    query = _apply_search(
        query,
        search=filters.search,
        parts=(
            literal("Registrierung: ") + RegistrationRequest.username,
            literal("Freigabe ausstehend"),
            literal(""),
            literal("registration_approval"),
        ),
    )

    def _map(request: RegistrationRequest) -> OperationInboxItem:
        due_at = request.created_at + timedelta(days=1) if request.created_at is not None else None
        created_at = _to_aware_datetime(request.created_at)
        escalated = bool(created_at is not None and created_at <= escalation_cutoff)
        priority_value: OperationPriority = "high" if escalated else "medium"
        return OperationInboxItem(
            id=f"registration:{request.id}",
            kind="registration_approval",
            title=f"Registrierung: {request.username}",
            description="Freigabe ausstehend",
            source_route="/admin",
            source_id=str(request.id),
            priority=priority_value,
            escalation=escalated,
            due_at=due_at,
            created_at=request.created_at,
            updated_at=request.updated_at,
            assignee_username=None,
            responsible_role="admin",
        )

    return _make_source(
        query,
        order_by=(
            priority_rank.asc(),
            RegistrationRequest.created_at.is_(None),
            RegistrationRequest.created_at.asc(),
            RegistrationRequest.id.asc(),
        ),
        mapper=_map,
    )


def _email_source(
    db: Session,
    *,
    filters: _OperationFilters,
) -> _OperationSource | None:
    if not _fixed_source_matches(filters, responsible_role=UserRole.editor):
        return None

    risk_count = _risk_count_expression(db)
    priority_rank = case((risk_count >= 3, 0), else_=1)
    query = db.query(EmailDraft, risk_count.label("risk_flag_count")).filter(
        EmailDraft.approved.is_(False),
        EmailDraft.risk_flags.isnot(None),
        EmailDraft.risk_flags != "",
        EmailDraft.risk_flags != "[]",
    )
    if filters.priority == "critical":
        query = query.filter(risk_count >= 3)
    elif filters.priority == "high":
        query = query.filter(risk_count < 3)
    elif filters.priority in {"medium", "low"}:
        query = query.filter(false())

    query = _apply_datetime_due_filter(
        query,
        column=EmailDraft.updated_at,
        offset_days=1,
        filters=filters,
    )
    query = _apply_search(
        query,
        search=filters.search,
        parts=(
            func.coalesce(EmailDraft.draft_subject, "Riskanter E-Mail-Entwurf"),
            cast(risk_count, String) + literal(" Risk-Flags"),
            literal(""),
            literal("email_risk"),
        ),
    )

    def _map(row: Any) -> OperationInboxItem:
        draft, computed_risk_count = row
        count = int(computed_risk_count or 0)
        priority_value: OperationPriority = "critical" if count >= 3 else "high"
        return OperationInboxItem(
            id=f"email:{draft.id}",
            kind="email_risk",
            title=draft.draft_subject or "Riskanter E-Mail-Entwurf",
            description=f"{count} Risk-Flags",
            source_route="/email",
            source_id=str(draft.id),
            priority=priority_value,
            escalation=True,
            due_at=draft.updated_at + timedelta(days=1) if draft.updated_at else None,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
            assignee_username=None,
            responsible_role="editor",
        )

    return _make_source(
        query,
        order_by=(
            priority_rank.asc(),
            EmailDraft.updated_at.is_(None),
            EmailDraft.updated_at.asc(),
            EmailDraft.id.asc(),
        ),
        mapper=_map,
    )


def _content_source(
    db: Session,
    *,
    filters: _OperationFilters,
) -> _OperationSource | None:
    if filters.role is not None and filters.role != UserRole.editor:
        return None

    overdue_days = _overdue_days_expression(db, today=filters.today)
    non_explicit_priority = ~ContentTask.priority.in_([TaskPriority.critical, TaskPriority.high])
    is_critical = or_(
        ContentTask.priority == TaskPriority.critical,
        and_(
            non_explicit_priority,
            ContentTask.due_date <= filters.today - timedelta(days=7),
        ),
    )
    is_high = or_(
        ContentTask.priority == TaskPriority.high,
        and_(
            non_explicit_priority,
            ContentTask.due_date <= filters.today - timedelta(days=3),
        ),
    )
    priority_rank = case((is_critical, 0), (is_high, 1), else_=2)
    role_assignee = literal("role:") + cast(ContentTask.assignee_role, String)
    assignee = case(
        (ContentTask.assignee_user_id.isnot(None), User.username),
        (ContentTask.assignee_role.isnot(None), role_assignee),
        else_=None,
    )

    query = (
        db.query(ContentTask, assignee.label("operation_assignee"))
        .outerjoin(User, User.id == ContentTask.assignee_user_id)
        .filter(
            ContentTask.status != TaskStatus.done,
            ContentTask.due_date.isnot(None),
            ContentTask.due_date < filters.today,
        )
    )
    if filters.assignee_user is not None:
        query = query.filter(
            func.lower(func.trim(func.coalesce(assignee, "unassigned"))) == filters.assignee_user
        )
    if filters.priority == "critical":
        query = query.filter(is_critical)
    elif filters.priority == "high":
        query = query.filter(and_(~is_critical, is_high))
    elif filters.priority == "medium":
        query = query.filter(~is_critical, ~is_high)
    elif filters.priority == "low":
        query = query.filter(false())

    query = _apply_date_due_filter(
        query,
        column=ContentTask.due_date,
        filters=filters,
    )
    query = _apply_search(
        query,
        search=filters.search,
        parts=(
            literal("Überfällige Task: ") + cast(ContentTask.type, String),
            literal("Status ")
            + cast(ContentTask.status, String)
            + literal(" · Priorität ")
            + cast(ContentTask.priority, String)
            + literal(" · ")
            + cast(overdue_days, String)
            + literal(" Tage überfällig"),
            func.coalesce(assignee, ""),
            literal("content_overdue"),
        ),
    )

    def _map(row: Any) -> OperationInboxItem:
        task, assignee_username = row
        days = (filters.today - task.due_date).days if task.due_date else 0
        if task.priority == TaskPriority.critical:
            priority_value: OperationPriority = "critical"
        elif task.priority == TaskPriority.high:
            priority_value = "high"
        else:
            priority_value = "critical" if days >= 7 else "high" if days >= 3 else "medium"

        return OperationInboxItem(
            id=f"content:{task.id}",
            kind="content_overdue",
            title=f"Überfällige Task: {task.type.value}",
            description=(
                f"Status {task.status.value} · Priorität {task.priority.value} · {days} Tage überfällig"
            ),
            source_route="/content",
            source_id=str(task.id),
            priority=priority_value,
            escalation=priority_value in {"high", "critical"},
            due_at=task.due_date,
            created_at=task.created_at,
            updated_at=task.updated_at,
            assignee_username=assignee_username,
            responsible_role="editor",
        )

    return _make_source(
        query,
        order_by=(
            priority_rank.asc(),
            ContentTask.due_date.is_(None),
            ContentTask.due_date.asc(),
            ContentTask.id.asc(),
        ),
        mapper=_map,
    )


def _deal_source(
    db: Session,
    *,
    filters: _OperationFilters,
) -> _OperationSource | None:
    if not _fixed_source_matches(
        filters,
        responsible_role=UserRole.editor,
        priority="high",
    ):
        return None

    missing_keys = _deal_missing_keys_expression(db)
    query = db.query(DealDraft).filter(
        DealDraft.status.in_([DealDraftStatus.review, DealDraftStatus.negotiating]),
        missing_keys.isnot(None),
        missing_keys != "",
    )
    query = _apply_datetime_due_filter(
        query,
        column=DealDraft.updated_at,
        offset_days=1,
        filters=filters,
    )
    query = _apply_search(
        query,
        search=filters.search,
        parts=(
            func.coalesce(
                DealDraft.brand_name,
                DealDraft.contact_name,
                "Deal ohne Namen",
            ),
            literal("Pflichtpunkte offen: ") + func.coalesce(missing_keys, ""),
            literal(""),
            literal("deal_checklist"),
        ),
    )

    def _map(deal: DealDraft) -> OperationInboxItem:
        missing_items = missing_required_items(deal.checklist)
        return OperationInboxItem(
            id=f"deal-checklist:{deal.id}",
            kind="deal_checklist",
            title=deal.brand_name or deal.contact_name or "Deal ohne Namen",
            description=f"Pflichtpunkte offen: {', '.join(missing_items)}",
            source_route="/email",
            source_id=str(deal.id),
            priority="high",
            escalation=True,
            due_at=deal.updated_at + timedelta(days=1) if deal.updated_at else None,
            created_at=deal.created_at,
            updated_at=deal.updated_at,
            assignee_username=None,
            responsible_role="editor",
        )

    return _make_source(
        query,
        order_by=(
            DealDraft.updated_at.is_(None),
            DealDraft.updated_at.asc(),
            DealDraft.id.asc(),
        ),
        mapper=_map,
    )


def _product_source(
    db: Session,
    *,
    filters: _OperationFilters,
    gap: str,
    approved_asset_exists: Any,
    content_exists: Any,
    deal_exists: Any,
) -> _OperationSource | None:
    if gap == "asset":
        priority_value: OperationPriority = "high"
        offset_days = 2
        description = "Produkt ohne freigegebenes Asset (Medienbruch Produkt → Asset)"
        source_route = "/products"
        gap_filter = ~approved_asset_exists
    elif gap == "content":
        priority_value = "medium"
        offset_days = 3
        description = "Asset vorhanden, aber kein Content geplant (Bruch Asset → Content)"
        source_route = "/content"
        gap_filter = and_(approved_asset_exists, ~content_exists)
    else:
        priority_value = "medium"
        offset_days = 4
        description = (
            "Content vorhanden, aber kein Deal/Kommunikationslink (Bruch Content → Kommunikation)"
        )
        source_route = "/email"
        gap_filter = and_(approved_asset_exists, content_exists, ~deal_exists)

    if not _fixed_source_matches(
        filters,
        responsible_role=UserRole.editor,
        priority=priority_value,
    ):
        return None

    query = db.query(Product).filter(gap_filter)
    query = _apply_datetime_due_filter(
        query,
        column=Product.updated_at,
        offset_days=offset_days,
        filters=filters,
    )
    query = _apply_search(
        query,
        search=filters.search,
        parts=(
            Product.title,
            literal(description),
            literal(""),
            literal("workflow_gap"),
        ),
    )

    def _map(product: Product) -> OperationInboxItem:
        return OperationInboxItem(
            id=f"workflow-gap:{product.id}:{gap}",
            kind="workflow_gap",
            title=product.title,
            description=description,
            source_route=source_route,
            source_id=str(product.id),
            priority=priority_value,
            escalation=priority_value == "high",
            due_at=product.updated_at + timedelta(days=offset_days) if product.updated_at else None,
            created_at=product.created_at,
            updated_at=product.updated_at,
            assignee_username=None,
            responsible_role="editor",
        )

    return _make_source(
        query,
        order_by=(
            Product.updated_at.is_(None),
            Product.updated_at.asc(),
            Product.id.asc(),
        ),
        mapper=_map,
    )


def _product_sources(
    db: Session,
    *,
    filters: _OperationFilters,
) -> list[_OperationSource]:
    approved_asset_exists = (
        db.query(Asset.id)
        .filter(
            Asset.owner_type == AssetOwnerType.product,
            Asset.owner_id == Product.id,
            Asset.review_state == AssetReviewState.approved,
        )
        .exists()
    )
    content_exists = db.query(ContentItem.id).filter(ContentItem.product_id == Product.id).exists()
    deal_exists = db.query(DealDraft.id).filter(DealDraft.product_id == Product.id).exists()

    sources: list[_OperationSource] = []
    for gap in ("asset", "content", "deal"):
        source = _product_source(
            db,
            filters=filters,
            gap=gap,
            approved_asset_exists=approved_asset_exists,
            content_exists=content_exists,
            deal_exists=deal_exists,
        )
        if source is not None:
            sources.append(source)
    return sources


@router.get("/inbox", response_model=OperationInboxOut)
def operations_inbox(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    assignee_user: str | None = Query(default=None),
    role: UserRole | None = Query(default=None),
    priority: OperationPriority | None = Query(default=None),
    due: OperationDueFilter = Query(default="all"),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> OperationInboxOut:
    now = _now_utc()
    filters = _OperationFilters(
        now=now,
        today=now.date(),
        search=_normalize_optional_filter(q),
        assignee_user=_normalize_optional_filter(assignee_user),
        role=role,
        priority=priority,
        due=due,
    )
    sources: list[_OperationSource] = []

    if has_permission(current_user, Permission.asset_review):
        asset_source = _asset_source(db, filters=filters)
        if asset_source is not None:
            sources.append(asset_source)

    if has_permission(current_user, Permission.user_approve_registration):
        registration_source = _registration_source(db, filters=filters)
        if registration_source is not None:
            sources.append(registration_source)

    if has_permission(current_user, Permission.email_read) or has_permission(
        current_user, Permission.email_generate
    ):
        email_source = _email_source(db, filters=filters)
        if email_source is not None:
            sources.append(email_source)

    if has_permission(current_user, Permission.content_manage) or has_permission(
        current_user, Permission.content_read
    ):
        content_source = _content_source(db, filters=filters)
        if content_source is not None:
            sources.append(content_source)

    if has_permission(current_user, Permission.deal_manage) or has_permission(
        current_user, Permission.deal_read
    ):
        deal_source = _deal_source(db, filters=filters)
        if deal_source is not None:
            sources.append(deal_source)

    if has_permission(current_user, Permission.product_read):
        sources.extend(_product_sources(db, filters=filters))

    total_open = sum(source.total for source in sources)
    return OperationInboxOut(
        generated_at=now,
        total_open=total_open,
        items=_merge_sources(sources, offset=offset, limit=limit),
    )
