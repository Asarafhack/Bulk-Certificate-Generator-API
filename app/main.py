from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import initialize_database
from .schemas import HealthResponse
from .api.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Bulk Certificate Generator API",
    description="Create, track, and retrieve certificates generated from bulk recipient requests.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["Health"], summary="Check API health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


app.include_router(router)
