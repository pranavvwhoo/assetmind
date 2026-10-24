"""Streamlit interface for the IT asset report generator."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from src.agents import AgentConfigurationError, AgentExecutionError, run_crew
from src.analytics import calculate_analytics
from src.data_processor import DatasetError, inspect_frame, load_dataset
from src.report_generator import generate_pdf

ROOT = Path(__file__).resolve().parent
SAMPLE_PATH = ROOT / "assets" / "sample_assets.csv"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
load_dotenv()

st.set_page_config(page_title="AssetMind | IT Asset Reports", page_icon="📊", layout="wide")
st.markdown(
    """
    <style>
      .block-container {padding-top: 1.6rem; padding-bottom: 2.5rem;}
      [data-testid="stMetric"] {background:#f4f7fb; border:1px solid #e2e8f0;
        padding:14px 16px; border-radius:12px;}
      .assetmind-caption {color:#64748b;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("IT Asset Report Generator")
st.caption("Deterministic inventory analytics with a real, sequential four-agent CrewAI review.")

with st.sidebar:
    st.header("Dataset")
    upload = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx"], help="Maximum file size: 10 MB.")
    use_sample = st.button("Use synthetic sample dataset", width="stretch")
    st.caption("Report history is temporary and may be lost when this Streamlit session resets.")
    st.divider()
    st.caption("AI report generation requires GEMINI_API_KEY. Dataset-derived analysis is sent to Google Gemini.")

if "history" not in st.session_state:
    st.session_state.history = []
if "dataset" not in st.session_state:
    st.session_state.dataset = None
if "analysis" not in st.session_state:
    st.session_state.analysis = None

if use_sample:
    try:
        st.session_state.dataset = load_dataset(SAMPLE_PATH.read_bytes(), SAMPLE_PATH.name)
        st.session_state.analysis = None
        st.success("Loaded fictional sample data. It is synthetic and contains intentional quality issues.")
    except (OSError, DatasetError) as exc:
        st.error(f"Could not load the bundled sample: {exc}")

if upload is not None:
    try:
        st.session_state.dataset = load_dataset(upload.getvalue(), upload.name)
        st.session_state.analysis = None
    except DatasetError as exc:
        st.session_state.dataset = None
        st.session_state.analysis = None
        st.error(str(exc))

dataset = st.session_state.dataset
tab_overview, tab_analysis, tab_history = st.tabs(["Overview", "Analysis & report", "Report history"])

with tab_overview:
    if dataset is None:
        st.info("Upload an asset inventory or select the synthetic sample dataset in the sidebar.")
    else:
        metrics = calculate_analytics(dataset)
        st.subheader(f"Dataset preview · {dataset.source_name}")
        st.dataframe(dataset.frame.head(15), width="stretch", hide_index=True)
        left, right = st.columns(2)
        with left:
            st.markdown("**Recognized fields**")
            st.write(", ".join(dataset.recognized_columns) or "None detected")
            st.markdown("**Unrecognized fields (preserved)**")
            st.write(", ".join(dataset.unrecognized_columns) or "None")
        with right:
            st.markdown("**Validation**")
            if dataset.column_issues or dataset.validation_issues:
                for issue in dataset.column_issues + dataset.validation_issues:
                    st.warning(issue)
            else:
                st.success("Required identifier is present; no duplicate or missing IDs were detected.")
        if metrics["total_assets"] == 0:
            st.warning("The dataset has no asset rows. Add data before interpreting the metrics.")
        else:
            st.subheader("Deterministic overview")
            cols = st.columns(5)
            for col, label, key in zip(
                cols,
                ["Total assets", "Allocated", "Unallocated", "Retired", "Rows with missing data"],
                ["total_assets", "allocated_assets", "unallocated_assets", "retired_assets", "assets_with_missing_information"],
            ):
                col.metric(label, metrics[key])
            st.metric("Data-quality score", f'{metrics["data_quality_score"]}%')
            radar = metrics["attention_radar"]
            st.divider()
            st.subheader("Asset Attention Radar")
            st.caption(
                "A transparent, rule-based review queue—not a prediction of financial, security, or failure risk. "
                "Use it to prioritize human follow-up."
            )
            radar_col, priority_col = st.columns([1, 2])
            with radar_col:
                st.metric("Assets flagged for review", radar["assets_requiring_review"])
                st.caption(
                    f"As of {radar['as_of_date']} · {radar['review_threshold']}+ points · "
                    "priority reflects data-quality and lifecycle signals."
                )
            with priority_col:
                priority_values = radar["priority_counts"]
                if any(priority_values.values()):
                    chart = pd.DataFrame({
                        "Priority": list(priority_values),
                        "Assets": list(priority_values.values()),
                    })
                    st.plotly_chart(
                        px.bar(
                            chart, x="Priority", y="Assets", color="Priority",
                            color_discrete_map={"Urgent": "#c2413b", "High": "#e58b35", "Watch": "#d4ae35"},
                        ),
                        width="stretch",
                    )
                else:
                    st.success("No records crossed the review threshold.")
            if radar["review_queue"]:
                st.markdown("**Ranked review queue**")
                st.dataframe(
                    pd.DataFrame(radar["review_queue"])[
                        ["source_row", "asset_id", "score", "priority", "evidence", "next_action"]
                    ].rename(columns={
                        "source_row": "Source row", "asset_id": "Asset ID", "score": "Attention score",
                        "priority": "Priority", "evidence": "Evidence", "next_action": "Suggested next step",
                    }),
                    width="stretch", hide_index=True,
                )
                if radar["queue_truncated"]:
                    st.caption("Showing the 25 highest-scoring records; download the JSON for the summary and full available evidence.")
            with st.expander("How the attention score works"):
                st.write(radar["method"])
                st.json(radar["scoring_weights"])
                st.caption(
                    "Signals only use values that are present in the uploaded file. Warranty proximity uses the "
                    "report date; unknown or unparsable dates are not treated as expired."
                )
            chart_col1, chart_col2 = st.columns(2)
            for container, title, key in (
                (chart_col1, "Assets by category", "by_category"),
                (chart_col2, "Assets by department", "by_department"),
            ):
                with container:
                    st.markdown(f"**{title}**")
                    counts = metrics[key]
                    if counts:
                        chart_data = pd.DataFrame({"Group": list(counts), "Assets": list(counts.values())})
                        st.plotly_chart(px.bar(chart_data, x="Group", y="Assets"), width="stretch")
                    else:
                        st.caption("This field is not available.")
            st.markdown("**Assets by status**")
            if metrics["by_status"]:
                st.dataframe(
                    pd.DataFrame(metrics["by_status"].items(), columns=["Status", "Assets"]),
                    width="stretch", hide_index=True,
                )

with tab_analysis:
    st.subheader("Generate report")
    if dataset is None:
        st.info("Load a dataset to enable analysis.")
    else:
        st.caption("Calculations are deterministic. CrewAI runs synchronously; task completion is shown after the workflow returns.")
        if st.button("Generate Report", type="primary", disabled=len(dataset.frame) == 0):
            current = {
                "source_name": dataset.source_name,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "analytics": calculate_analytics(dataset),
                "ai_status": "not_started",
            }
            st.session_state.analysis = current
            with st.status("Calculating metrics and running the CrewAI sequential workflow…", expanded=True) as status:
                st.write("Deterministic validation and statistics completed.")
                try:
                    crew_result = run_crew(current["analytics"], dataset.source_name)
                    current.update(crew_result)
                    current["ai_status"] = "completed"
                    status.update(label="Analysis and four-agent quality review complete", state="complete")
                except (AgentConfigurationError, AgentExecutionError) as exc:
                    current["ai_status"] = "failed"
                    current["ai_error"] = str(exc)
                    if isinstance(exc, AgentExecutionError):
                        current["agent_events"] = exc.agent_events
                    status.update(label="AI analysis unavailable; deterministic analysis is preserved", state="error")
                except Exception as exc:
                    logging.exception("Unexpected report generation failure")
                    current["ai_status"] = "failed"
                    current["ai_error"] = f"Unexpected error ({type(exc).__name__})."
                    status.update(label="AI analysis failed; deterministic analysis is preserved", state="error")
            st.session_state.analysis = current
            st.session_state.history.insert(0, {
                "generated_at": current["generated_at"],
                "source_name": current["source_name"],
                "total_assets": current["analytics"]["total_assets"],
                "ai_status": current["ai_status"],
            })
            del st.session_state.history[20:]

        current = st.session_state.analysis
        if current:
            metrics = current["analytics"]
            st.divider()
            if current["ai_status"] == "completed":
                st.success("All four CrewAI agents completed. Review their outputs below.")
            elif current["ai_status"] == "failed":
                st.error(current.get("ai_error", "CrewAI report generation failed."))
            st.subheader("Verified asset statistics")
            st.json({
                key: metrics[key] for key in (
                    "total_assets", "allocated_assets", "unallocated_assets",
                    "allocation_unknown_assets", "retired_assets", "active_assets",
                    "retirement_unknown_assets", "assets_with_missing_information",
                    "data_quality_score", "duplicate_identifier_values",
                )
            })
            radar = metrics["attention_radar"]
            st.subheader("Asset Attention Radar")
            st.metric("Records prioritized for human review", radar["assets_requiring_review"])
            st.caption(
                f"Rule-based score as of {radar['as_of_date']}; not a financial, cyber-security, or failure-risk prediction."
            )
            if radar["review_queue"]:
                st.dataframe(
                    pd.DataFrame(radar["review_queue"][:10])[
                        ["source_row", "asset_id", "score", "priority", "evidence", "next_action"]
                    ].rename(columns={
                        "source_row": "Source row", "asset_id": "Asset ID", "score": "Attention score",
                        "priority": "Priority", "evidence": "Evidence", "next_action": "Suggested next step",
                    }),
                    width="stretch", hide_index=True,
                )
            if current.get("agent_events"):
                st.markdown("**CrewAI task execution**")
                st.dataframe(pd.DataFrame(current["agent_events"]), width="stretch", hide_index=True)
            if current["ai_status"] == "completed":
                report = current["report"]
                st.subheader("Executive summary")
                st.write(report["executive_summary"])
                st.subheader("Findings")
                for item in report.get("findings", []):
                    st.markdown(f"**{item.get('severity', 'info').upper()} · {item.get('title', 'Finding')}**")
                    st.write(item.get("detail", ""))
                st.subheader("Data-quality findings")
                for item in current["quality_analysis"].get("findings", []):
                    st.markdown(f"**{item.get('severity', 'info').upper()} · {item.get('title', 'Finding')}**")
                    st.write(item.get("detail", ""))
                st.subheader("Recommendations")
                if report.get("recommendations"):
                    st.dataframe(pd.DataFrame(report["recommendations"]), width="stretch", hide_index=True)
                st.subheader("Final quality review")
                review = current["quality_review"]
                (st.success if review["passed"] else st.warning)(
                    "Passed evidence and section checks." if review["passed"] else "Reviewer flagged issues."
                )
                if review.get("issues") or review.get("unsupported_claims"):
                    st.write(review.get("issues", []) + review.get("unsupported_claims", []))
                st.caption("Analytics specialist observations and hypotheses")
                st.json(current["analytics_interpretation"])
            try:
                pdf_bytes = generate_pdf(current)
                filename = f"asset-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf"
                st.download_button("Download PDF report", pdf_bytes, filename, "application/pdf")
            except Exception as exc:
                logging.exception("PDF generation failed")
                st.error(f"PDF generation failed ({type(exc).__name__}).")
            json_bytes = json.dumps(current, indent=2, ensure_ascii=False).encode("utf-8")
            st.download_button(
                "Download structured JSON", json_bytes,
                f"asset-analysis-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json",
                "application/json",
            )

with tab_history:
    st.subheader("Session report history")
    st.caption("Temporary history for this active Streamlit session only; it is not stored in a database.")
    if st.session_state.history:
        st.dataframe(pd.DataFrame(st.session_state.history), width="stretch", hide_index=True)
    else:
        st.info("No reports have been generated in this session.")
