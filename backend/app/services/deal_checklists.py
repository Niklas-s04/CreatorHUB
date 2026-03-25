from __future__ import annotations

from copy import deepcopy

from app.models.deal import DealDraftStatus

_BASE: list[dict[str, str | bool]] = [
    {
        "key": "brand_verified",
        "label": "Brand/Ansprechpartner verifiziert",
        "required": True,
        "done": False,
    },
    {"key": "budget_clarified", "label": "Budget geklärt", "required": True, "done": False},
    {
        "key": "deliverables_defined",
        "label": "Deliverables definiert",
        "required": True,
        "done": False,
    },
    {
        "key": "usage_rights_defined",
        "label": "Nutzungsrechte geklärt",
        "required": True,
        "done": False,
    },
]

_NEGOTIATING: list[dict[str, str | bool]] = [
    {"key": "timeline_agreed", "label": "Timeline abgestimmt", "required": True, "done": False},
    {
        "key": "approval_flow_defined",
        "label": "Freigabeflow vereinbart",
        "required": True,
        "done": False,
    },
]

_WON: list[dict[str, str | bool]] = [
    {
        "key": "contract_archived",
        "label": "Vertrags-/Briefingstand archiviert",
        "required": True,
        "done": False,
    },
    {
        "key": "handover_to_content",
        "label": "Übergabe an Content geplant",
        "required": True,
        "done": False,
    },
]


def default_checklist_for_status(status: DealDraftStatus) -> list[dict[str, str | bool]]:
    items = deepcopy(_BASE)
    if status in {DealDraftStatus.negotiating, DealDraftStatus.won}:
        items.extend(deepcopy(_NEGOTIATING))
    if status == DealDraftStatus.won:
        items.extend(deepcopy(_WON))
    return items


def merge_checklist(
    *,
    current: list[dict[str, str | bool]] | None,
    status: DealDraftStatus,
    override: list[dict[str, str | bool]] | None,
) -> list[dict[str, str | bool]]:
    base = default_checklist_for_status(status)
    by_key = {str(item.get("key")): item for item in base}

    for source in current or []:
        key = str(source.get("key") or "")
        if not key or key not in by_key:
            continue
        by_key[key]["done"] = bool(source.get("done"))

    for source in override or []:
        key = str(source.get("key") or "")
        if not key:
            continue
        target = by_key.get(key)
        if target is None:
            by_key[key] = {
                "key": key,
                "label": str(source.get("label") or key),
                "required": bool(source.get("required", False)),
                "done": bool(source.get("done", False)),
            }
            continue
        target["done"] = bool(source.get("done"))

    return list(by_key.values())


def missing_required_items(checklist: list[dict[str, str | bool]] | None) -> list[str]:
    if not checklist:
        return []
    missing: list[str] = []
    for item in checklist:
        if bool(item.get("required")) and not bool(item.get("done")):
            missing.append(str(item.get("key") or "unknown"))
    return missing
