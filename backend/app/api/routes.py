"""API routes for forest carbon data, spatial queries, and QA/QC."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.carbon import (
    CarbonBySpecies,
    CarbonSummary,
    IngestionStatus,
    PlotFeatureCollection,
    QARunSummary,
)
from app.services import carbon, qa_engine

router = APIRouter()


# ── Carbon Metrics ──────────────────────────────────────────────────────────


@router.get("/carbon/summary/{statecd}", response_model=CarbonSummary)
async def carbon_summary(statecd: int, db: AsyncSession = Depends(get_db)) -> CarbonSummary:
    """Get aggregate carbon statistics for a state.

    State codes follow FIPS: NC=37, SC=45, GA=13, VA=51, AL=1, etc.
    """
    try:
        return await carbon.get_carbon_summary(db, statecd)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/carbon/species/{statecd}", response_model=list[CarbonBySpecies])
async def carbon_by_species(
    statecd: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[CarbonBySpecies]:
    """Top species by carbon density for a state."""
    return await carbon.get_carbon_by_species(db, statecd, limit=limit)


# ── Geospatial ──────────────────────────────────────────────────────────────


@router.get("/plots/{statecd}/geojson", response_model=PlotFeatureCollection)
async def plots_geojson(
    statecd: int,
    min_carbon: float | None = Query(default=None, description="Min carbon_ag (lbs)"),
    species: int | None = Query(default=None, description="Filter by species code (e.g., 131)"),
    limit: int = Query(default=500, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
) -> PlotFeatureCollection:
    """Return FIA plots as GeoJSON with carbon summaries.

    Useful for mapping carbon density across a state. Each feature includes
    total carbon, tree count, dominant species, and stand age.
    """
    return await carbon.get_plots_geojson(
        db, statecd, min_carbon=min_carbon, species_filter=species, limit=limit
    )


# ── QA/QC ───────────────────────────────────────────────────────────────────


@router.post("/qa/run", response_model=QARunSummary)
async def run_qa_checks(db: AsyncSession = Depends(get_db)) -> QARunSummary:
    """Execute all QA/QC validation checks on ingested data.

    Returns a summary with per-check results, severity levels, and failure rates.
    This mimics the automated validation pipelines described in the Funga JD:
    catching inconsistencies before data reaches downstream dbt models.
    """
    return await qa_engine.run_all_checks(db)


# ── Ingestion (async trigger) ──────────────────────────────────────────────


@router.post("/ingest/{state_abbr}", response_model=IngestionStatus)
async def trigger_ingestion(state_abbr: str) -> IngestionStatus:
    """Trigger FIA data ingestion for a state.

    In production this would be an async task (Celery/SQS). For the demo,
    it runs synchronously to keep the stack simple.
    """
    import time

    from app.ingestion.fia_loader import ingest_state

    start = time.time()
    try:
        result = ingest_state(state_abbr)
        total_rows = sum(t["rows"] for t in result["tables"].values())
        elapsed = time.time() - start
        return IngestionStatus(
            state=state_abbr.upper(),
            table="ALL",
            rows_ingested=total_rows,
            duration_seconds=round(elapsed, 2),
            status="completed",
            message=f"Ingested {total_rows:,} rows across {len(result['tables'])} tables",
        )
    except Exception as e:
        elapsed = time.time() - start
        return IngestionStatus(
            state=state_abbr.upper(),
            table="ALL",
            rows_ingested=0,
            duration_seconds=round(elapsed, 2),
            status="failed",
            message=str(e),
        )
