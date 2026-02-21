"""Shared test fixtures."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def mock_db() -> AsyncMock:
    """Async mock of a SQLAlchemy AsyncSession."""
    return AsyncMock(spec=AsyncSession)


def mock_row(**kwargs: object) -> MagicMock:
    """Create a mock result row with named attributes."""
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


def mock_result_one(row: MagicMock) -> MagicMock:
    """Create a mock DB execute result that returns one row via .one() or .one_or_none()."""
    result = MagicMock()
    result.one.return_value = row
    result.one_or_none.return_value = row
    return result


def mock_result_none() -> MagicMock:
    """Create a mock DB execute result where .one_or_none() returns None (empty result set)."""
    result = MagicMock()
    result.one_or_none.return_value = None
    return result


def mock_result_all(rows: list[MagicMock]) -> MagicMock:
    """Create a mock DB execute result that returns rows via .all()."""
    result = MagicMock()
    result.all.return_value = rows
    return result
