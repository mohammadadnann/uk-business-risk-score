"""Collect filing history for companies linked to our cohort through shared
directors, so we can find their real failure dates instead of trusting
their current status, which would leak future information.
"""

import json
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
import os

load_dotenv()
API_KEY = os.getenv("CH_API_KEY")
BASE_URL = "https://api.company-information.service.gov.uk"
FILINGS_DIR = Path(__file__).resolve().parents[1] / "data" / "director_links"


def fetch_filing_history(company_number: str) -> dict:
    """Call a company's filing history endpoint, retrying once on a 429."""
    url = f"{BASE_URL}/company/{company_number}/filing-history"
    r = requests.get(url, auth=(API_KEY, ""))
    if r.status_code == 429:
        time.sleep(int(r.headers.get("Retry-After", 5)))
        r = requests.get(url, auth=(API_KEY, ""))
    r.raise_for_status()
    return r.json()


def collect_director_links(company_numbers: set, sleep_seconds: float = 1.0) -> None:
    """Loop over linked company numbers and save filing history, skipping
    anything already collected.
    """
    FILINGS_DIR.mkdir(parents=True, exist_ok=True)

    done = 0
    skipped = 0
    failed = []

    for i, number in enumerate(sorted(company_numbers), start=1):
        out_path = FILINGS_DIR / f"{number}.json"
        if out_path.exists():
            skipped += 1
            continue

        try:
            data = fetch_filing_history(number)
            out_path.write_text(json.dumps(data))
            done += 1
        except Exception as e:
            failed.append((number, str(e)))

        time.sleep(sleep_seconds)

        if i % 200 == 0:
            print(f"{i}/{len(company_numbers)} processed, {done} collected, {skipped} skipped, {len(failed)} failed")

    print(f"finished. collected: {done}, skipped: {skipped}, failed: {len(failed)}")
    if failed:
        print("failed numbers:", failed[:10])