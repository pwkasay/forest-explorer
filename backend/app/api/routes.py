"""API routes for forest carbon data, spatial queries, and QA/QC."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.carbon import (
    CarbonBySpecies,
    CarbonSummary,
    DataHealthReport,
    IngestionStatus,
    PlotFeatureCollection,
    QARunSummary,
    TableHealth,
)
from app.services import carbon, qa_engine

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Carbon Metrics ──────────────────────────────────────────────────────────


@router.get("/carbon/summary/{statecd}", response_model=CarbonSummary)
async def carbon_summary(statecd: int, db: AsyncSession = Depends(get_db)) -> CarbonSummary:
    """Get aggregate carbon statistics for a state.

    State codes follow FIPS: NC=37, SC=45, GA=13, VA=51, AL=1, etc.
    """
    return await carbon.get_carbon_summary(db, statecd)


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


# ── County Boundaries ──────────────────────────────────────────────────────


@router.get("/counties/{statecd}/geojson")
async def county_boundaries(
    statecd: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return county boundaries as a GeoJSON FeatureCollection for a state.

    Uses Census TIGER/Line polygons loaded by the tiger_loader ingestion pipeline.
    """
    total = await db.execute(text("SELECT COUNT(*) FROM raw.county_boundaries"))
    if total.scalar() == 0:
        raise HTTPException(
            status_code=404,
            detail="County boundary data not loaded. Run tiger_loader to ingest TIGER data.",
        )

    result = await db.execute(
        text("""
            SELECT
                geoid,
                name,
                statecd,
                countycd,
                aland,
                awater,
                ST_AsGeoJSON(geom)::json AS geometry
            FROM raw.county_boundaries
            WHERE statecd = :statecd
            ORDER BY name
        """),
        {"statecd": statecd},
    )
    rows = result.all()
    features = [
        {
            "type": "Feature",
            "geometry": r.geometry,
            "properties": {
                "geoid": r.geoid,
                "name": r.name,
                "statecd": r.statecd,
                "countycd": r.countycd,
                "aland_sqm": r.aland,
                "awater_sqm": r.awater,
            },
        }
        for r in rows
    ]
    return {"type": "FeatureCollection", "features": features}


# ── Climate Data ───────────────────────────────────────────────────────────


@router.get("/climate/{statecd}")
async def climate_data(
    statecd: int,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return PRISM climate normals joined to plot-level carbon metrics.

    Enables correlation analysis between temperature/precipitation patterns
    and forest carbon density.
    """
    total = await db.execute(text("SELECT COUNT(*) FROM raw.prism_normals"))
    if total.scalar() == 0:
        raise HTTPException(
            status_code=404,
            detail="PRISM climate data not loaded. Run prism_loader to ingest climate normals.",
        )

    result = await db.execute(
        text("""
            SELECT
                p.cn AS plot_cn,
                p.lat,
                p.lon,
                p.invyr,
                c.annual_tmean_f,
                c.annual_ppt_in,
                c.jan_tmean_f,
                c.jul_tmean_f,
                c.growing_season_ppt_in,
                COALESCE(SUM(t.carbon_ag * t.tpa_unadj) / 2000.0, 0) AS carbon_ag_tons,
                COUNT(t.cn) AS tree_count
            FROM raw.fia_plot p
            JOIN raw.prism_normals c ON c.plot_cn = p.cn
            LEFT JOIN raw.fia_tree t ON t.plt_cn = p.cn AND t.statuscd = 1
            WHERE p.statecd = :statecd
            GROUP BY p.cn, p.lat, p.lon, p.invyr,
                     c.annual_tmean_f, c.annual_ppt_in,
                     c.jan_tmean_f, c.jul_tmean_f, c.growing_season_ppt_in
            ORDER BY carbon_ag_tons DESC
            LIMIT 1000
        """),
        {"statecd": statecd},
    )
    return [dict(r._mapping) for r in result.all()]


# ── QA/QC ───────────────────────────────────────────────────────────────────


@router.post("/qa/run", response_model=QARunSummary)
async def run_qa_checks(
    statecd: int | None = Query(default=None, description="Filter by state FIPS code"),
    db: AsyncSession = Depends(get_db),
) -> QARunSummary:
    """Execute all QA/QC validation checks on ingested data.

    Returns a summary with per-check results, severity levels, and failure rates.
    This mimics automated validation pipelines,
    catching inconsistencies before data reaches downstream dbt models.

    Optionally filter by state FIPS code (e.g., NC=37, SC=45).
    """
    return await qa_engine.run_all_checks(db, statecd=statecd)


# ── Data Health ────────────────────────────────────────────────────────────


_HEALTH_TABLES = [
    ("raw", "fia_plot", True),
    ("raw", "fia_tree", True),
    ("raw", "fia_cond", True),
    ("public", "species_ref", True),
    ("raw", "county_boundaries", False),
    ("raw", "prism_normals", False),
]


@router.get("/health/data", response_model=DataHealthReport)
async def data_health(db: AsyncSession = Depends(get_db)) -> DataHealthReport:
    """Report data pipeline health: table row counts, dbt status, loaded states."""
    tables: list[TableHealth] = []

    for schema, table, required in _HEALTH_TABLES:
        try:
            result = await db.execute(
                text(f"SELECT COUNT(*) FROM {schema}.{table}")  # noqa: S608
            )
            count = result.scalar() or 0
            tables.append(
                TableHealth(
                    table_name=f"{schema}.{table}",
                    row_count=count,
                    status="populated" if count > 0 else "empty",
                    required=required,
                )
            )
        except Exception:
            await db.rollback()
            tables.append(
                TableHealth(
                    table_name=f"{schema}.{table}",
                    row_count=0,
                    status="missing",
                    required=required,
                )
            )

    # Check if dbt staging views exist (use information_schema to avoid
    # aborting the transaction if the view doesn't exist)
    result = await db.execute(
        text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'staging' AND table_name = 'stg_fia_plots'
            )
        """)
    )
    dbt_models_built = result.scalar() or False

    dbt_seed_loaded = any(
        t.table_name == "public.species_ref" and t.status == "populated" for t in tables
    )

    # Which states have data
    try:
        result = await db.execute(
            text("SELECT DISTINCT statecd FROM raw.fia_plot ORDER BY statecd")
        )
        states_with_data = [r[0] for r in result.all()]
    except Exception:
        await db.rollback()
        states_with_data = []

    # Determine overall status
    required_populated = all(t.status == "populated" for t in tables if t.required)
    any_data = any(t.status == "populated" for t in tables)

    if required_populated and dbt_seed_loaded:
        overall = "healthy"
    elif any_data:
        overall = "degraded"
    else:
        overall = "empty"

    return DataHealthReport(
        overall_status=overall,
        tables=tables,
        dbt_seed_loaded=dbt_seed_loaded,
        dbt_models_built=dbt_models_built,
        states_with_data=states_with_data,
        checked_at=datetime.now(UTC),
    )


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
