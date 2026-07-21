"""Collect profile, filing history, and officers for each company in the
cohort, saving one combined JSON file per company. Safe to stop and rerun,
since already collected companies are skipped.
"""

import json
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("CH_API_KEY")
BASE_URL = "https://api.company-information.service.gov.uk"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def fetch_company(number: str) -> dict:
    """Call the three endpoints for one company and combine the results."""
    auth = (API_KEY, "")
    profile = requests.get(f"{BASE_URL}/company/{number}", auth=auth).json()
    filings = requests.get(f"{BASE_URL}/company/{number}/filing-history", auth=auth).json()
    officers = requests.get(f"{BASE_URL}/company/{number}/officers", auth=auth).json()
    return {"profile": profile, "filings": filings, "officers": officers}


def collect_cohort(cohort_path: str, sleep_seconds: float = 0.6) -> None:
    """Loop over every company in the cohort and save its data, skipping
    anything already collected.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cohort = pd.read_parquet(cohort_path)
    numbers = cohort["CompanyNumber"].tolist()

    done = 0
    skipped = 0
    failed = []

    for i, number in enumerate(numbers, start=1):
        out_path = RAW_DIR / f"{number}.json"
        if out_path.exists():
            skipped += 1
            continue

        try:
            data = fetch_company(number)
            out_path.write_text(json.dumps(data))
            done += 1
        except Exception as e:
            failed.append((number, str(e)))

        time.sleep(sleep_seconds)

        if i % 50 == 0:
            print(f"{i}/{len(numbers)} processed, {done} collected, {skipped} skipped, {len(failed)} failed")

    print(f"finished. collected: {done}, skipped: {skipped}, failed: {len(failed)}")
    if failed:
        print("failed company numbers:", failed[:10])