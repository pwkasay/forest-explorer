"""Census TIGER/Line county boundary loader.

Downloads the national county shapefile from the US Census Bureau's TIGER/Line
program and loads boundaries for a target state into PostGIS. County polygons
enable choropleth maps of carbon density by county on the frontend.

Usage:
    python -m app.ingestion.tiger_loader --state NC
"""

import argparse
import logging
import tempfile
from pathlib import Path

import geopandas as gpd
import httpx
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.ingestion.fia_loader import STATE_CODES

logger = logging.getLogger(__name__)

TIGER_URL = "https://www2.census.gov/geo/tiger/TIGER2023/COUNTY/tl_2023_us_county.zip"


def download_shapefile(url: str) -> Path:
    """Download a zipped shapefile to a temp directory and return the path."""
    tmp_dir = tempfile.mkdtemp(prefix="tiger_")
    zip_path = Path(tmp_dir) / "county.zip"
    logger.info(f"Downloading TIGER county shapefile from {url}")

    with (
        httpx.Client(timeout=httpx.Timeout(30, read=300), follow_redirects=True) as client,
        client.stream("GET", url) as resp,
    ):
        resp.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)

    logger.info(f"Downloaded {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
    return zip_path


def load_county_boundaries(state_abbr: str) -> dict:
    """Download TIGER county boundaries and load them into PostGIS for one state.

    Returns a summary dict with row count and state info.
    """
    state_abbr = state_abbr.upper()
    if state_abbr not in STATE_CODES:
        raise ValueError(f"Unknown state: {state_abbr}")

    statecd = STATE_CODES[state_abbr]
    statefp = str(statecd).zfill(2)

    zip_path = download_shapefile(TIGER_URL)
    try:
        gdf = gpd.read_file(f"zip://{zip_path}")
    finally:
        zip_path.unlink(missing_ok=True)

    # Filter to target state
    gdf = gdf[gdf["STATEFP"] == statefp].copy()
    logger.info(f"Found {len(gdf)} counties for {state_abbr} (STATEFP={statefp})")

    if len(gdf) == 0:
        return {"state": state_abbr, "counties_loaded": 0}

    # Prepare for PostGIS
    gdf = gdf.rename(
        columns={
            "GEOID": "geoid",
            "NAME": "name",
            "ALAND": "aland",
            "AWATER": "awater",
        }
    )
    gdf["statecd"] = int(statefp)
    gdf["countycd"] = gdf["COUNTYFP"].astype(int)
    gdf = gdf[["geoid", "name", "statecd", "countycd", "aland", "awater", "geometry"]]

    # Ensure EPSG:4326 (TIGER is NAD83 which is practically identical, but be explicit)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    engine = create_engine(settings.database_url_sync)
    try:
        # Delete existing state data
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM raw.county_boundaries WHERE statecd = :statecd"),
                {"statecd": statecd},
            )
            logger.info(f"Deleted existing county boundaries for statecd={statecd}")

        # Load via geopandas
        gdf.to_postgis(
            "county_boundaries",
            engine,
            schema="raw",
            if_exists="append",
            index=False,
        )
        logger.info(f"Loaded {len(gdf)} county boundaries for {state_abbr}")
    finally:
        engine.dispose()

    return {"state": state_abbr, "counties_loaded": len(gdf)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Ingest Census TIGER county boundaries")
    parser.add_argument("--state", required=True, help="State abbreviation (e.g., NC)")
    args = parser.parse_args()

    result = load_county_boundaries(args.state)
    print(f"\nLoaded {result['counties_loaded']} counties for {result['state']}")
