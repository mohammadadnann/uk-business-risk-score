# UK SME Credit Risk Intelligence Platform

**Production-ready credit risk intelligence platform for UK private limited SMEs using Companies House data.**

![dashboard screenshot placeholder](docs/screenshot.png)

### Built for
- Credit controllers
- Suppliers
- Procurement teams
- Commercial lenders

## Key Features

- **Live insolvency risk intelligence** — Generates explainable risk scores for eligible UK private limited companies through real-time Companies House lookups.
- **Calibrated probabilities** — Uses isotonic regression so predicted risk better reflects observed historical insolvency rates.
- **Explainable AI** — SHAP explanations highlight the key behavioural signals influencing each prediction in plain English.
- **Model governance** — Detects companies outside the trained population (e.g. PLCs and banks) and withholds unsupported predictions rather than returning misleading scores.
- **Leakage-safe modelling** — Uses snapshot-based feature engineering to ensure no post-event information is available during prediction.
- **Production deployment** — Containerised FastAPI and Streamlit application with live scoring through Docker Compose.

## Why this matters

UK SMEs make up 99.85% of private sector businesses but get none of the credit-risk visibility large listed companies do. This platform closes that gap with a live, explainable insolvency signal built entirely on public data.

## System Architecture

Companies House API
│
▼
Feature Engineering
│
▼
Leakage Validation
│
▼
XGBoost
│
▼
Probability Calibration
│
▼
SHAP Explanation
│
▼
Eligibility Validation
│
▼
FastAPI
│
▼
Streamlit

## Model Performance

| Capability | Result |
|---|---|
| Precision @ Top 10% | **0.72** |
| Baseline | 0.52 |
| Probability Calibration | 16pp → 11pp error |
| Explainability | SHAP |
| Deployment | FastAPI + Streamlit + Docker |

## Tech Stack

**Machine Learning**
- XGBoost, scikit-learn (calibration), SHAP

**Data Engineering**
- pandas, Companies House REST API

**API**
- FastAPI

**Frontend**
- Streamlit

**Deployment**
- Docker, Docker Compose

**Testing**
- pytest

## Quick Start

```bash
docker compose up --build
```
Open `http://localhost:8501`. Requires a free Companies House API key in `.env` (see `.env.example`).

## Data Sources

- [Companies House Bulk Data](http://download.companieshouse.gov.uk/en_output.html) & [REST API](https://developer-specs.company-information.service.gov.uk/)
- [UK Business Population Estimates 2025](https://www.gov.uk/government/statistics/business-population-estimates-2025/business-population-estimates-for-the-uk-and-regions-2025-statistical-release)
- [Business Insolvency Demography 2015–2025](https://www.gov.uk/government/statistics/business-insolvency-demography-2015-to-2025)

## Model Scope

- Scored population is UK private limited SMEs only; PLCs, banks, and out-of-range companies are flagged and withheld, not scored
- Director network feature uses historical data only; defaults to 0 for live lookups (real-time network traversal is too slow for a single request)
- 247 of 1,500 originally identified failed companies lacked a reliable failure date and were excluded from training
- Calibration validated at 5 probability bands due to test set size (503 companies)

Full technical rationale, investigation notes, and design decisions: [`decisions.md`](decisions.md)