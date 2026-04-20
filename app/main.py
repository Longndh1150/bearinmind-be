import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.api.router import api_router
from app.core.logging_config import setup_logging
from app.db.session import engine

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    logger.info(f"Starting Bear In Mind API v{__version__}")
    yield
    logger.info("Shutting down Bear In Mind API...")
    await engine.dispose()


app = FastAPI(
    title="Bear In Mind API",
    version=__version__,
    lifespan=lifespan,
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error on {request.method} {request.url}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."},
    )

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def liveness():
    return {"status": "ok"}
