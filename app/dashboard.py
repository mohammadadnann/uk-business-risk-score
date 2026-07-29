"""Streamlit dashboard for the UK business risk model. Calls the running
FastAPI service and displays a company's risk score with SHAP based
reasons in a visual, readable way.
"""

import requests
import streamlit as st

API_URL = "http://127.0.0.1:8003"

st.set_page_config(page_title="UK Business Risk Predictor", page_icon="📊", layout="centered")

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

st.title("📊 UK Business Risk Predictor")
st.caption("Live insolvency risk scoring for UK companies, built on Companies House data.")

col1, col2 = st.columns([3, 1])
with col1:
    company_number = st.text_input(
        "Company number", value="00006400",
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
            st.warning(
                "This company is significantly older or larger than typical companies "
                "in the training data (e.g. large PLCs). The model was trained mainly "
                "on small and medium private limited companies, so this score should "
                "be treated with extra caution."
            )

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
                + ' — value: ' + str(reason["value"]) + (" days" if reason["feature"] in ("Time since accounts filed", "Longest gap between filings") else "")
                + '<br><span style="color:#666; font-size:0.9rem;">'
                + reason["direction"].capitalize() + ' the risk score</span>'
                '</div>'
            )
            st.markdown(reason_html, unsafe_allow_html=True)

        with st.expander("See all raw feature values"):
            metric_cols = st.columns(3)
            for i, (key, value) in enumerate(data["features"].items()):
                with metric_cols[i % 3]:
                    st.metric(key.replace("_", " ").title(), value)