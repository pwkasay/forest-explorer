"""Pydantic schemas for API responses — GeoJSON-native for spatial data."""

from datetime import datetime

from pydantic import BaseModel, Field

# ── Carbon metrics ──────────────────────────────────────────────────────────


class CarbonBySpecies(BaseModel):
    """Carbon density aggregated by tree species."""

    spcd: int
    species_name: str
    plot_count: int
    avg_carbon_ag_per_acre: float = Field(description="Mean above-ground carbon (lbs/acre)")
    avg_carbon_bg_per_acre: float = Field(description="Mean below-ground carbon (lbs/acre)")
    avg_carbon_total_per_acre: float = Field(description="Mean total carbon (lbs/acre)")
    avg_dia: float = Field(description="Mean diameter at breast height (inches)")


class CarbonByCounty(BaseModel):
    """Carbon summary by county with GeoJSON-compatible coordinates."""

    statecd: int
    countycd: int
    county_fips: str
    plot_count: int
    total_carbon_ag_tons: float
    total_carbon_bg_tons: float
    avg_carbon_per_acre_tons: float
    dominant_forest_type: str | None = None


class CarbonSummary(BaseModel):
    """High-level carbon statistics for a state or region."""

    statecd: int
    total_plots: int
    total_trees: int
    total_carbon_ag_tons: float
    total_carbon_bg_tons: float
    avg_carbon_per_acre_tons: float
    species_count: int
    most_recent_inventory: int
    loblolly_pine_pct: float = Field(
        description="Percentage of trees that are loblolly pine (SPCD 131)"
    )
    data_available: bool = Field(
        default=True,
        description="False when no FIA data exists for this state",
    )


# ── GeoJSON ─────────────────────────────────────────────────────────────────


class PlotProperties(BaseModel):
    """Properties embedded in a GeoJSON Feature for a plot."""

    cn: int
    statecd: int
    countycd: int | None
    invyr: int
    elev: int | None
    carbon_ag_total: float | None = Field(description="Sum of CARBON_AG across trees (lbs)")
    carbon_bg_total: float | None
    tree_count: int | None
    dominant_species: str | None
    stand_age: int | None


class GeoJSONFeature(BaseModel):
    """A single GeoJSON Feature."""

    type: str = "Feature"
    geometry: dict
    properties: PlotProperties


class PlotFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection of FIA plots."""

    type: str = "FeatureCollection"
    features: list[GeoJSONFeature]


# ── QA/QC ───────────────────────────────────────────────────────────────────


class QACheckResult(BaseModel):
    """Result of a single QA/QC validation check."""

    check_name: str
    table_name: str
    severity: str  # error, warning, info
    records_checked: int
    records_failed: int
    failure_rate: float
    details: dict | None = None


class QARunSummary(BaseModel):
    """Summary of a full QA/QC validation run."""

    run_id: str
    timestamp: datetime
    total_checks: int
    errors: int
    warnings: int
    checks: list[QACheckResult]


# ── Data Health ─────────────────────────────────────────────────────────────


class TableHealth(BaseModel):
    """Health status of a single database table."""

    table_name: str
    row_count: int
    status: str = Field(description="populated, empty, or missing")
    required: bool = True


class DataHealthReport(BaseModel):
    """Overall data pipeline health report."""

    overall_status: str = Field(description="healthy, degraded, or empty")
    tables: list[TableHealth]
    dbt_seed_loaded: bool
    dbt_models_built: bool
    states_with_data: list[int]
    checked_at: datetime


# ── Ingestion ───────────────────────────────────────────────────────────────


class IngestionStatus(BaseModel):
    """Status response for data ingestion jobs."""

    state: str
    table: str
    rows_ingested: int
    duration_seconds: float
    status: str  # running, completed, failed
    message: str | None = None
