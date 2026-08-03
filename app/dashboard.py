"""Streamlit dashboard for the UK SME Credit Risk Intelligence Platform.
Calls the running FastAPI service and displays a company's risk score
with SHAP based reasons in a visual, readable way.
"""

import requests
import streamlit as st
import os
API_URL = os.getenv("API_URL", "http://127.0.0.1:8003")

FEATURE_LABELS_DISPLAY = {
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

st.set_page_config(page_title="UK SME Credit Risk Intelligence Platform", page_icon="📊", layout="centered")

st.markdown(
    """
    <style>
    .risk-card {
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .risk-high { background-color: #fde8e8; border: 1px solid #f5b5b5; }
    .risk-medium { background-color: #fef3e0; border: 1px solid #f5d38a; }
    .risk-low { background-color: #e6f4ea; border: 1px solid #a8d5b5; }
    .risk-number { font-size: 3rem; font-weight: 700; margin: 0; }
    .reason-card {
        padding: 0.9rem 1.1rem;
        border-radius: 10px;
        margin-bottom: 0.6rem;
        border-left: 4px solid;
    }
    .reason-up { background-color: #fdf1f1; border-left-color: #d9534f; }
    .reason-down { background-color: #eef8f0; border-left-color: #4caf50; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📊 UK SME Credit Risk Intelligence Platform")
st.caption("Live insolvency risk intelligence for UK SMEs, built on Companies House data.")

col1, col2 = st.columns([3, 1])
with col1:
    company_number = st.text_input(
    "Company number", value="",
    label_visibility="collapsed", placeholder="Enter a UK company number"
    )
with col2:
    check = st.button("Check risk", use_container_width=True)

if check:
    with st.spinner("Fetching live company data and scoring..."):
        try:
            response = requests.get(f"{API_URL}/score/{company_number}", timeout=30)
        except requests.exceptions.ConnectionError:
            st.error("Could not reach the scoring service. Is the API running?")
            st.stop()

    if response.status_code == 404:
        st.error("Company not found. Check the company number and try again.")
    else:
        data = response.json()

        if data.get("out_of_distribution"):
            st.markdown(
                f"""
                <div class="risk-card" style="background-color: #f0f0f0; border: 1px solid #ccc;">
                    <p style="margin:0; font-size:1.1rem; color:#555;">{data['company_name']}</p>
                    <p style="font-size:1.6rem; font-weight:700; margin:0.5rem 0;">⚠️ Prediction unavailable</p>
                    <p style="margin:0; color:#555;">This company falls outside the population the model was trained on
                    (UK private limited SMEs). A reliable insolvency risk estimate cannot be produced.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.subheader("Reasons")
            for reason in data.get("ood_reasons", []):
                st.markdown(f"- {reason}")
        else:
            risk = data["risk_score"]

            if risk >= 0.6:
                css_class = "risk-high"
                label = "High risk"
            elif risk >= 0.3:
                css_class = "risk-medium"
                label = "Medium risk"
            else:
                css_class = "risk-low"
                label = "Low risk"

            risk_html = (
                '<div class="risk-card ' + css_class + '">'
                '<p style="margin:0; font-size:1.1rem; color:#555;">' + data["company_name"] + '</p>'
                '<p class="risk-number">' + f"{risk * 100:.1f}%" + '</p>'
                '<p style="margin:0; font-weight:600;">' + label + '</p>'
                '</div>'
            )
            st.markdown(risk_html, unsafe_allow_html=True)

            st.subheader("What's driving this score")
            for reason in data["top_reasons"]:
                if reason["direction"] == "increased":
                    direction_class = "reason-up"
                    arrow = "⬆️"
                else:
                    direction_class = "reason-down"
                    arrow = "⬇️"

                reason_html = (
                    '<div class="reason-card ' + direction_class + '">'
                    + arrow + ' <strong>' + reason["feature"] + '</strong>'
                    + ' — value: ' + str(reason["value"])
                    + (" days" if reason["feature"] in ("Time since accounts filed", "Longest gap between filings") else "")
                    + '<br><span style="color:#666; font-size:0.9rem;">'
                    + reason["direction"].capitalize() + ' the risk score</span>'
                    '</div>'
                )
                st.markdown(reason_html, unsafe_allow_html=True)

        with st.expander("See remaining feature values"):
            shown_features = {r["feature"] for r in data.get("top_reasons", [])}
            # Mapping back from the display label to the underlying feature key,
            # so we can skip anything already shown above.
            remaining = {
                key: value for key, value in data["features"].items()
                if FEATURE_LABELS_DISPLAY.get(key, key) not in shown_features
            }
            metric_cols = st.columns(3)
            for i, (key, value) in enumerate(remaining.items()):
                with metric_cols[i % 3]:
                    st.metric(key.replace("_", " ").title(), value)