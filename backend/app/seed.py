from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import engine, SessionLocal
from app.models.base import Base
from app.models.user import User, UserRole
from app.models.knowledge import KnowledgeDoc, KnowledgeDocType


DEFAULT_BRAND_VOICE = """- Ton: freundlich, direkt, professionell, keine Übertreibungen
- Länge: 6–12 Sätze Standard
- Emojis: selten/nie
- Anrede: „Hi <Name>,“ oder „Hallo <Name>,“ je nach Kontext
- Closing: „Viele Grüße,“
- Do: klare Fragen, next steps, kurze Bulletpoints
- Don’t: Zusagen ohne Bestätigung, keine privaten Daten
""".strip()

DEFAULT_POLICY = """- Keine Bankdaten, Adresse, Telefonnummer ausgeben oder wiederholen.
- Keine rechtsverbindlichen Zusagen („verbindlich“, „garantiere“) ohne manuelle Freigabe.
- Bei unklaren Details: max. 3 konkrete Rückfragen.
- Bei dubiosen Mails: höfliche Ablehnung + keine Links klicken + um offizielle Kontaktwege bitten.
""".strip()


def bootstrap_if_needed() -> None:
    import os
    if os.getenv("SKIP_BOOTSTRAP", "false").lower() in ("true", "1", "yes"):
        print("SKIP_BOOTSTRAP is set - skipping bootstrap")
        return

    # Tabellen für lokale Starts anlegen; produktiv über Alembic migrieren.
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        # Standard-Admin nur einmal anlegen.
        admin = db.query(User).filter(User.username == settings.BOOTSTRAP_ADMIN_USERNAME).first()
        if not admin:
            db.add(User(
                username=settings.BOOTSTRAP_ADMIN_USERNAME,
                hashed_password=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
                role=UserRole.admin,
                is_active=True,
            ))
            db.commit()

        # Standard-Wissensdokumente nur anlegen, wenn sie fehlen.
        has_brand = db.query(KnowledgeDoc).filter(KnowledgeDoc.type == KnowledgeDocType.brand_voice).first()
        if not has_brand:
            db.add(KnowledgeDoc(type=KnowledgeDocType.brand_voice, title="Default Brand Voice", content=DEFAULT_BRAND_VOICE))
        has_policy = db.query(KnowledgeDoc).filter(KnowledgeDoc.type == KnowledgeDocType.policy).first()
        if not has_policy:
            db.add(KnowledgeDoc(type=KnowledgeDocType.policy, title="Default Policy", content=DEFAULT_POLICY))
        db.commit()
    finally:
        db.close()
