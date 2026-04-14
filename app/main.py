from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.router import api_router
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Bear In Mind API",
    version=__version__,
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def liveness():
    return {"status": "ok"}
