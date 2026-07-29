"""FastAPI service for the UK business risk model. Given a real company
number, fetches its current data from Companies House, computes the same
features used in training, and returns a risk score with SHAP based
reasons.
"""

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import shap
import xgboost as xgb
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from src.features import (
    days_since_last_accounts,
    count_late_confirmation_statements,
    count_recent_resignations,
    count_new_charges,
    company_age_years,
    longest_filing_gap,
)

load_dotenv()
API_KEY = os.getenv("CH_API_KEY")
BASE_URL = "https://api.company-information.service.gov.uk"

app = FastAPI(title="UK Business Risk Predictor")

model = xgb.XGBClassifier()
model.load_model(Path(__file__).resolve().parents[1] / "data" / "model.json")
explainer = shap.TreeExplainer(model)

FEATURE_COLS = [
    "days_since_last_accounts", "count_late_confirmation_statements",
    "count_recent_resignations", "count_new_charges", "company_age_years",
    "longest_filing_gap", "accounts_missing", "filing_gap_missing",
    "director_distress_score_safe",
]

FEATURE_LABELS = {
    "days_since_last_accounts": "Time since accounts filed",
    "count_late_confirmation_statements": "Late confirmation statements",
    "count_recent_resignations": "Recent director resignations",
    "count_new_charges": "New charges registered",
    "company_age_years": "Company age",
    "longest_filing_gap": "Longest gap between filings",
    "accounts_missing": "No accounts due date on record",
    "filing_gap_missing": "Limited filing history",
    "director_distress_score_safe": "Directors linked to prior failures",
}


def fetch_company_data(company_number: str) -> dict:
    """Fetch a company's profile, filings, and officers from the live API."""
    auth = (API_KEY, "")
    profile = requests.get(f"{BASE_URL}/company/{company_number}", auth=auth)
    if profile.status_code == 404:
        raise HTTPException(404, "Company not found")
    profile.raise_for_status()
    filings = requests.get(f"{BASE_URL}/company/{company_number}/filing-history", auth=auth).json()
    officers = requests.get(f"{BASE_URL}/company/{company_number}/officers", auth=auth).json()
    return {"profile": profile.json(), "filings": filings, "officers": officers}


@app.get("/score/{company_number}")
def score_company(company_number: str):
    """Return a risk score for a real UK company, using today as the
    effective snapshot date.
    """
    data = fetch_company_data(company_number)
    snapshot = pd.Timestamp(datetime.utcnow())

    filings = data["filings"].get("items", [])
    officers = data["officers"].get("items", [])
    profile = data["profile"]

    features = {
        "days_since_last_accounts": int(round(days_since_last_accounts(filings, snapshot) or 0)),
        "count_late_confirmation_statements": count_late_confirmation_statements(filings),
        "count_recent_resignations": count_recent_resignations(officers, snapshot),
        "count_new_charges": count_new_charges(filings, snapshot),
        "company_age_years": round(company_age_years(profile, snapshot), 1),
        "longest_filing_gap": int(round(longest_filing_gap(filings, snapshot) or 0)),
        "director_distress_score_safe": 0,
    }
    features["accounts_missing"] = int(pd.isna(features["days_since_last_accounts"]))
    features["filing_gap_missing"] = int(pd.isna(features["longest_filing_gap"]))
    features["days_since_last_accounts"] = features["days_since_last_accounts"] or 0
    features["longest_filing_gap"] = features["longest_filing_gap"] or 0

    row = pd.DataFrame([features])[FEATURE_COLS]
    risk_score = float(model.predict_proba(row)[0][1])

    shap_values = explainer.shap_values(row)[0]
    # Excluding the director network feature from live explanations, since it
    # is not computed in real time for a live lookup and would be misleading
    # to present as a genuine driver of the score.
    contributions = sorted(
        [
            (name, shap_val, features[name])
            for name, shap_val in zip(FEATURE_COLS, shap_values)
            if name != "director_distress_score_safe"
        ],
        key=lambda x: abs(x[1]),
        reverse=True,
    )
    top_reasons = [
        {
            "feature": FEATURE_LABELS.get(name, name),
            "value": val,
            "impact": round(float(shap_val), 4),
            "direction": "increased" if shap_val > 0 else "decreased",
        }
        for name, shap_val, val in contributions[:5]
    ]

    ocompany_category = profile.get("type", "")
    company_category = profile.get("type", "") or ""
    out_of_distribution = (
        features["company_age_years"] > 50
        or features["count_recent_resignations"] >= 3
        or "plc" in company_category.lower()
    )

    return {
        "company_number": company_number,
        "company_name": profile.get("company_name"),
        "risk_score": round(risk_score, 4),
        "top_reasons": top_reasons,
        "features": features,
        "out_of_distribution": out_of_distribution,
    }