# Forest Carbon Explorer — Backend

Python 3.13 + FastAPI + PostGIS data pipeline and API.

## Stack

- **FastAPI** with async SQLAlchemy + asyncpg
- **dbt-core** + dbt-postgres for staging → marts transformation
- **PostGIS** for geospatial queries (GeoAlchemy2, Shapely)
- **Pydantic** schemas for all API responses (RFC 7946 GeoJSON)

## API Endpoints (`/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/carbon/summary/{statecd}` | Aggregate carbon stats for a state |
| GET | `/carbon/species/{statecd}` | Top species ranked by carbon density |
| GET | `/plots/{statecd}/geojson` | Plot locations as GeoJSON FeatureCollection |
| POST | `/qa/run` | Run all QA/QC validation checks |
| POST | `/ingest/{state_abbr}` | Trigger FIA data ingestion |
| GET | `/health` | Service health check |
| GET | `/health/data` | Data pipeline health (states loaded, dbt status) |

## Local Development

```bash
pip install -e ".[dev]"
uvicorn app.main:app --reload          # API at http://localhost:8000
ruff check . && ruff format --check .  # Lint
pytest                                 # Tests (mocked, no DB required)
```

## dbt Models

```
models/
├── staging/          # 1:1 views on raw tables — cleaning, renaming, quality flags
│   ├── stg_fia_plots.sql
│   ├── stg_fia_trees.sql
│   ├── stg_fia_conditions.sql
│   ├── stg_county_boundaries.sql
│   └── stg_prism_normals.sql
└── marts/            # Materialized business-ready aggregations
    ├── mart_carbon_by_species.sql
    └── mart_plot_carbon_density.sql
```

## Testing

Tests are fully mocked — no database required to run them:

```bash
pytest --tb=short -q   # 23 tests, <1s
```
