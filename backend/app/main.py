"""Forest Carbon Data Explorer — FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=(
        "REST API for forest carbon data from the USFS Forest Inventory & Analysis program. "
        "Serves spatial carbon metrics, species-level aggregations, and QA/QC validation results "
        "to an interactive Vue dashboard."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "forest-carbon-explorer"}
