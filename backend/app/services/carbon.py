"""Carbon metrics service — queries PostGIS for spatial carbon data.

These queries serve the dashboard and mirror the kind of aggregations
a Funga Data Engineer would build for Growth and Land team visibility.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.carbon import (
    CarbonBySpecies,
    CarbonSummary,
    GeoJSONFeature,
    PlotFeatureCollection,
    PlotProperties,
)


async def get_carbon_summary(db: AsyncSession, statecd: int) -> CarbonSummary:
    """Aggregate carbon statistics for a state."""
    result = await db.execute(
        text("""
            SELECT
                p.statecd,
                COUNT(DISTINCT p.cn) AS total_plots,
                COUNT(t.cn) AS total_trees,
                COALESCE(SUM(t.carbon_ag * t.tpa_unadj) / 2000.0, 0) AS total_carbon_ag_tons,
                COALESCE(SUM(t.carbon_bg * t.tpa_unadj) / 2000.0, 0) AS total_carbon_bg_tons,
                COALESCE(
                    AVG(t.carbon_ag + COALESCE(t.carbon_bg, 0)) * AVG(t.tpa_unadj) / 2000.0, 0
                ) AS avg_carbon_per_acre_tons,
                COUNT(DISTINCT t.spcd) AS species_count,
                MAX(p.invyr) AS most_recent_inventory,
                COALESCE(
                    100.0 * COUNT(*) FILTER (WHERE t.spcd = 131) / NULLIF(COUNT(*), 0), 0
                ) AS loblolly_pine_pct
            FROM raw.fia_plot p
            JOIN raw.fia_tree t ON t.plt_cn = p.cn
            WHERE p.statecd = :statecd
              AND t.statuscd = 1  -- live trees only
            GROUP BY p.statecd
        """),
        {"statecd": statecd},
    )
    row = result.one_or_none()
    if row is None:
        return CarbonSummary(
            statecd=statecd,
            total_plots=0,
            total_trees=0,
            total_carbon_ag_tons=0.0,
            total_carbon_bg_tons=0.0,
            avg_carbon_per_acre_tons=0.0,
            species_count=0,
            most_recent_inventory=0,
            loblolly_pine_pct=0.0,
        )
    return CarbonSummary(
        statecd=row.statecd,
        total_plots=row.total_plots,
        total_trees=row.total_trees,
        total_carbon_ag_tons=round(row.total_carbon_ag_tons, 2),
        total_carbon_bg_tons=round(row.total_carbon_bg_tons, 2),
        avg_carbon_per_acre_tons=round(row.avg_carbon_per_acre_tons, 4),
        species_count=row.species_count,
        most_recent_inventory=row.most_recent_inventory or 0,
        loblolly_pine_pct=round(row.loblolly_pine_pct, 1),
    )


async def get_carbon_by_species(
    db: AsyncSession, statecd: int, limit: int = 20
) -> list[CarbonBySpecies]:
    """Top species by carbon density for a state."""
    result = await db.execute(
        text("""
            WITH species_agg AS (
                SELECT
                    t.spcd,
                    COUNT(DISTINCT p.cn) AS plot_count,
                    AVG(t.carbon_ag * t.tpa_unadj) AS avg_carbon_ag_per_acre,
                    AVG(COALESCE(t.carbon_bg, 0) * t.tpa_unadj) AS avg_carbon_bg_per_acre,
                    AVG((t.carbon_ag + COALESCE(t.carbon_bg, 0)) * t.tpa_unadj)
                        AS avg_carbon_total_per_acre,
                    AVG(t.dia) AS avg_dia
                FROM raw.fia_tree t
                JOIN raw.fia_plot p ON p.cn = t.plt_cn
                WHERE p.statecd = :statecd
                  AND t.statuscd = 1
                  AND t.carbon_ag IS NOT NULL
                  AND t.tpa_unadj IS NOT NULL
                GROUP BY t.spcd
                HAVING COUNT(DISTINCT p.cn) >= 5
            )
            SELECT * FROM species_agg
            ORDER BY avg_carbon_total_per_acre DESC
            LIMIT :limit
        """),
        {"statecd": statecd, "limit": limit},
    )
    rows = result.all()

    # Species code → name mapping loaded from dbt seed (fallback to code)
    species_names = await _get_species_names(db)

    return [
        CarbonBySpecies(
            spcd=r.spcd,
            species_name=species_names.get(r.spcd, f"SPCD {r.spcd}"),
            plot_count=r.plot_count,
            avg_carbon_ag_per_acre=round(r.avg_carbon_ag_per_acre, 2),
            avg_carbon_bg_per_acre=round(r.avg_carbon_bg_per_acre, 2),
            avg_carbon_total_per_acre=round(r.avg_carbon_total_per_acre, 2),
            avg_dia=round(r.avg_dia, 1),
        )
        for r in rows
    ]


async def get_plots_geojson(
    db: AsyncSession,
    statecd: int,
    min_carbon: float | None = None,
    species_filter: int | None = None,
    limit: int = 500,
) -> PlotFeatureCollection:
    """Return FIA plots as a GeoJSON FeatureCollection with carbon summaries."""
    filters = ["p.statecd = :statecd", "p.geom IS NOT NULL"]
    params: dict = {"statecd": statecd, "limit": limit}

    if min_carbon is not None:
        filters.append("pc.carbon_ag_total >= :min_carbon")
        params["min_carbon"] = min_carbon

    if species_filter is not None:
        filters.append("pc.dominant_spcd = :species_filter")
        params["species_filter"] = species_filter

    where_clause = " AND ".join(filters)

    result = await db.execute(
        text(f"""
            WITH plot_carbon AS (
                SELECT
                    plt_cn,
                    SUM(carbon_ag * tpa_unadj) AS carbon_ag_total,
                    SUM(COALESCE(carbon_bg, 0) * tpa_unadj) AS carbon_bg_total,
                    COUNT(*) AS tree_count,
                    MODE() WITHIN GROUP (ORDER BY spcd) AS dominant_spcd
                FROM raw.fia_tree
                WHERE statuscd = 1
                GROUP BY plt_cn
            )
            SELECT
                p.cn, p.statecd, p.countycd, p.invyr, p.elev,
                ST_X(p.geom) AS lon, ST_Y(p.geom) AS lat,
                pc.carbon_ag_total, pc.carbon_bg_total, pc.tree_count,
                pc.dominant_spcd,
                c.stdage
            FROM raw.fia_plot p
            LEFT JOIN plot_carbon pc ON pc.plt_cn = p.cn
            LEFT JOIN raw.fia_cond c ON c.plt_cn = p.cn AND c.condid = 1
            WHERE {where_clause}
            ORDER BY pc.carbon_ag_total DESC NULLS LAST
            LIMIT :limit
        """),
        params,
    )
    rows = result.all()
    species_names = await _get_species_names(db)

    features = [
        GeoJSONFeature(
            geometry={"type": "Point", "coordinates": [r.lon, r.lat]},
            properties=PlotProperties(
                cn=r.cn,
                statecd=r.statecd,
                countycd=r.countycd,
                invyr=r.invyr,
                elev=r.elev,
                carbon_ag_total=round(r.carbon_ag_total, 2) if r.carbon_ag_total else None,
                carbon_bg_total=round(r.carbon_bg_total, 2) if r.carbon_bg_total else None,
                tree_count=r.tree_count,
                dominant_species=species_names.get(r.dominant_spcd) if r.dominant_spcd else None,
                stand_age=r.stdage,
            ),
        )
        for r in rows
    ]

    return PlotFeatureCollection(features=features)


async def _get_species_names(db: AsyncSession) -> dict[int, str]:
    """Load species code → common name mapping."""
    try:
        result = await db.execute(text("SELECT spcd, common_name FROM staging.stg_species_ref"))
        return {r.spcd: r.common_name for r in result.all()}
    except Exception:
        # Seed table may not exist yet — return common SE US species
        return {
            131: "loblolly pine",
            132: "longleaf pine",
            110: "shortleaf pine",
            129: "eastern white pine",
            261: "eastern hemlock",
            316: "red maple",
            318: "sugar maple",
            531: "American beech",
            541: "white ash",
            621: "sweetgum",
            693: "black cherry",
            746: "quaking aspen",
            802: "white oak",
            833: "northern red oak",
            837: "scarlet oak",
            951: "American elm",
        }
