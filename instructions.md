# Forest Carbon Data Explorer — Claude Code Instructions

## Context
This is a portfolio project for a Data Engineer application at Funga PBC, a climate tech startup using fungal microbiome restoration for forest carbon sequestration. The project demonstrates: FIA data ingestion, dbt transformations, geospatial QA/QC, and a Vue dashboard — mirroring Funga's actual stack (PostgreSQL/PostGIS, dbt, Python, Docker).

## Architecture Decisions
- **Python 3.14** with FastAPI (async throughout, type hints everywhere)
- **Vue 3** with Composition API (not Streamlit — shows full-stack range)
- **dbt-core** with dbt-postgres adapter (not dbt Cloud)
- **PostGIS** for all spatial data (not just plain PostgreSQL)
- **Docker Compose** for local dev; production-ready Dockerfiles
- No heavy managed platforms (no Snowflake, no Databricks) — Funga explicitly values lean, composable tools

## Code Standards
- Python: Ruff for linting, strict type hints, async where possible
- SQL (dbt): CTEs over subqueries, explicit column naming, `{{ ref() }}` always
- Vue: `<script setup>` syntax, composables for shared logic, Pinia for state
- All API responses use Pydantic models
- GeoJSON for all spatial API responses

## Key Data Flow
1. `ingestion/fia_loader.py` pulls from USFS FIADB-API → raw tables in PostgreSQL
2. dbt `staging` models clean and normalize raw data
3. dbt `marts` models aggregate into carbon-per-acre metrics by geography/species
4. FastAPI serves these marts + spatial queries to the Vue frontend
5. QA/QC validation runs as a service layer, flagging data quality issues

## Priority Order for Development
1. Get Docker Compose stack running (PostgreSQL+PostGIS, backend, frontend)
2. FIA data ingestion pipeline (start with NC loblolly pine data)
3. dbt models (staging → marts)
4. API endpoints for carbon metrics + spatial queries
5. Vue dashboard (map view, carbon charts, QA/QC panel)
6. Polish: tests, error handling, documentation

## FIA API Notes
- Base URL: `https://apps.fs.usda.gov/fiadb-api/`
- Key endpoints: `/fullreport` (EVALIDator), direct table downloads
- Bulk CSVs available at: `https://apps.fs.usda.gov/fia/datamart/CSV/`
- State-level files: `{STATE}_TREE.csv`, `{STATE}_PLOT.csv`, `{STATE}_COND.csv`
- Coordinates in PLOT table are fuzzed for privacy (~0.5-1 mile)
- Use `TPA_UNADJ` expansion factor for population estimates

## Geospatial Conventions
- All geometry stored as EPSG:4326 (WGS84) in PostGIS
- API returns GeoJSON (RFC 7946)
- Frontend uses Leaflet with OpenStreetMap tiles
- County boundaries from US Census TIGER/Line shapefiles
