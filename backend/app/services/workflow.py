from __future__ import annotations

from collections.abc import Iterable

from app.models.base import utcnow
from app.models.user import User
from app.models.workflow import WorkflowStatus
from app.services.errors import BusinessRuleViolation

WORKFLOW_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.draft: {WorkflowStatus.in_review, WorkflowStatus.archived},
    WorkflowStatus.in_review: {WorkflowStatus.approved, WorkflowStatus.rejected, WorkflowStatus.draft},
    WorkflowStatus.approved: {
        WorkflowStatus.published,
        WorkflowStatus.archived,
        WorkflowStatus.in_review,
    },
    WorkflowStatus.rejected: {WorkflowStatus.draft, WorkflowStatus.in_review, WorkflowStatus.archived},
    WorkflowStatus.published: {WorkflowStatus.in_review, WorkflowStatus.archived},
    WorkflowStatus.archived: {WorkflowStatus.in_review},
}

WORKFLOW_REVIEW_DECISION_STATES: set[WorkflowStatus] = {
    WorkflowStatus.approved,
    WorkflowStatus.rejected,
    WorkflowStatus.published,
}


def validate_workflow_status_change(
    *,
    current_status: WorkflowStatus,
    target_status: WorkflowStatus,
    review_reason: str | None,
) -> None:
    if current_status != target_status:
        allowed = WORKFLOW_TRANSITIONS.get(current_status, set())
        if target_status not in allowed:
            allowed_text = ", ".join(sorted(value.value for value in allowed)) or "<none>"
            raise BusinessRuleViolation(
                f"Invalid workflow transition: {current_status.value} -> {target_status.value}. Allowed: {allowed_text}"
            )

    if target_status in WORKFLOW_REVIEW_DECISION_STATES and not (review_reason or "").strip():
        raise BusinessRuleViolation(
            f"review_reason required when workflow_status is {target_status.value}"
        )


def requires_re_review(
    *,
    current_status: WorkflowStatus,
    changed_fields: Iterable[str],
    relevant_fields: set[str],
) -> bool:
    if current_status not in {WorkflowStatus.approved, WorkflowStatus.published}:
        return False
    return any(field in relevant_fields for field in changed_fields)


def auto_re_review_reason(changed_fields: Iterable[str]) -> str:
    changed = sorted({field for field in changed_fields})
    if not changed:
        return "Re-review required due to relevant content update"
    return "Re-review required due to changes: " + ", ".join(changed)


def apply_workflow_change(
    *,
    entity,
    target_status: WorkflowStatus,
    review_reason: str | None,
    actor: User | None,
) -> None:
    entity.workflow_status = target_status
    entity.review_reason = (review_reason or "").strip() or None
    entity.reviewed_at = utcnow()
    entity.reviewed_by_id = getattr(actor, "id", None) if actor else None
    entity.reviewed_by_name = (
        (getattr(actor, "username", None) or getattr(actor, "email", None)) if actor else None
    )
