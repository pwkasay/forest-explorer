# 🍄 Forest Carbon Data Explorer

**A full-stack data engineering demo ingesting USFS Forest Inventory & Analysis data through automated QA/QC pipelines, transforming it with dbt, and serving it via a Vue dashboard with interactive geospatial carbon visualizations.**

Built as a portfolio project demonstrating data engineering skills for climate tech — a data stack that bridges genomic sequencing, geospatial analysis, and carbon accounting.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Vue 3 Frontend (Vite + Leaflet + Chart.js)             │
│  Interactive map, carbon dashboards, QA/QC reports      │
├─────────────────────────────────────────────────────────┤
│  FastAPI Backend (Python 3.14)                          │
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
| Clean Python for data manipulation | Type-hinted, async Python 3.14 throughout |
| Treat internal teams as customers | Dashboard designed for non-technical Growth/Land team users |

## Tech Stack

**Backend:** Python 3.14, FastAPI, SQLAlchemy + GeoAlchemy2, asyncpg  
**Data:** dbt-core + dbt-postgres, FIA API ingestion  
**Frontend:** Vue 3 (Composition API), Vite, Leaflet, Chart.js  
**Infrastructure:** PostgreSQL 16 + PostGIS 3.4, Docker Compose, Nginx  
**Geospatial:** PostGIS, Shapely, GeoPandas, pyproj  

## Quick Start

```bash
# Clone and start everything
git clone https://github.com/pwkasay/forest-explorer.git
cd forest-explorer
cp .env.example .env

# Start the stack
docker compose up -d

# Ingest FIA data for a sample state (North Carolina)
docker compose exec backend python -m app.ingestion.fia_loader --state NC

# Run dbt transformations
docker compose exec backend dbt run --project-dir /app/dbt

# Open the dashboard
open http://localhost:3000
```

## Project Structure

```
forest-carbon-explorer/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI route handlers
│   │   ├── core/           # Config, database, dependencies
│   │   ├── models/         # SQLAlchemy + GeoAlchemy2 ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic, QA/QC engine
│   │   └── ingestion/      # FIA API data loaders
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
├── scripts/                # Dev utilities
├── docker-compose.yml
└── .claude/                # Claude Code instructions
```

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

## Data Sources

- **USFS FIA Database API** — Tree-level measurements, carbon estimates, plot locations
- **EVALIDator API** — Aggregate forest statistics by state/county
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
