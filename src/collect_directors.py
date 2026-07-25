"""Collect appointment history for directors linked to failed companies, to
build a director network feature. Saves one JSON file per director, safe to
stop and rerun since already collected directors are skipped.
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
DIRECTOR_DIR = Path(__file__).resolve().parents[1] / "data" / "directors"


def fetch_director_appointments(link: str) -> dict:
    """Call a director's appointments endpoint, retrying once on a 429."""
    url = f"{BASE_URL}{link}"
    r = requests.get(url, auth=(API_KEY, ""))
    if r.status_code == 429:
        time.sleep(int(r.headers.get("Retry-After", 5)))
        r = requests.get(url, auth=(API_KEY, ""))
    r.raise_for_status()
    return r.json()


def collect_directors(director_links: set, sleep_seconds: float = 1.0) -> None:
    """Loop over director appointment links and save each one, skipping
    anything already collected.
    """
    DIRECTOR_DIR.mkdir(parents=True, exist_ok=True)

    done = 0
    skipped = 0
    failed = []

    for i, link in enumerate(sorted(director_links), start=1):
        officer_id = link.split("/")[2]
        out_path = DIRECTOR_DIR / f"{officer_id}.json"
        if out_path.exists():
            skipped += 1
            continue

        try:
            data = fetch_director_appointments(link)
            out_path.write_text(json.dumps(data))
            done += 1
        except Exception as e:
            failed.append((link, str(e)))

        time.sleep(sleep_seconds)

        if i % 200 == 0:
            print(f"{i}/{len(director_links)} processed, {done} collected, {skipped} skipped, {len(failed)} failed")

    print(f"finished. collected: {done}, skipped: {skipped}, failed: {len(failed)}")
    if failed:
        print("failed links:", failed[:10])



        