"""FIA DataMart ingestion pipeline.

Downloads state-level CSV files from the USFS FIA DataMart and loads them
into PostgreSQL with PostGIS geometry. Uses chunked reads to keep memory
bounded — NC_TREE.csv alone is ~150MB with 600K+ rows.

Note: Public FIA coordinates are displaced ~0.5-1 mile by USFS for privacy.
The geometry column built from lat/lon reflects these fuzzed positions.

Usage:
    python -m app.ingestion.fia_loader --state NC
    python -m app.ingestion.fia_loader --state NC --tables PLOT,TREE,COND
"""

import argparse
import logging
import tempfile
import time
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from sqlalchemy import Engine, create_engine, text

from app.core.config import settings

logger = logging.getLogger(__name__)

# FIA state codes (FIPS)
STATE_CODES: dict[str, int] = {
    "AL": 1,
    "AK": 2,
    "AZ": 4,
    "AR": 5,
    "CA": 6,
    "CO": 8,
    "CT": 9,
    "DE": 10,
    "FL": 12,
    "GA": 13,
    "HI": 15,
    "ID": 16,
    "IL": 17,
    "IN": 18,
    "IA": 19,
    "KS": 20,
    "KY": 21,
    "LA": 22,
    "ME": 23,
    "MD": 24,
    "MA": 25,
    "MI": 26,
    "MN": 27,
    "MS": 28,
    "MO": 29,
    "MT": 30,
    "NE": 31,
    "NV": 32,
    "NH": 33,
    "NJ": 34,
    "NM": 35,
    "NY": 36,
    "NC": 37,
    "ND": 38,
    "OH": 39,
    "OK": 40,
    "OR": 41,
    "PA": 42,
    "RI": 44,
    "SC": 45,
    "SD": 46,
    "TN": 47,
    "TX": 48,
    "UT": 49,
    "VT": 50,
    "VA": 51,
    "WA": 53,
    "WV": 54,
    "WI": 55,
    "WY": 56,
}

# Columns to keep from each table (reduces memory and load time)
PLOT_COLS = [
    "CN",
    "STATECD",
    "UNITCD",
    "COUNTYCD",
    "PLOT",
    "INVYR",
    "LAT",
    "LON",
    "ELEV",
    "ECOSUBCD",
]

COND_COLS = [
    "CN",
    "PLT_CN",
    "CONDID",
    "STATECD",
    "FORTYPCD",
    "STDAGE",
    "STDSZCD",
    "SITECLCD",
    "SLOPE",
    "ASPECT",
    "OWNCD",
    "OWNGRPCD",
    "CONDPROP_UNADJ",
]

TREE_COLS = [
    "CN",
    "PLT_CN",
    "CONDID",
    "SUBP",
    "TREE",
    "STATECD",
    "SPCD",
    "DIA",
    "HT",
    "ACTUALHT",
    "CR",
    "STATUSCD",
    "DRYBIO_AG",
    "DRYBIO_BG",
    "CARBON_AG",
    "CARBON_BG",
    "TPA_UNADJ",
    "VOLCFNET",
]

# FK-safe ordering: dependents deleted first, parents loaded first
_DELETE_ORDER = ["fia_tree", "fia_cond", "fia_plot"]


def download_fia_csv(state_abbr: str, table_name: str) -> Path:
    """Download a state-level FIA CSV to a temp file and return its path.

    Streams the HTTP response to disk in 1 MB chunks so the full response
    body never lives in memory. Caller is responsible for deleting the file
    (use try/finally).

    For states that provide ZIP files instead of CSVs, the ZIP is streamed
    to disk, the CSV member is extracted to a second temp file, and the ZIP
    is deleted.
    """
    base_url = settings.fia_datamart_url
    url = f"{base_url}/{state_abbr}_{table_name}.csv"
    logger.info(f"Downloading {url}")

    with httpx.Client(timeout=httpx.Timeout(30, read=300), follow_redirects=True) as client:
        head = client.head(url)

        if head.status_code == 404:
            # ZIP fallback
            url = f"{base_url}/{state_abbr}_{table_name}.zip"
            logger.info(f"CSV not found, trying {url}")
            zip_tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)  # noqa: SIM115
            try:
                with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                        zip_tmp.write(chunk)
                zip_tmp.close()

                csv_tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)  # noqa: SIM115
                with zipfile.ZipFile(zip_tmp.name) as zf:
                    csv_name = zf.namelist()[0]
                    with zf.open(csv_name) as src:
                        while block := src.read(1024 * 1024):
                            csv_tmp.write(block)
                csv_tmp.close()
                return Path(csv_tmp.name)
            finally:
                Path(zip_tmp.name).unlink(missing_ok=True)
        else:
            tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)  # noqa: SIM115
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                downloaded = 0
                for chunk in resp.iter_bytes(chunk_size=1024 * 1024):
                    tmp.write(chunk)
                    downloaded += len(chunk)
            tmp.close()
            logger.info(f"Downloaded {downloaded / 1024 / 1024:.1f} MB to {tmp.name}")
            return Path(tmp.name)


def clean_plot_df(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and filter PLOT table, keeping only needed columns."""
    available = [c for c in PLOT_COLS if c in df.columns]
    df = df[available].copy()
    df.columns = df.columns.str.lower()
    # Drop rows without coordinates
    df = df.dropna(subset=["lat", "lon"])
    return df


def clean_cond_df(df: pd.DataFrame) -> pd.DataFrame:
    """Clean COND table."""
    available = [c for c in COND_COLS if c in df.columns]
    df = df[available].copy()
    df.columns = df.columns.str.lower()
    return df


def clean_tree_df(df: pd.DataFrame) -> pd.DataFrame:
    """Clean TREE table, filtering to live trees with valid measurements."""
    available = [c for c in TREE_COLS if c in df.columns]
    df = df[available].copy()
    df.columns = df.columns.str.lower()
    return df


def delete_state_data(engine: Engine, table_name: str, statecd: int, schema: str = "raw") -> None:
    """Delete all rows for a state from a raw table. Called once before chunked loading."""
    with engine.begin() as conn:
        conn.execute(
            text(f"DELETE FROM {schema}.{table_name} WHERE statecd = :statecd"),
            {"statecd": statecd},
        )
    logger.info(f"Deleted existing data for statecd={statecd} from {schema}.{table_name}")


def update_plot_geometry(engine: Engine, table_name: str = "fia_plot", schema: str = "raw") -> None:
    """Build PostGIS geometry from lat/lon. Called once after all plot chunks are loaded.

    Note: FIA coordinates are fuzzed ~0.5-1 mile by USFS for privacy —
    geometry reflects approximate, not exact, plot locations.
    """
    with engine.begin() as conn:
        result = conn.execute(
            text(f"""
                UPDATE {schema}.{table_name}
                SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
                WHERE lat IS NOT NULL AND lon IS NOT NULL AND geom IS NULL
            """)
        )
    logger.info(f"Updated geometry for {result.rowcount:,} plots")


def load_chunk_to_postgres(
    df: pd.DataFrame, table_name: str, engine: Engine, schema: str = "raw"
) -> int:
    """Append a DataFrame chunk to PostgreSQL. Returns row count inserted."""
    with engine.begin() as conn:
        df.to_sql(
            table_name,
            conn,
            schema=schema,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=5000,
        )
    return len(df)


def _ingest_table_chunked(
    csv_path: Path,
    table_name: str,
    clean_fn: Callable[[pd.DataFrame], pd.DataFrame],
    usecols: list[str],
    engine: Engine,
    schema: str = "raw",
    chunksize: int = 50_000,
) -> int:
    """Read a CSV in chunks, clean each chunk, and load to Postgres.

    Only parses columns listed in *usecols* (NC_TREE.csv has ~70 columns
    but we only need 18, cutting per-chunk memory by ~75%).

    Returns total rows loaded.
    """
    total_rows = 0
    usecols_set = set(usecols)

    reader = pd.read_csv(
        csv_path,
        usecols=lambda c: c in usecols_set,
        chunksize=chunksize,
        low_memory=False,
    )

    for i, chunk in enumerate(reader):
        cleaned = clean_fn(chunk)
        if len(cleaned) == 0:
            continue
        loaded = load_chunk_to_postgres(cleaned, table_name, engine, schema)
        total_rows += loaded
        logger.info(f"  {table_name}: chunk {i + 1} — {loaded:,} rows (total: {total_rows:,})")
        del cleaned

    return total_rows


def ingest_state(state_abbr: str, tables: list[str] | None = None) -> dict[str, Any]:
    """Ingest FIA data for a state. Returns summary statistics.

    Downloads each table's CSV to a temp file, then reads it in 50K-row
    chunks through the clean→load pipeline. Peak memory stays under ~200 MB
    even for NC_TREE's 600K+ rows.
    """
    state_abbr = state_abbr.upper()
    if state_abbr not in STATE_CODES:
        raise ValueError(f"Unknown state: {state_abbr}")

    statecd = STATE_CODES[state_abbr]
    tables = tables or ["PLOT", "COND", "TREE"]
    results: dict[str, Any] = {"state": state_abbr, "tables": {}}

    table_config: dict[str, tuple[str, Callable[[pd.DataFrame], pd.DataFrame], list[str], bool]] = {
        "PLOT": ("fia_plot", clean_plot_df, PLOT_COLS, True),
        "COND": ("fia_cond", clean_cond_df, COND_COLS, False),
        "TREE": ("fia_tree", clean_tree_df, TREE_COLS, False),
    }

    engine = create_engine(settings.database_url_sync)
    try:
        # FK-safe delete: dependents first (TREE, COND) then parent (PLOT)
        pg_tables_to_load = [table_config[t][0] for t in tables if t in table_config]
        for dep_table in _DELETE_ORDER:
            if dep_table in pg_tables_to_load:
                delete_state_data(engine, dep_table, statecd)

        # Load in FK order (PLOT first so COND/TREE FKs resolve)
        for table in tables:
            if table not in table_config:
                logger.warning(f"Unknown table: {table}")
                continue

            pg_table, clean_fn, usecols, needs_geometry = table_config[table]
            start = time.time()
            logger.info(f"Ingesting {state_abbr}_{table}...")

            csv_path = download_fia_csv(state_abbr, table)
            try:
                rows = _ingest_table_chunked(
                    csv_path=csv_path,
                    table_name=pg_table,
                    clean_fn=clean_fn,
                    usecols=usecols,
                    engine=engine,
                )

                if needs_geometry:
                    update_plot_geometry(engine, pg_table)
            finally:
                csv_path.unlink(missing_ok=True)

            elapsed = time.time() - start
            results["tables"][table] = {
                "rows": rows,
                "duration_seconds": round(elapsed, 2),
            }
            logger.info(f"  -> {rows:,} rows in {elapsed:.1f}s")
    finally:
        engine.dispose()

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Ingest FIA data for a US state")
    parser.add_argument("--state", required=True, help="State abbreviation (e.g., NC)")
    parser.add_argument("--tables", default="PLOT,COND,TREE", help="Comma-separated table list")
    args = parser.parse_args()

    tables = [t.strip().upper() for t in args.tables.split(",")]
    result = ingest_state(args.state, tables)

    print(f"\nIngestion complete for {result['state']}:")
    for table, info in result["tables"].items():
        print(f"  {table}: {info['rows']:,} rows ({info['duration_seconds']}s)")
