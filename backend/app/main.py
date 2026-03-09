"""FastAPI application: CORS, lifespan, static mounts, routers."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ORIGINS, GENERATED_DIR, UPLOAD_DIR, setup_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing()
    yield


app = FastAPI(
    title="Agent Factory v4",
    description="AI-powered social media content creation platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file mounts
app.mount("/generated", StaticFiles(directory=str(GENERATED_DIR)), name="generated")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# API routers
from app.api.v1.router import api_router  # noqa: E402

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "agent-factory-v4"}
