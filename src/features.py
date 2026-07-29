"""Feature functions for the UK business risk model. Each function computes
one signal from a company's filing or officer history, relative to a given
snapshot date. Used both for building the training table and, without
snapshot filtering, for live company lookups.
"""

import json
from pathlib import Path

import pandas as pd


def days_since_last_accounts(filings: list, snapshot_date: pd.Timestamp) -> float:
    """Return days since the most recent accounts filing before the snapshot
    date. A long gap suggests the company has fallen behind on statutory
    filing. Missing entirely (never filed) returns NaN.
    """
    accounts_dates = [
        pd.to_datetime(f["date"]) for f in filings if f.get("type") in ("AA", "AAMD")
    ]
    if not accounts_dates:
        return float("nan")
    return (snapshot_date - max(accounts_dates)).days


def count_late_confirmation_statements(filings: list) -> int:
    """Count confirmation statements filed more than 379 days after the
    previous one (12 months plus the 14 day statutory grace period).
    """
    dates = sorted(pd.to_datetime(f["date"]) for f in filings if f.get("type") == "CS01")
    if len(dates) < 2:
        return 0
    gaps = pd.Series(dates).diff().dropna().dt.days
    return int((gaps > 379).sum())


def count_recent_resignations(officers: list, snapshot_date: pd.Timestamp) -> int:
    """Count officers who resigned in the 12 months before the snapshot date."""
    window_start = snapshot_date - pd.DateOffset(months=12)
    count = 0
    for o in officers:
        resigned_on = o.get("resigned_on")
        if resigned_on and window_start <= pd.to_datetime(resigned_on) < snapshot_date:
            count += 1
    return count


def count_new_charges(filings: list, snapshot_date: pd.Timestamp) -> int:
    """Count MR01 filings (new charge created) in the 24 months before the
    snapshot date. A charge is a lender securing debt against company assets.
    """
    window_start = snapshot_date - pd.DateOffset(months=24)
    count = 0
    for f in filings:
        if f.get("type") == "MR01":
            filed_on = pd.to_datetime(f["date"])
            if window_start <= filed_on < snapshot_date:
                count += 1
    return count


def company_age_years(profile: dict, snapshot_date: pd.Timestamp) -> float:
    """Return the company's age in years at the snapshot date."""
    incorporated = pd.to_datetime(profile["date_of_creation"])
    return (snapshot_date - incorporated).days / 365.25


def longest_filing_gap(filings: list, snapshot_date: pd.Timestamp) -> float:
    """Return the longest gap in days between consecutive filings before the
    snapshot date. A long gap can indicate a company has gone quiet.
    """
    dates = sorted(pd.to_datetime(f["date"]) for f in filings if pd.to_datetime(f["date"]) < snapshot_date)
    if len(dates) < 2:
        return float("nan")
    gaps = pd.Series(dates).diff().dropna().dt.days
    return float(gaps.max())


def filter_before_snapshot(data: dict, snapshot_date: pd.Timestamp) -> dict:
    """Return a version of a company's data containing only information
    available before its snapshot date.
    """
    filings = [
        item for item in data["filings"]["items"]
        if pd.to_datetime(item.get("date")) < snapshot_date
    ]
    officers = [
        o for o in data["officers"]["items"]
        if pd.to_datetime(o.get("appointed_on", "1900-01-01")) < snapshot_date
    ]
    return {"profile": data["profile"], "filings": filings, "officers": officers}


def get_failure_date(filings_items):
    """Return the date liquidation started, or None if no clear marker exists."""
    for target_type in ("600", "COCOMP"):
        matches = [item["date"] for item in filings_items if item.get("type") == target_type]
        if matches:
            return min(matches)
    return None


def director_distress_count_safe(officer_link: str, snapshot_date: pd.Timestamp,
                                   linked_failure_dates: dict, directors_dir: Path) -> int:
    """Count how many of a director's other companies had already failed,
    with a known failure date before the snapshot date.
    """
    officer_id = officer_link.split("/")[2]
    path = directors_dir / f"{officer_id}.json"
    if not path.exists():
        return 0
    data = json.loads(path.read_text())
    count = 0
    for item in data.get("items", []):
        other_number = item.get("appointed_to", {}).get("company_number")
        other_failure_date = linked_failure_dates.get(other_number)
        if other_failure_date is not None and other_failure_date < snapshot_date:
            count += 1
    return count


def company_director_distress_safe(officers: list, snapshot_date: pd.Timestamp,
                                     linked_failure_dates: dict, directors_dir: Path) -> int:
    """Sum of safe distress counts across all directors of one company."""
    total = 0
    for o in officers:
        if o.get("officer_role") == "director":
            link = o.get("links", {}).get("officer", {}).get("appointments")
            if link:
                total += director_distress_count_safe(link, snapshot_date, linked_failure_dates, directors_dir)
    return total