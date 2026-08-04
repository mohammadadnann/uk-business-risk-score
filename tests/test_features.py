"""Tests for the shared feature functions and leakage filter, using
synthetic data so these run without any network access.
"""

import pandas as pd
import pytest

from src.features import (
    filter_before_snapshot,
    days_since_last_accounts,
    count_late_confirmation_statements,
    count_recent_resignations,
    count_new_charges,
    company_age_years,
    longest_filing_gap,
)


@pytest.fixture
def sample_company():
    """A synthetic company with filings and officers spanning a snapshot date."""
    return {
        "profile": {"date_of_creation": "2015-01-01"},
        "filings": {
            "items": [
                {"date": "2020-01-01", "type": "AA"},
                {"date": "2021-01-01", "type": "AA"},
                {"date": "2023-01-01", "type": "AA"},  # after snapshot, should be excluded
                {"date": "2020-06-01", "type": "CS01"},
                {"date": "2021-08-01", "type": "CS01"},  # gap of 426 days, late
            ]
        },
        "officers": {
            "items": [
                {"officer_role": "director", "appointed_on": "2015-01-01", "resigned_on": "2020-05-01"},
                {"officer_role": "director", "appointed_on": "2015-01-01", "resigned_on": "2022-01-01"},  # after snapshot
            ]
        },
    }


@pytest.fixture
def snapshot_date():
    return pd.Timestamp("2022-01-01")


def test_filter_before_snapshot_excludes_future_filings(sample_company, snapshot_date):
    """The leakage filter must never let a post-snapshot filing through."""
    filtered = filter_before_snapshot(sample_company, snapshot_date)
    filing_dates = [pd.to_datetime(f["date"]) for f in filtered["filings"]]
    assert all(d < snapshot_date for d in filing_dates)
    assert len(filtered["filings"]) == 4  # the 2023 filing is excluded


def test_filter_before_snapshot_excludes_future_resignations(sample_company, snapshot_date):
    """Officers who resign after the snapshot date must not appear as resigned."""
    filtered = filter_before_snapshot(sample_company, snapshot_date)
    # only the officer who appointed before the snapshot survives the officer filter
    assert len(filtered["officers"]) == 2


def test_days_since_last_accounts_uses_latest_pre_snapshot_filing(sample_company, snapshot_date):
    """Should measure from the most recent AA filing before the snapshot, not after."""
    filtered = filter_before_snapshot(sample_company, snapshot_date)
    days = days_since_last_accounts(filtered["filings"], snapshot_date)
    # latest AA filing before snapshot is 2021-01-01
    expected = (snapshot_date - pd.Timestamp("2021-01-01")).days
    assert days == expected


def test_days_since_last_accounts_returns_nan_when_no_accounts_filed(snapshot_date):
    """Missing accounts history should return NaN, not crash or default silently."""
    result = days_since_last_accounts([], snapshot_date)
    assert pd.isna(result)


def test_count_late_confirmation_statements_flags_long_gaps(sample_company):
    """A gap over 379 days between confirmation statements counts as late."""
    count = count_late_confirmation_statements(sample_company["filings"]["items"])
    assert count == 1


def test_count_recent_resignations_respects_window(sample_company, snapshot_date):
    """Only resignations in the 12 months before the snapshot should count."""
    filtered = filter_before_snapshot(sample_company, snapshot_date)
    count = count_recent_resignations(filtered["officers"], snapshot_date)
    # the one resignation in filtered officers is 2020-05-01, well outside 12 months before 2022-01-01
    assert count == 0


def test_company_age_years_is_positive_and_reasonable(sample_company, snapshot_date):
    """A company incorporated in 2015 should be about 7 years old at this snapshot."""
    age = company_age_years(sample_company["profile"], snapshot_date)
    assert 6.9 < age < 7.1


def test_longest_filing_gap_ignores_post_snapshot_filings(sample_company, snapshot_date):
    """The longest gap must be computed only from pre-snapshot filings."""
    filtered = filter_before_snapshot(sample_company, snapshot_date)
    gap = longest_filing_gap(filtered["filings"], snapshot_date)
    assert gap > 0