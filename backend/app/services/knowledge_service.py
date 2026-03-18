from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeDoc, KnowledgeDocType


def get_knowledge_bundle(db: Session) -> dict[str, str]:
    """Return concatenated brand_voice, policy, templates."""
    docs = db.query(KnowledgeDoc).all()
    parts = {"brand_voice": [], "policy": [], "template": []}
    for d in docs:
        if d.type == KnowledgeDocType.brand_voice:
            parts["brand_voice"].append(f"# {d.title}\n{d.content}")
        elif d.type == KnowledgeDocType.policy:
            parts["policy"].append(f"# {d.title}\n{d.content}")
        elif d.type == KnowledgeDocType.template:
            parts["template"].append(f"# {d.title}\n{d.content}")
    return {
        "brand_voice": "\n\n".join(parts["brand_voice"]).strip(),
        "policy": "\n\n".join(parts["policy"]).strip(),
        "templates": "\n\n".join(parts["template"]).strip(),
    }
