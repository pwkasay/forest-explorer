"""Automated QA/QC validation pipeline for FIA data.

Catches inconsistencies in tabular and geospatial data before they reach
downstream dbt models — a core responsibility of a data engineering role.
Each check is a composable function that returns a QACheckResult.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.carbon import QACheckResult, QARunSummary


async def check_null_coordinates(db: AsyncSession, statecd: int | None = None) -> QACheckResult:
    """Flag plots missing lat/lon — can't build geometry without them."""
    where = "WHERE statecd = :statecd" if statecd else ""
    params = {"statecd": statecd} if statecd else {}
    result = await db.execute(
        text(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE lat IS NULL OR lon IS NULL) AS failed
            FROM raw.fia_plot
            {where}
        """),
        params,
    )
    row = result.one()
    total, failed = row.total, row.failed
    return QACheckResult(
        check_name="null_coordinates",
        table_name="raw.fia_plot",
        severity="error" if failed > 0 else "info",
        records_checked=total,
        records_failed=failed,
        failure_rate=failed / total if total > 0 else 0.0,
        details={"description": "Plots with NULL lat or lon values"},
    )


async def check_coordinate_bounds(db: AsyncSession, statecd: int | None = None) -> QACheckResult:
    """Validate that plot coordinates fall within continental US bounds."""
    where = "WHERE statecd = :statecd" if statecd else ""
    params = {"statecd": statecd} if statecd else {}
    result = await db.execute(
        text(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE lat IS NOT NULL AND lon IS NOT NULL
                    AND (lat < 24.0 OR lat > 50.0 OR lon < -125.0 OR lon > -66.0)
                ) AS failed
            FROM raw.fia_plot
            {where}
        """),
        params,
    )
    row = result.one()
    return QACheckResult(
        check_name="coordinate_bounds_conus",
        table_name="raw.fia_plot",
        severity="warning" if row.failed > 0 else "info",
        records_checked=row.total,
        records_failed=row.failed,
        failure_rate=row.failed / row.total if row.total > 0 else 0.0,
        details={
            "description": "Plots outside continental US bounding box",
            "bounds": {"lat": [24.0, 50.0], "lon": [-125.0, -66.0]},
        },
    )


async def check_negative_carbon(db: AsyncSession, statecd: int | None = None) -> QACheckResult:
    """Carbon values should never be negative — flag measurement errors."""
    join = "JOIN raw.fia_plot p ON p.cn = t.plt_cn" if statecd else ""
    where = "WHERE p.statecd = :statecd" if statecd else ""
    params = {"statecd": statecd} if statecd else {}
    result = await db.execute(
        text(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE t.carbon_ag < 0 OR t.carbon_bg < 0
                    OR t.drybio_ag < 0 OR t.drybio_bg < 0
                ) AS failed
            FROM raw.fia_tree t
            {join}
            {where}
        """),
        params,
    )
    row = result.one()
    return QACheckResult(
        check_name="negative_carbon_or_biomass",
        table_name="raw.fia_tree",
        severity="error" if row.failed > 0 else "info",
        records_checked=row.total,
        records_failed=row.failed,
        failure_rate=row.failed / row.total if row.total > 0 else 0.0,
        details={"description": "Trees with negative carbon or biomass values"},
    )


async def check_diameter_outliers(db: AsyncSession, statecd: int | None = None) -> QACheckResult:
    """Flag trees with implausible diameters (>60 inches is extremely rare)."""
    join = "JOIN raw.fia_plot p ON p.cn = t.plt_cn" if statecd else ""
    where = "WHERE p.statecd = :statecd" if statecd else ""
    params = {"statecd": statecd} if statecd else {}
    result = await db.execute(
        text(f"""
            SELECT
                COUNT(*) FILTER (WHERE t.dia IS NOT NULL) AS total,
                COUNT(*) FILTER (WHERE t.dia > 60.0) AS failed
            FROM raw.fia_tree t
            {join}
            {where}
        """),
        params,
    )
    row = result.one()
    return QACheckResult(
        check_name="diameter_outliers",
        table_name="raw.fia_tree",
        severity="warning" if row.failed > 0 else "info",
        records_checked=row.total,
        records_failed=row.failed,
        failure_rate=row.failed / row.total if row.total > 0 else 0.0,
        details={"description": "Trees with DIA > 60 inches (potential measurement error)"},
    )


async def check_orphaned_trees(db: AsyncSession, statecd: int | None = None) -> QACheckResult:
    """Trees should reference a valid plot — orphans indicate ingestion issues."""
    if statecd:
        join = "JOIN raw.fia_plot p ON p.cn = t.plt_cn"
        where = "WHERE p.statecd = :statecd"
        subquery = "SELECT cn FROM raw.fia_plot WHERE statecd = :statecd"
    else:
        join = ""
        where = ""
        subquery = "SELECT cn FROM raw.fia_plot"
    params = {"statecd": statecd} if statecd else {}
    result = await db.execute(
        text(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE t.plt_cn NOT IN ({subquery})
                ) AS failed
            FROM raw.fia_tree t
            {join}
            {where}
        """),
        params,
    )
    row = result.one()
    return QACheckResult(
        check_name="orphaned_trees",
        table_name="raw.fia_tree",
        severity="error" if row.failed > 0 else "info",
        records_checked=row.total,
        records_failed=row.failed,
        failure_rate=row.failed / row.total if row.total > 0 else 0.0,
        details={"description": "Trees referencing non-existent plot CN values"},
    )


async def check_inventory_year_range(db: AsyncSession, statecd: int | None = None) -> QACheckResult:
    """Inventory years should be within a reasonable range."""
    where = "WHERE statecd = :statecd" if statecd else ""
    params = {"statecd": statecd} if statecd else {}
    result = await db.execute(
        text(f"""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE invyr < 1968 OR invyr > 2026) AS failed,
                MIN(invyr) AS min_year,
                MAX(invyr) AS max_year
            FROM raw.fia_plot
            {where}
        """),
        params,
    )
    row = result.one()
    return QACheckResult(
        check_name="inventory_year_range",
        table_name="raw.fia_plot",
        severity="warning" if row.failed > 0 else "info",
        records_checked=row.total,
        records_failed=row.failed,
        failure_rate=row.failed / row.total if row.total > 0 else 0.0,
        details={
            "description": "Plots with inventory year outside 1968-2026",
            "min_year": row.min_year,
            "max_year": row.max_year,
        },
    )


# ── Runner ──────────────────────────────────────────────────────────────────

ALL_CHECKS = [
    check_null_coordinates,
    check_coordinate_bounds,
    check_negative_carbon,
    check_diameter_outliers,
    check_orphaned_trees,
    check_inventory_year_range,
]


async def run_all_checks(db: AsyncSession, statecd: int | None = None) -> QARunSummary:
    """Execute all QA/QC checks and return a summary."""
    run_id = str(uuid.uuid4())
    checks: list[QACheckResult] = []

    for check_fn in ALL_CHECKS:
        result = await check_fn(db, statecd=statecd)
        checks.append(result)

    errors = sum(1 for c in checks if c.severity == "error" and c.records_failed > 0)
    warnings = sum(1 for c in checks if c.severity == "warning" and c.records_failed > 0)

    return QARunSummary(
        run_id=run_id,
        timestamp=datetime.now(UTC),
        total_checks=len(checks),
        errors=errors,
        warnings=warnings,
        checks=checks,
    )
