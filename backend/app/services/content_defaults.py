from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from app.models.content import (
    ChecklistPhase,
    ContentChecklistTemplate,
    ContentChecklistTemplateItem,
    ContentPlatform,
    ContentPlatformProfile,
    ContentType,
    TaskPriority,
)

SYSTEM_PLATFORM_PROFILES: list[dict[str, Any]] = [
    {
        "platform": ContentPlatform.youtube,
        "name": "YouTube default",
        "schema_json": {
            "required_base_fields": [
                "title",
                "publish_date",
                "description_md",
                "tags_csv",
            ],
            "fields": [
                {
                    "key": "category",
                    "label": "Category",
                    "type": "select",
                    "required": True,
                    "options": ["Review", "Tutorial", "Unboxing", "Vlog", "Short"],
                },
                {
                    "key": "visibility",
                    "label": "Visibility",
                    "type": "select",
                    "required": True,
                    "options": ["private", "unlisted", "public"],
                },
                {
                    "key": "thumbnail_note",
                    "label": "Thumbnail note",
                    "type": "textarea",
                    "required": False,
                },
            ],
        },
    },
    {
        "platform": ContentPlatform.instagram,
        "name": "Instagram default",
        "schema_json": {
            "required_base_fields": [
                "title",
                "publish_date",
                "description_md",
                "tags_csv",
            ],
            "fields": [
                {
                    "key": "format",
                    "label": "Format",
                    "type": "select",
                    "required": True,
                    "options": ["Reel", "Story", "Carousel", "Post"],
                },
                {
                    "key": "collab_handle",
                    "label": "Collab handle",
                    "type": "text",
                    "required": False,
                },
                {
                    "key": "audio",
                    "label": "Audio",
                    "type": "text",
                    "required": False,
                },
            ],
        },
    },
    {
        "platform": ContentPlatform.tiktok,
        "name": "TikTok default",
        "schema_json": {
            "required_base_fields": [
                "title",
                "publish_date",
                "description_md",
                "tags_csv",
            ],
            "fields": [
                {
                    "key": "sound",
                    "label": "Sound",
                    "type": "text",
                    "required": False,
                },
                {
                    "key": "privacy",
                    "label": "Privacy",
                    "type": "select",
                    "required": True,
                    "options": ["private", "friends", "public"],
                },
                {
                    "key": "cta",
                    "label": "Call to action",
                    "type": "text",
                    "required": False,
                },
            ],
        },
    },
]


SYSTEM_CHECKLIST_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "YouTube Review",
        "description": "Long-form review workflow from outline to launch.",
        "applies_to_platform": ContentPlatform.youtube,
        "applies_to_type": ContentType.review,
        "items": [
            ("Research product angles", ChecklistPhase.pre_production, True, "high", -7, True),
            ("Write outline and hook", ChecklistPhase.pre_production, True, "high", -5, True),
            ("Record main footage", ChecklistPhase.production, True, "high", -3, True),
            ("Edit video and audio", ChecklistPhase.post_production, True, "high", -2, True),
            ("Create thumbnail", ChecklistPhase.post_production, True, "medium", -1, True),
            ("Upload metadata and schedule", ChecklistPhase.upload, True, "medium", 0, True),
        ],
    },
    {
        "name": "Short/Reel/TikTok",
        "description": "Short-form clip workflow for vertical platforms.",
        "applies_to_platform": None,
        "applies_to_type": ContentType.short,
        "items": [
            ("Define hook and CTA", ChecklistPhase.pre_production, True, "high", -3, True),
            ("Record vertical clips", ChecklistPhase.production, True, "high", -2, True),
            ("Edit captions and pacing", ChecklistPhase.post_production, True, "high", -1, True),
            ("Add hashtags and sound", ChecklistPhase.upload, True, "medium", 0, True),
            ("Crosspost where relevant", ChecklistPhase.upload, False, "medium", 0, False),
        ],
    },
    {
        "name": "Unboxing Video",
        "description": "Unboxing workflow from package prep to upload.",
        "applies_to_platform": ContentPlatform.youtube,
        "applies_to_type": ContentType.review,
        "items": [
            ("Prepare product and set", ChecklistPhase.pre_production, True, "medium", -5, True),
            ("Record package opening", ChecklistPhase.production, True, "high", -4, True),
            (
                "Record closeups and first impressions",
                ChecklistPhase.production,
                True,
                "high",
                -3,
                True,
            ),
            ("Cut story flow", ChecklistPhase.post_production, True, "high", -2, True),
            ("Add title, tags and description", ChecklistPhase.upload, True, "medium", -1, True),
            ("Final publish check", ChecklistPhase.upload, True, "medium", 0, True),
        ],
    },
]


def ensure_content_defaults(db: Session) -> None:
    _ensure_platform_profiles(db, SYSTEM_PLATFORM_PROFILES)
    _ensure_checklist_templates(db, SYSTEM_CHECKLIST_TEMPLATES)


def _ensure_platform_profiles(db: Session, profiles: Iterable[dict[str, Any]]) -> None:
    for definition in profiles:
        profile = (
            db.query(ContentPlatformProfile)
            .filter(
                ContentPlatformProfile.platform == definition["platform"],
                ContentPlatformProfile.name == definition["name"],
                ContentPlatformProfile.is_system.is_(True),
            )
            .first()
        )
        if profile is None:
            db.add(
                ContentPlatformProfile(
                    platform=definition["platform"],
                    name=definition["name"],
                    schema_json=definition["schema_json"],
                    is_active=True,
                    is_system=True,
                    owner_user_id=None,
                )
            )
            continue

        if profile.schema_json != definition["schema_json"] or not profile.is_active:
            profile.schema_json = definition["schema_json"]
            profile.is_active = True
            profile.version += 1


def _ensure_checklist_templates(db: Session, templates: Iterable[dict[str, Any]]) -> None:
    for definition in templates:
        template = (
            db.query(ContentChecklistTemplate)
            .filter(
                ContentChecklistTemplate.name == definition["name"],
                ContentChecklistTemplate.is_system.is_(True),
            )
            .first()
        )
        if template is None:
            template = ContentChecklistTemplate(
                name=definition["name"],
                description=definition["description"],
                applies_to_platform=definition["applies_to_platform"],
                applies_to_type=definition["applies_to_type"],
                is_shared=True,
                is_system=True,
                owner_user_id=None,
            )
            db.add(template)
            db.flush()
        else:
            changed = False
            for key in ("description", "applies_to_platform", "applies_to_type"):
                if getattr(template, key) != definition[key]:
                    setattr(template, key, definition[key])
                    changed = True
            if not template.is_shared:
                template.is_shared = True
                changed = True
            if changed:
                template.version += 1
            db.query(ContentChecklistTemplateItem).filter(
                ContentChecklistTemplateItem.template_id == template.id
            ).delete()

        for index, item in enumerate(definition["items"]):
            title, phase, required, priority, due_offset_days, can_block_publish = item
            db.add(
                ContentChecklistTemplateItem(
                    template_id=template.id,
                    title=title,
                    phase=phase,
                    required=required,
                    priority_default=TaskPriority(priority),
                    due_offset_days=due_offset_days,
                    can_block_publish=can_block_publish,
                    sort_order=index,
                )
            )
