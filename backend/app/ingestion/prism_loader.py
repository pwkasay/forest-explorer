"""PRISM 30-year climate normals loader.

Samples PRISM 4km raster grids at FIA plot locations to associate each plot
with mean annual temperature, precipitation, and seasonal climate metrics.
These climate-carbon joins enable analysis of how temperature and moisture
patterns correlate with forest carbon density.

Requires rasterio for raster sampling. Uses the PRISM normals BIL files
(1991-2020 period) downloaded from https://prism.oregonstate.edu/normals/.

Usage:
    python -m app.ingestion.prism_loader --state NC
"""

import argparse
import logging
import tempfile
import zipfile
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from app.core.config import settings
from app.ingestion.fia_loader import STATE_CODES

logger = logging.getLogger(__name__)

# PRISM 30-year normals (1991-2020) — annual + monthly BIL rasters
PRISM_BASE = "https://services.nacse.org/prism/data/public/normals/4km"
PRISM_VARS = {
    "tmean_annual": f"{PRISM_BASE}/tmean/14",  # annual mean temp
    "ppt_annual": f"{PRISM_BASE}/ppt/14",  # annual precip
    "tmean_jan": f"{PRISM_BASE}/tmean/1",  # January mean temp
    "tmean_jul": f"{PRISM_BASE}/tmean/7",  # July mean temp
}


def _download_prism_bil(url: str, label: str) -> Path:
    """Download a PRISM BIL zip file and extract the .bil raster."""
    tmp_dir = tempfile.mkdtemp(prefix=f"prism_{label}_")
    zip_path = Path(tmp_dir) / "prism.zip"
    logger.info(f"Downloading PRISM {label} from {url}")

    with (
        httpx.Client(timeout=httpx.Timeout(30, read=300), follow_redirects=True) as client,
        client.stream("GET", url) as resp,
    ):
        resp.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                f.write(chunk)

    # Extract all files (BIL format needs .bil, .hdr, .prj together)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(tmp_dir)
    zip_path.unlink()

    bil_files = list(Path(tmp_dir).glob("*.bil"))
    if not bil_files:
        raise FileNotFoundError(f"No .bil file found in PRISM download for {label}")
    return bil_files[0]


def _sample_raster_at_points(bil_path: Path, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Sample a PRISM BIL raster at the given lat/lon coordinates.

    Returns an array of values (NaN where coordinates fall outside the raster).
    """
    import rasterio

    with rasterio.open(bil_path) as src:
        # Convert lat/lon to raster row/col indices
        values = np.full(len(lats), np.nan)
        for i, (lon, lat) in enumerate(zip(lons, lats, strict=True)):
            try:
                row, col = src.index(float(lon), float(lat))
                if 0 <= row < src.height and 0 <= col < src.width:
                    val = src.read(1)[row, col]
                    # PRISM uses -9999 as nodata
                    if val > -9999:
                        values[i] = val
            except Exception:
                continue
    return values


def load_prism_normals(state_abbr: str) -> dict:
    """Sample PRISM climate normals at all FIA plot locations for a state.

    Downloads annual and monthly raster files, samples at each plot's lat/lon,
    computes growing season precipitation (Apr-Sep), and stores results in
    raw.prism_normals.
    """
    state_abbr = state_abbr.upper()
    if state_abbr not in STATE_CODES:
        raise ValueError(f"Unknown state: {state_abbr}")

    statecd = STATE_CODES[state_abbr]
    engine = create_engine(settings.database_url_sync)

    try:
        # Get plot coordinates for this state
        with engine.connect() as conn:
            plots = pd.read_sql(
                text(
                    "SELECT cn, lat, lon FROM raw.fia_plot "
                    "WHERE statecd = :statecd AND lat IS NOT NULL AND lon IS NOT NULL"
                ),
                conn,
                params={"statecd": statecd},
            )

        if len(plots) == 0:
            logger.warning(f"No plots found for {state_abbr} — ingest FIA data first")
            return {"state": state_abbr, "plots_sampled": 0}

        logger.info(f"Sampling PRISM normals at {len(plots)} plots for {state_abbr}")
        lats = plots["lat"].values
        lons = plots["lon"].values

        # Download and sample each variable
        raster_paths: dict[str, Path] = {}
        try:
            for label, url in PRISM_VARS.items():
                raster_paths[label] = _download_prism_bil(url, label)

            tmean_annual = _sample_raster_at_points(raster_paths["tmean_annual"], lats, lons)
            ppt_annual = _sample_raster_at_points(raster_paths["ppt_annual"], lats, lons)
            tmean_jan = _sample_raster_at_points(raster_paths["tmean_jan"], lats, lons)
            tmean_jul = _sample_raster_at_points(raster_paths["tmean_jul"], lats, lons)

            # Download growing season months (Apr=4 through Sep=9) for precip
            growing_ppt = np.zeros(len(plots))
            for month in range(4, 10):
                url = f"{PRISM_BASE}/ppt/{month}"
                bil_path = _download_prism_bil(url, f"ppt_{month:02d}")
                raster_paths[f"ppt_{month:02d}"] = bil_path
                growing_ppt += _sample_raster_at_points(bil_path, lats, lons)
        finally:
            # Clean up downloaded rasters
            for path in raster_paths.values():
                for f in path.parent.iterdir():
                    f.unlink(missing_ok=True)
                path.parent.rmdir()

        # Build results DataFrame
        # PRISM temps are in Celsius — convert to Fahrenheit for US forestry convention
        results = pd.DataFrame(
            {
                "plot_cn": plots["cn"],
                "annual_tmean_f": np.round(tmean_annual * 9 / 5 + 32, 1),
                "annual_ppt_in": np.round(ppt_annual / 25.4, 2),  # mm to inches
                "jan_tmean_f": np.round(tmean_jan * 9 / 5 + 32, 1),
                "jul_tmean_f": np.round(tmean_jul * 9 / 5 + 32, 1),
                "growing_season_ppt_in": np.round(growing_ppt / 25.4, 2),
            }
        )

        # Drop rows where all climate values are NaN (plot outside PRISM extent)
        climate_cols = [c for c in results.columns if c != "plot_cn"]
        results = results.dropna(subset=climate_cols, how="all")

        # Delete existing state data and insert
        with engine.begin() as conn:
            conn.execute(
                text("""
                    DELETE FROM raw.prism_normals
                    WHERE plot_cn IN (
                        SELECT cn FROM raw.fia_plot WHERE statecd = :statecd
                    )
                """),
                {"statecd": statecd},
            )

        results.to_sql(
            "prism_normals",
            engine,
            schema="raw",
            if_exists="append",
            index=False,
            method="multi",
            chunksize=5000,
        )
        logger.info(f"Loaded climate normals for {len(results)} plots in {state_abbr}")

    finally:
        engine.dispose()

    return {"state": state_abbr, "plots_sampled": len(results)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Sample PRISM climate normals at FIA plots")
    parser.add_argument("--state", required=True, help="State abbreviation (e.g., NC)")
    args = parser.parse_args()

    result = load_prism_normals(args.state)
    print(f"\nSampled climate normals for {result['plots_sampled']} plots in {result['state']}")
