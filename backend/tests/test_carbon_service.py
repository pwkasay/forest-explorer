"""Tests for the carbon metrics service — mocked DB."""

from unittest.mock import AsyncMock

from app.schemas.carbon import CarbonSummary, PlotFeatureCollection
from app.services import carbon
from tests.conftest import mock_result_all, mock_result_none, mock_result_one, mock_row


async def test_get_carbon_summary(mock_db: AsyncMock) -> None:
    """get_carbon_summary should return a valid CarbonSummary from mock data."""
    mock_db.execute.return_value = mock_result_one(
        mock_row(
            statecd=37,
            total_plots=1500,
            total_trees=45000,
            total_carbon_ag_tons=125000.0,
            total_carbon_bg_tons=32000.0,
            avg_carbon_per_acre_tons=18.5,
            species_count=42,
            most_recent_inventory=2022,
            loblolly_pine_pct=35.7,
        )
    )

    summary = await carbon.get_carbon_summary(mock_db, statecd=37)

    assert isinstance(summary, CarbonSummary)
    assert summary.statecd == 37
    assert summary.total_plots == 1500
    assert summary.species_count == 42
    assert summary.loblolly_pine_pct == 35.7


async def test_get_carbon_summary_null_inventory(mock_db: AsyncMock) -> None:
    """most_recent_inventory=None should return 0 via the `or 0` fallback."""
    mock_db.execute.return_value = mock_result_one(
        mock_row(
            statecd=37,
            total_plots=0,
            total_trees=0,
            total_carbon_ag_tons=0.0,
            total_carbon_bg_tons=0.0,
            avg_carbon_per_acre_tons=0.0,
            species_count=0,
            most_recent_inventory=None,
            loblolly_pine_pct=0.0,
        )
    )

    summary = await carbon.get_carbon_summary(mock_db, statecd=37)

    assert summary.most_recent_inventory == 0


async def test_get_carbon_summary_empty_data(mock_db: AsyncMock) -> None:
    """When no tree data exists, get_carbon_summary should return zeroed CarbonSummary."""
    mock_db.execute.return_value = mock_result_none()

    summary = await carbon.get_carbon_summary(mock_db, statecd=37)

    assert isinstance(summary, CarbonSummary)
    assert summary.statecd == 37
    assert summary.total_plots == 0
    assert summary.total_trees == 0
    assert summary.total_carbon_ag_tons == 0.0
    assert summary.avg_carbon_per_acre_tons == 0.0
    assert summary.species_count == 0
    assert summary.most_recent_inventory == 0
    assert summary.loblolly_pine_pct == 0.0


async def test_get_species_names_fallback(mock_db: AsyncMock) -> None:
    """When staging table doesn't exist, _get_species_names returns hardcoded dict."""
    mock_db.execute.side_effect = Exception("relation does not exist")

    names = await carbon._get_species_names(mock_db)

    assert isinstance(names, dict)
    assert names[131] == "loblolly pine"
    assert names[802] == "white oak"
    assert len(names) > 10


async def test_get_carbon_by_species_empty(mock_db: AsyncMock) -> None:
    """Empty species results should return an empty list."""
    mock_db.execute.side_effect = [
        mock_result_all([]),  # main species query
        Exception("relation does not exist"),  # _get_species_names fallback
    ]

    result = await carbon.get_carbon_by_species(mock_db, statecd=37)

    assert result == []


async def test_get_plots_geojson_empty(mock_db: AsyncMock) -> None:
    """Empty plot results should return a valid empty FeatureCollection."""
    mock_db.execute.side_effect = [
        mock_result_all([]),  # main plots query
        Exception("relation does not exist"),  # _get_species_names fallback
    ]

    result = await carbon.get_plots_geojson(mock_db, statecd=37)

    assert isinstance(result, PlotFeatureCollection)
    assert result.type == "FeatureCollection"
    assert result.features == []
