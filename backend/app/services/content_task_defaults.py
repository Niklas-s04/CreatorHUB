from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.content import ContentItem, ContentTask, ContentType, TaskStatus, TaskType

DEFAULT_TASKS: dict[ContentType, list[tuple[TaskType, str]]] = {
    ContentType.review: [
        (TaskType.script, "Script / Outline"),
        (TaskType.record, "Record"),
        (TaskType.edit, "Edit"),
        (TaskType.thumbnail, "Thumbnail"),
        (TaskType.upload, "Upload & metadata"),
        (TaskType.publish, "Publish / launch"),
    ],
    ContentType.short: [
        (TaskType.record, "Record"),
        (TaskType.edit, "Edit"),
        (TaskType.thumbnail, "Thumbnail"),
        (TaskType.upload, "Upload"),
        (TaskType.publish, "Publish"),
        (TaskType.crosspost, "Crosspost"),
    ],
    ContentType.post: [
        (TaskType.script, "Copy / Caption"),
        (TaskType.design, "Design asset"),
        (TaskType.upload, "Schedule / upload"),
        (TaskType.publish, "Publish"),
        (TaskType.crosspost, "Crosspost"),
    ],
    ContentType.story: [
        (TaskType.record, "Record clips"),
        (TaskType.edit, "Edit"),
        (TaskType.upload, "Upload"),
        (TaskType.publish, "Publish"),
    ],
}


def ensure_default_tasks_for_item(db: Session, content_item: ContentItem) -> int:
    templates = DEFAULT_TASKS.get(content_item.type)
    if not templates:
        return 0

    existing = (
        db.query(ContentTask.id).filter(ContentTask.content_item_id == content_item.id).first()
    )
    if existing:
        return 0

    for task_type, note in templates:
        db.add(
            ContentTask(
                content_item_id=content_item.id,
                type=task_type,
                title=note,
                status=TaskStatus.todo,
                notes=note,
            )
        )

    db.flush()
    return len(templates)
