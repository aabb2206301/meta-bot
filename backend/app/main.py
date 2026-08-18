"""
FastAPI entrypoint. All channel and dashboard routers registered as of
Phase 6.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.app_env}


from .channels.whatsapp import router as whatsapp_router
from .channels.instagram import router as instagram_router
from .channels.facebook import router as facebook_router
from .api.dashboard_routes import router as dashboard_router
from .api.websocket import router as websocket_router

app.include_router(whatsapp_router)
app.include_router(instagram_router)
app.include_router(facebook_router)
app.include_router(dashboard_router)
app.include_router(websocket_router)