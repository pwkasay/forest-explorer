"""Tests for the QA/QC engine — async checks with mocked DB."""

from unittest.mock import AsyncMock

import pytest

from app.schemas.carbon import QACheckResult, QARunSummary
from app.services import qa_engine
from tests.conftest import mock_result_one, mock_row


async def test_check_null_coordinates_clean(mock_db: AsyncMock) -> None:
    """Zero failures should produce severity 'info'."""
    mock_db.execute.return_value = mock_result_one(mock_row(total=100, failed=0))

    result = await qa_engine.check_null_coordinates(mock_db)

    assert isinstance(result, QACheckResult)
    assert result.check_name == "null_coordinates"
    assert result.records_checked == 100
    assert result.records_failed == 0
    assert result.severity == "info"
    assert result.failure_rate == 0.0


async def test_check_null_coordinates_with_failures(mock_db: AsyncMock) -> None:
    """Failures should produce severity 'error' with correct rate."""
    mock_db.execute.return_value = mock_result_one(mock_row(total=100, failed=5))

    result = await qa_engine.check_null_coordinates(mock_db)

    assert result.severity == "error"
    assert result.records_failed == 5
    assert result.failure_rate == pytest.approx(0.05)


async def test_check_coordinate_bounds_clean(mock_db: AsyncMock) -> None:
    """No out-of-bounds plots should produce severity 'info'."""
    mock_db.execute.return_value = mock_result_one(mock_row(total=200, failed=0))

    result = await qa_engine.check_coordinate_bounds(mock_db)

    assert result.check_name == "coordinate_bounds_conus"
    assert result.severity == "info"


async def test_check_negative_carbon_clean(mock_db: AsyncMock) -> None:
    """No negative carbon values should produce severity 'info'."""
    mock_db.execute.return_value = mock_result_one(mock_row(total=500, failed=0))

    result = await qa_engine.check_negative_carbon(mock_db)

    assert result.check_name == "negative_carbon_or_biomass"
    assert result.severity == "info"


async def test_check_diameter_outliers_warning(mock_db: AsyncMock) -> None:
    """Diameter outliers should produce severity 'warning'."""
    mock_db.execute.return_value = mock_result_one(mock_row(total=500, failed=3))

    result = await qa_engine.check_diameter_outliers(mock_db)

    assert result.severity == "warning"
    assert result.records_failed == 3


async def test_check_orphaned_trees_clean(mock_db: AsyncMock) -> None:
    """No orphaned trees should produce severity 'info'."""
    mock_db.execute.return_value = mock_result_one(mock_row(total=1000, failed=0))

    result = await qa_engine.check_orphaned_trees(mock_db)

    assert result.check_name == "orphaned_trees"
    assert result.severity == "info"


async def test_check_inventory_year_range_clean(mock_db: AsyncMock) -> None:
    """Normal year range should produce severity 'info'."""
    mock_db.execute.return_value = mock_result_one(
        mock_row(total=100, failed=0, min_year=2000, max_year=2023)
    )

    result = await qa_engine.check_inventory_year_range(mock_db)

    assert result.check_name == "inventory_year_range"
    assert result.severity == "info"
    assert result.details is not None
    assert result.details["min_year"] == 2000
    assert result.details["max_year"] == 2023


async def test_run_all_checks_returns_summary(mock_db: AsyncMock) -> None:
    """run_all_checks should execute all checks and return a valid summary."""
    # Mock responses for each of the 6 checks in ALL_CHECKS order
    mock_db.execute.side_effect = [
        mock_result_one(mock_row(total=100, failed=0)),  # null_coordinates
        mock_result_one(mock_row(total=100, failed=0)),  # coordinate_bounds
        mock_result_one(mock_row(total=100, failed=0)),  # negative_carbon
        mock_result_one(mock_row(total=100, failed=0)),  # diameter_outliers
        mock_result_one(mock_row(total=100, failed=0)),  # orphaned_trees
        mock_result_one(mock_row(total=100, failed=0, min_year=2000, max_year=2023)),
    ]

    summary = await qa_engine.run_all_checks(mock_db)

    assert isinstance(summary, QARunSummary)
    assert summary.total_checks == len(qa_engine.ALL_CHECKS)
    assert len(summary.checks) == len(qa_engine.ALL_CHECKS)
    assert summary.run_id  # non-empty UUID string
    assert summary.errors == 0
    assert summary.warnings == 0
