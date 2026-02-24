# 🍄 Forest Carbon Data Explorer

**A full-stack data engineering demo ingesting USFS Forest Inventory & Analysis data through automated QA/QC pipelines, transforming it with dbt, and serving it via a Vue dashboard with interactive geospatial carbon visualizations.**

Built as a portfolio project demonstrating data engineering skills for climate tech — a data stack that bridges genomic sequencing, geospatial analysis, and carbon accounting.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Vue 3 Frontend (Vite + Leaflet + Chart.js)             │
│  Interactive map, carbon dashboards, QA/QC reports      │
├─────────────────────────────────────────────────────────┤
│  FastAPI Backend (Python 3.13)                          │
│  REST API, data ingestion, validation pipelines         │
├─────────────────────────────────────────────────────────┤
│  dbt Transformation Layer                               │
│  staging → marts: clean, versioned, documented models   │
├─────────────────────────────────────────────────────────┤
│  PostgreSQL + PostGIS                                   │
│  Spatial queries, forest plot data, carbon estimates     │
└─────────────────────────────────────────────────────────┘
```

## What This Demonstrates

| Requirement | How This Project Shows It |
|---|---|
| SQL + dbt transformation layers | dbt models transforming raw FIA data into carbon-ready marts |
| Internal data apps (Streamlit or similar) | Vue dashboard with carbon metrics, maps, QA/QC visibility |
| Geospatial workflows (vector/raster QA/QC) | PostGIS spatial queries, boundary validation, Leaflet maps |
| Automated QA/QC pipelines | Validation framework catching data inconsistencies pre-delivery |
| Containerized connectors pulling from APIs | Dockerized FIA API ingestion pipeline |
| Cloud-native deployment (Docker, AWS/GCP) | Docker Compose stack, production-ready Dockerfile |
| Clean Python for data manipulation | Type-hinted, async Python 3.13 throughout |
| Treat internal teams as customers | Dashboard designed for non-technical Growth/Land team users |

## Tech Stack

**Backend:** Python 3.13, FastAPI, SQLAlchemy + GeoAlchemy2, asyncpg
**Data:** dbt-core + dbt-postgres, FIA API ingestion  
**Frontend:** Vue 3 (Composition API), Vite, Leaflet, Chart.js  
**Infrastructure:** PostgreSQL 16 + PostGIS 3.4, Docker Compose
**Geospatial:** PostGIS, Shapely, GeoPandas, pyproj

## Quick Start

```bash
# Clone and start everything
git clone https://github.com/pwkasay/forest-explorer.git
cd forest-explorer
cp .env.example .env
docker compose up -d

# Ingest FIA data for North Carolina (~5-15 min, downloads ~150MB from USFS)
docker compose exec backend python -m app.ingestion.fia_loader --state NC

# Load species reference and build dbt models
docker compose exec backend dbt seed --project-dir /app/dbt --profiles-dir /app/dbt
docker compose exec backend dbt run  --project-dir /app/dbt --profiles-dir /app/dbt
docker compose exec backend dbt test --project-dir /app/dbt --profiles-dir /app/dbt

# Open the dashboard
open http://localhost:3001          # Dashboard
# API docs at http://localhost:8002/docs
```

Or use the **Makefile** shortcuts:

```bash
make setup                          # docker compose up -d
make ingest                         # Ingest NC data (STATE=NC by default)
make ingest STATE=SC                # Ingest a different state
make dbt-seed                       # Load species reference CSV (run before dbt)
make dbt                            # Build staging views + mart tables (requires dbt-seed)
make dbt-test                       # Run 28 data quality tests
make test                           # Run backend unit tests (23 tests)
make lint                           # Ruff lint + format check
```

### Optional: County Boundaries & Climate Data

The core dashboard works with just FIA data, but two additional ingestion pipelines unlock county-level and climate endpoints:

```bash
make ingest-counties               # Census TIGER county polygons (~30s)
make ingest-climate                # PRISM 30-year climate normals (~3 min)
make dbt                           # Rebuild models with new data
```

These are **optional** — skip them to get up and running faster, or run them later to enable the `/api/v1/counties/` and `/api/v1/climate/` API endpoints.

### Data ingestion options

The ingestion pipeline supports all 50 US states. Each state downloads three CSV files (PLOT, TREE, COND) from the USFS FIA DataMart:

```bash
# Ingest a single state
docker compose exec backend python -m app.ingestion.fia_loader --state GA

# Ingest specific tables only (useful for debugging)
docker compose exec backend python -m app.ingestion.fia_loader --state NC --tables PLOT,TREE
```

State codes are standard two-letter abbreviations (NC, SC, GA, VA, FL, etc.). FIPS codes used in the API: NC=37, SC=45, GA=13.

## Project Structure

```
forest-explorer/
├── .github/workflows/      # CI pipeline (lint + test on PRs)
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI route handlers
│   │   ├── core/           # Config, database, dependencies
│   │   ├── models/         # SQLAlchemy + GeoAlchemy2 ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic, QA/QC engine
│   │   └── ingestion/      # FIA, TIGER, and PRISM data loaders
│   ├── dbt/
│   │   ├── models/
│   │   │   ├── staging/    # 1:1 with raw tables, light cleaning
│   │   │   └── marts/      # Business-ready aggregations
│   │   ├── seeds/          # Reference data (species codes, etc.)
│   │   └── macros/         # Reusable SQL snippets
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── components/     # Reusable Vue components
│   │   ├── views/          # Page-level views
│   │   ├── composables/    # Vue composition functions
│   │   └── stores/         # Pinia state management
│   └── public/
├── docker/                 # Dockerfiles
├── scripts/                # Audit & dev utilities
└── docker-compose.yml
```

## API Endpoints

Interactive docs at `http://localhost:8002/docs`.

| Method | Path | Description | Requires |
|--------|------|-------------|----------|
| GET | `/api/v1/carbon/summary/{statecd}` | Aggregate carbon stats | FIA data |
| GET | `/api/v1/carbon/species/{statecd}` | Top species by carbon density | FIA data |
| GET | `/api/v1/plots/{statecd}/geojson` | Plot locations as GeoJSON | FIA data |
| GET | `/api/v1/counties/{statecd}/geojson` | County boundary polygons | TIGER data (optional) |
| GET | `/api/v1/climate/{statecd}` | Plot-level climate metrics | PRISM data (optional) |
| POST | `/api/v1/qa/run` | Run QA/QC validation checks | FIA data |
| GET | `/api/v1/health/data` | Pipeline health status | — |
| POST | `/api/v1/ingest/{state_abbr}` | Trigger FIA ingestion | — |

State codes in paths are FIPS codes: NC=37, SC=45, GA=13.

## Dashboard Pages

- **Dashboard** (`/`) — KPI cards + species carbon chart
- **Map** (`/map`) — Leaflet map with plot clusters, carbon filters, species filter
- **QA/QC** (`/qa`) — Data validation results with severity badges

## Development

```bash
# Backend only (requires local PostgreSQL+PostGIS)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Frontend only
cd frontend
npm install
npm run dev

# Run dbt
cd backend/dbt
dbt run && dbt test
```

## CI & Verification

GitHub Actions runs linting (`ruff`) and tests (`pytest`, `npm run build`) on every push and PR to `main`.

To verify the full pipeline locally after ingestion:

```bash
python scripts/audit_endpoints.py              # Hits every API endpoint, reports PASS/WARN/FAIL
python scripts/audit_endpoints.py --state 45   # Audit a specific state (FIPS code)
```

## Data Sources

- **USFS FIA Database API** — Tree-level measurements, carbon estimates, plot locations
- **Census TIGER/Line** — County boundary polygons (optional, enables `/api/v1/counties/` endpoint)
- **PRISM Climate Normals** — 30-year temperature/precipitation normals at 4km resolution (optional, enables `/api/v1/climate/` endpoint)
- **FIA Species Reference** — Tree species codes and common names (dbt seed)

## Key Concepts

This project works with **Forest Inventory & Analysis (FIA)** data from the USDA Forest Service — the same ground-truth dataset that underpins US forest carbon accounting. Key fields:

- `CARBON_AG` / `CARBON_BG` — Above/belowground carbon per tree (lbs)
- `DRYBIO_AG` / `DRYBIO_BG` — Dry biomass estimates
- `DIA` — Diameter at breast height (inches)
- `SPCD` — Species code (e.g., 131 = loblolly pine)
- `TPA_UNADJ` — Trees-per-acre expansion factor
- `FORTYPCD` — Forest type code
- `STDAGE` — Stand age (years)
- **Coordinate fuzzing** — Public FIA plot coordinates are displaced ~0.5–1 mile by USFS for privacy; carbon estimates remain precise but mapped locations are approximate

The dbt models transform these raw measurements into carbon-per-acre estimates by species, forest type, and geography

## License

MIT
