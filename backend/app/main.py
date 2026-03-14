from __future__ import annotations

import asyncio
from contextlib import suppress

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routers import auth, products, assets, content, email, images, knowledge, health, deals, audit
from app.seed import bootstrap_if_needed
from app.services.auto_archive import auto_archive_daemon


def create_app() -> FastAPI:
    app = FastAPI(title=settings.PROJECT_NAME, version="1.0.0")

    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(products.router, prefix="/api/products", tags=["products"])
    app.include_router(assets.router, prefix="/api/assets", tags=["assets"])
    app.include_router(content.router, prefix="/api/content", tags=["content"])
    app.include_router(email.router, prefix="/api/email", tags=["email"])
    app.include_router(images.router, prefix="/api/images", tags=["images"])
    app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
    app.include_router(deals.router, prefix="/api/deals", tags=["deals"])
    app.include_router(audit.router, prefix="/api/audit", tags=["audit"])

    @app.on_event("startup")
    def _startup() -> None:
        bootstrap_if_needed()
        app.state.auto_archive_task = None
        if settings.AUTO_ARCHIVE_ENABLED:
            loop = asyncio.get_event_loop()
            app.state.auto_archive_task = loop.create_task(auto_archive_daemon())

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        task = getattr(app.state, "auto_archive_task", None)
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
