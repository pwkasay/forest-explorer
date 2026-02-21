"""Tests for FIA ingestion — pure function tests on clean/transform logic."""

import pandas as pd
import pytest

from app.ingestion.fia_loader import (
    STATE_CODES,
    clean_cond_df,
    clean_plot_df,
    clean_tree_df,
    ingest_state,
)


def _make_plot_df() -> pd.DataFrame:
    """Minimal PLOT DataFrame matching expected CSV columns."""
    return pd.DataFrame(
        [
            {
                "CN": 1001,
                "STATECD": 37,
                "UNITCD": 1,
                "COUNTYCD": 101,
                "PLOT": 1,
                "INVYR": 2021,
                "LAT": 35.5,
                "LON": -79.0,
                "ELEV": 300,
                "ECOSUBCD": "M220A",
            },
            {
                "CN": 1002,
                "STATECD": 37,
                "UNITCD": 1,
                "COUNTYCD": 101,
                "PLOT": 2,
                "INVYR": 2021,
                "LAT": None,
                "LON": None,
                "ELEV": 250,
                "ECOSUBCD": "M220A",
            },
        ]
    )


def _make_tree_df() -> pd.DataFrame:
    """Minimal TREE DataFrame."""
    return pd.DataFrame(
        [
            {
                "CN": 2001,
                "PLT_CN": 1001,
                "CONDID": 1,
                "SUBP": 1,
                "TREE": 1,
                "STATECD": 37,
                "SPCD": 131,
                "DIA": 8.5,
                "HT": 45.0,
                "ACTUALHT": 44.0,
                "CR": 60,
                "STATUSCD": 1,
                "DRYBIO_AG": 120.0,
                "DRYBIO_BG": 30.0,
                "CARBON_AG": 60.0,
                "CARBON_BG": 15.0,
                "TPA_UNADJ": 6.018,
                "VOLCFNET": 8.5,
            }
        ]
    )


def _make_cond_df() -> pd.DataFrame:
    """Minimal COND DataFrame."""
    return pd.DataFrame(
        [
            {
                "CN": 3001,
                "PLT_CN": 1001,
                "CONDID": 1,
                "STATECD": 37,
                "FORTYPCD": 161,
                "STDAGE": 35,
                "STDSZCD": 3,
                "SITECLCD": 3,
                "SLOPE": 5,
                "ASPECT": 180,
                "OWNCD": 46,
                "OWNGRPCD": 40,
                "CONDPROP_UNADJ": 1.0,
            }
        ]
    )


def test_state_codes_has_nc() -> None:
    """NC should map to FIPS code 37."""
    assert "NC" in STATE_CODES
    assert STATE_CODES["NC"] == 37


def test_state_codes_has_se_states() -> None:
    """All SE US states should be in the mapping."""
    for state in ["NC", "SC", "GA", "VA", "AL", "FL", "TN"]:
        assert state in STATE_CODES


def test_clean_plot_df_drops_null_coords() -> None:
    """Rows with null lat/lon should be dropped."""
    df = _make_plot_df()
    cleaned = clean_plot_df(df)
    assert len(cleaned) == 1


def test_clean_plot_df_lowercases_columns() -> None:
    """All column names should be lowercase after cleaning."""
    df = _make_plot_df()
    cleaned = clean_plot_df(df)
    assert all(c == c.lower() for c in cleaned.columns)


def test_clean_tree_df_preserves_rows() -> None:
    """Valid tree rows should survive cleaning."""
    df = _make_tree_df()
    cleaned = clean_tree_df(df)
    assert len(cleaned) == 1
    assert "carbon_ag" in cleaned.columns
    assert "spcd" in cleaned.columns


def test_clean_cond_df_lowercases_columns() -> None:
    """COND column names should be lowercase after cleaning."""
    df = _make_cond_df()
    cleaned = clean_cond_df(df)
    assert all(c == c.lower() for c in cleaned.columns)
    assert "fortypcd" in cleaned.columns


def test_clean_plot_df_handles_missing_optional_columns() -> None:
    """clean_plot_df should handle DataFrames missing optional columns."""
    df = pd.DataFrame(
        [
            {
                "CN": 1001,
                "STATECD": 37,
                "INVYR": 2021,
                "LAT": 35.5,
                "LON": -79.0,
            }
        ]
    )
    cleaned = clean_plot_df(df)
    assert len(cleaned) == 1
    assert "lat" in cleaned.columns


def test_ingest_state_invalid_raises() -> None:
    """Unknown state abbreviation should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown state"):
        ingest_state("XX")
