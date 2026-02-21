"""Live data integrity audit for the Forest Carbon Explorer API.

Hits every endpoint on the running stack and reports whether each returns
real data, empty data, fallback data, or errors.

Usage:
    python scripts/audit_endpoints.py [--base-url http://localhost:8002] [--state 37]
"""

from __future__ import annotations

import argparse
import sys

import httpx

# The 17 species codes from the hardcoded fallback dict in carbon.py.
# If species results ONLY contain these, the seed table isn't being used.
_FALLBACK_SPCD = {
    110,
    121,
    129,
    131,
    132,
    261,
    316,
    318,
    531,
    541,
    621,
    693,
    746,
    802,
    833,
    837,
    951,
}

PASS = "\033[92m[PASS]\033[0m"
WARN = "\033[93m[WARN]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"


def check_health(client: httpx.Client, base: str) -> bool:
    """Check basic API health."""
    try:
        r = client.get(f"{base}/health")
        if r.status_code == 200:
            print(f"  {PASS} /health                       status=ok")
            return True
    except Exception:
        pass
    # FastAPI may not have a /health — try docs endpoint
    try:
        r = client.get(f"{base.rsplit('/api/v1', 1)[0]}/docs")
        if r.status_code == 200:
            print(f"  {PASS} /docs                         FastAPI docs reachable")
            return True
    except Exception:
        pass
    print(f"  {FAIL} /health                       API not reachable")
    return False


def check_summary(client: httpx.Client, base: str, state: int) -> bool:
    """Check carbon summary endpoint."""
    r = client.get(f"{base}/carbon/summary/{state}")
    if r.status_code != 200:
        print(f"  {FAIL} /carbon/summary/{state}          HTTP {r.status_code}")
        return False
    data = r.json()
    plots = data.get("total_plots", 0)
    trees = data.get("total_trees", 0)
    available = data.get("data_available", True)
    if not available or plots == 0:
        print(
            f"  {FAIL} /carbon/summary/{state}          No data (plots=0, data_available={available})"
        )
        return False
    carbon = data.get("avg_carbon_per_acre_tons", 0)
    print(
        f"  {PASS} /carbon/summary/{state}          plots={plots:,}  trees={trees:,}  carbon={carbon:.4f} t/ac"
    )
    return True


def check_species(client: httpx.Client, base: str, state: int) -> bool:
    """Check species endpoint and detect hardcoded fallback usage."""
    r = client.get(f"{base}/carbon/species/{state}?limit=15")
    if r.status_code != 200:
        print(f"  {FAIL} /carbon/species/{state}          HTTP {r.status_code}")
        return False
    data = r.json()
    if not data:
        print(f"  {FAIL} /carbon/species/{state}          Empty response")
        return False
    # Check if all returned species codes are in the fallback set
    returned_spcd = {s["spcd"] for s in data}
    names_with_code = [s for s in data if s["species_name"].startswith("SPCD ")]
    if names_with_code:
        print(
            f"  {WARN} /carbon/species/{state}          "
            f"{len(names_with_code)} species using code fallback (seed table incomplete)"
        )
        return True
    # If all species are in the fallback set, likely using hardcoded names
    if returned_spcd.issubset(_FALLBACK_SPCD) and len(data) > 5:
        print(
            f"  {WARN} /carbon/species/{state}          "
            f"{len(data)} species — all from fallback set (dbt seed may not be loaded)"
        )
        return True
    print(
        f"  {PASS} /carbon/species/{state}          {len(data)} species from seed table"
    )
    return True


def check_plots(client: httpx.Client, base: str, state: int) -> bool:
    """Check GeoJSON plots endpoint."""
    r = client.get(f"{base}/plots/{state}/geojson?limit=100")
    if r.status_code != 200:
        print(f"  {FAIL} /plots/{state}/geojson           HTTP {r.status_code}")
        return False
    data = r.json()
    features = data.get("features", [])
    if not features:
        print(f"  {FAIL} /plots/{state}/geojson           No features returned")
        return False
    # Validate coordinate ranges
    bad_coords = 0
    for f in features:
        coords = f.get("geometry", {}).get("coordinates", [])
        if len(coords) >= 2:
            lon, lat = coords[0], coords[1]
            if not (24.0 <= lat <= 50.0 and -125.0 <= lon <= -66.0):
                bad_coords += 1
    suffix = ""
    if bad_coords:
        suffix = f"  ({bad_coords} out-of-bounds coords)"
    print(
        f"  {PASS} /plots/{state}/geojson           {len(features)} features, coords valid{suffix}"
    )
    return True


def check_counties(client: httpx.Client, base: str, state: int) -> bool:
    """Check county boundaries endpoint."""
    r = client.get(f"{base}/counties/{state}/geojson")
    if r.status_code == 404:
        detail = r.json().get("detail", "not loaded")
        print(f"  {WARN} /counties/{state}/geojson        {detail}")
        return True
    if r.status_code != 200:
        print(f"  {FAIL} /counties/{state}/geojson        HTTP {r.status_code}")
        return False
    data = r.json()
    features = data.get("features", [])
    if not features:
        print(
            f"  {WARN} /counties/{state}/geojson        Empty FeatureCollection for this state"
        )
        return True
    print(f"  {PASS} /counties/{state}/geojson        {len(features)} counties")
    return True


def check_climate(client: httpx.Client, base: str, state: int) -> bool:
    """Check climate data endpoint."""
    r = client.get(f"{base}/climate/{state}")
    if r.status_code == 404:
        detail = r.json().get("detail", "not loaded")
        print(f"  {WARN} /climate/{state}                 {detail}")
        return True
    if r.status_code != 200:
        print(f"  {FAIL} /climate/{state}                 HTTP {r.status_code}")
        return False
    data = r.json()
    if not data:
        print(f"  {WARN} /climate/{state}                 Empty response")
        return True
    null_climate = sum(1 for row in data if row.get("annual_tmean_f") is None)
    if null_climate > 0:
        print(
            f"  {WARN} /climate/{state}                 {null_climate}/{len(data)} rows with NULL climate columns"
        )
        return True
    print(
        f"  {PASS} /climate/{state}                 {len(data)} records with climate data"
    )
    return True


def check_qa(client: httpx.Client, base: str, state: int) -> bool:
    """Check QA engine endpoint."""
    r = client.post(f"{base}/qa/run?statecd={state}")
    if r.status_code != 200:
        print(f"  {FAIL} /qa/run                       HTTP {r.status_code}")
        return False
    data = r.json()
    total = data.get("total_checks", 0)
    errors = data.get("errors", 0)
    warnings = data.get("warnings", 0)
    if total == 0:
        print(f"  {FAIL} /qa/run                       No checks executed")
        return False
    empty_checks = sum(
        1 for c in data.get("checks", []) if c.get("records_checked", 0) == 0
    )
    status = PASS if errors == 0 else FAIL
    suffix = ""
    if empty_checks:
        suffix = f"  ({empty_checks} checks had 0 records)"
    print(
        f"  {status} /qa/run                       {total} checks, {errors} errors, {warnings} warnings{suffix}"
    )
    return errors == 0


def check_data_health(client: httpx.Client, base: str) -> bool:
    """Check the data health endpoint."""
    r = client.get(f"{base}/health/data")
    if r.status_code != 200:
        print(f"  {FAIL} /health/data                  HTTP {r.status_code}")
        return False
    data = r.json()
    overall = data.get("overall_status", "unknown")
    states = data.get("states_with_data", [])
    seed = data.get("dbt_seed_loaded", False)
    dbt = data.get("dbt_models_built", False)

    parts = [f"status={overall}"]
    if states:
        parts.append(f"states={states}")
    if not seed:
        parts.append("seed NOT loaded")
    if not dbt:
        parts.append("dbt models NOT built")

    status = PASS if overall == "healthy" else WARN if overall == "degraded" else FAIL
    print(f"  {status} /health/data                  {', '.join(parts)}")
    return overall != "empty"


def main() -> None:
    parser = argparse.ArgumentParser(description="Forest Carbon Data Integrity Audit")
    parser.add_argument(
        "--base-url", default="http://localhost:8002", help="API base URL"
    )
    parser.add_argument(
        "--state", type=int, default=37, help="State FIPS code (default: 37=NC)"
    )
    args = parser.parse_args()

    base = f"{args.base_url.rstrip('/')}/api/v1"

    print(f"\n{'=' * 55}")
    print("  Forest Carbon Data Integrity Audit")
    print(f"  State: FIPS {args.state} | Base URL: {args.base_url}")
    print(f"{'=' * 55}\n")

    has_failure = False
    with httpx.Client(timeout=30.0) as client:
        if not check_health(client, base):
            print("\n  API not reachable — aborting audit.\n")
            sys.exit(1)

        checks = [
            check_data_health(client, base),
            check_summary(client, base, args.state),
            check_species(client, base, args.state),
            check_plots(client, base, args.state),
            check_counties(client, base, args.state),
            check_climate(client, base, args.state),
            check_qa(client, base, args.state),
        ]
        has_failure = not all(checks)

    print(f"\n{'=' * 55}")
    if has_failure:
        print("  Result: ISSUES FOUND (see FAIL items above)")
    else:
        print("  Result: ALL CHECKS PASSED")
    print(f"{'=' * 55}\n")

    sys.exit(1 if has_failure else 0)


if __name__ == "__main__":
    main()
