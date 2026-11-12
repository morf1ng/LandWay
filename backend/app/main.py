from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import DB_ENABLED, init_db
from app.deps import require_user
from app.routers.api import public_router, router
from app.routers.auth import router as auth_router
from app.store import store

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Smart Caspian Transit", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(public_router, prefix="/api")
app.include_router(auth_router, prefix="/api/auth")
app.include_router(router, prefix="/api", dependencies=[Depends(require_user)])


@app.get("/")
def root():
    return {
        "name": "Smart Caspian Transit",
        "shipments": len(store.read()["shipments"]),
        "database": DB_ENABLED,
    }
