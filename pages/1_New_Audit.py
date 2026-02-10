"""
New Audit page -- configure and run a website audit.
"""

import os
import sys
import time
import queue
import asyncio
import threading
import tempfile
from pathlib import Path
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env for local development (inline to avoid re-importing streamlit_app)
def _load_env():
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

_load_env()

st.set_page_config(page_title="New Audit", page_icon="\U0001f680", layout="wide")

# ---------------------------------------------------------------------------
# Phase-to-progress mapping
# ---------------------------------------------------------------------------

PHASE_PROGRESS = {
    "Extracting Logos": 0.05,
    "Website Crawling": 0.10,
    "Deep Research": 0.20,
    "Primary Analysis": 0.45,
    "Secondary Analysis": 0.60,
    "Screenshots": 0.70,
    "Competitor Analysis": 0.80,
    "Quality Review": 0.85,
    "Synthesis": 0.90,
    "Report Generation": 0.95,
    "Complete": 1.0,
}

# ---------------------------------------------------------------------------
# Section A: Configuration form
# ---------------------------------------------------------------------------

st.header("New Website Audit")

with st.form("audit_config"):
    col1, col2 = st.columns(2)

    with col1:
        company_name = st.text_input("Company Name", placeholder="Acme Corp")
        company_website = st.text_input("Website URL", placeholder="https://acme.com")
        industry = st.selectbox(
            "Industry",
            [
                "B2B SaaS",
                "Healthcare",
                "Fintech",
                "E-commerce",
                "Education",
                "Manufacturing",
                "Professional Services",
                "Other",
            ],
        )

    with col2:
        competitors = st.text_area(
            "Competitors (comma-separated)",
            placeholder="competitor1.com, competitor2.com",
        )
        max_pages = st.slider("Max Pages to Crawl", 5, 50, 20)
        analyst_name = st.text_input("Analyst Name", value="Agentic Auditor")

    submitted = st.form_submit_button("Start Audit", type="primary")

# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def _validate_inputs(name: str, url: str) -> str | None:
    """Return an error message string, or None if valid."""
    if not name.strip():
        return "Company Name is required."
    if not url.strip():
        return "Website URL is required."
    if not (url.startswith("http://") or url.startswith("https://")):
        return "Website URL must start with http:// or https://"
    return None


# ---------------------------------------------------------------------------
# Section B: Audit execution with progress
# ---------------------------------------------------------------------------


def _run_audit(config: dict, max_pages: int, progress_queue: queue.Queue):
    """Run the audit pipeline in a background thread."""
    try:
        from audit import setup_context_from_config, extract_logos
        from orchestrator.orchestrator import Orchestrator
        from utils.llm_client import LLMClient

        def progress_callback(phase, status, detail=""):
            progress_queue.put({"phase": phase, "status": status, "detail": detail})

        # Setup context
        progress_queue.put(
            {"phase": "Extracting Logos", "status": "started", "detail": "Building context..."}
        )
        context = setup_context_from_config(config, max_pages)

        # Skip screenshot capture when Playwright is unavailable
        skip_screenshots = False
        try:
            import playwright  # noqa: F401
        except ImportError:
            skip_screenshots = True

        # Extract logos (may fail gracefully)
        try:
            extract_logos(context)
        except Exception:
            pass  # Logos are nice-to-have, not critical

        progress_queue.put(
            {"phase": "Extracting Logos", "status": "completed", "detail": "Context ready"}
        )

        llm_client = LLMClient()
        orchestrator = Orchestrator(
            context, llm_client, verbose=False, progress_callback=progress_callback
        )

        # Run async audit in a fresh event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(orchestrator.run_audit())
        finally:
            loop.close()

        # Generate HTML report
        progress_queue.put(
            {"phase": "Report Generation", "status": "started", "detail": "Generating HTML report..."}
        )
        from utils.report import generate_html_report

        safe_name = "".join(
            c if c.isalnum() or c in "-_" else "-" for c in context.company_name
        )
        audit_date_str = context.audit_date.replace("/", "-")
        output_dir = PROJECT_ROOT / "clients" / safe_name / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{safe_name}-audit-{audit_date_str}.html"
        report_path = generate_html_report(report, str(output_path), context=context)

        with open(report_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        progress_queue.put(
            {
                "phase": "Complete",
                "status": "completed",
                "detail": "Audit finished!",
                "report": report,
                "context": context,
                "html_content": html_content,
                "report_path": report_path,
            }
        )

    except Exception as e:
        progress_queue.put({"phase": "Error", "status": "failed", "detail": str(e)})


# Handle form submission
if submitted:
    error = _validate_inputs(company_name, company_website)
    if error:
        st.error(error)
    else:
        config = {
            "company_name": company_name.strip(),
            "company_website": company_website.strip().rstrip("/"),
            "industry": industry,
            "competitors": competitors.strip(),
            "analyst_name": analyst_name.strip(),
            "analyst_company": "Bhavsar Growth Consulting",
            "analyst_website": "https://growth.llc",
            "audit_date": datetime.now().strftime("%m-%d-%Y"),
        }

        # Reset any previous audit state
        for key in [
            "audit_report",
            "audit_context",
            "audit_complete",
            "audit_running",
            "audit_error",
            "audit_html",
            "audit_report_path",
        ]:
            st.session_state.pop(key, None)

        st.session_state["audit_config"] = config
        st.session_state["audit_max_pages"] = max_pages
        st.session_state["audit_running"] = True

# ---------------------------------------------------------------------------
# Progress polling (runs when audit is active)
# ---------------------------------------------------------------------------

if st.session_state.get("audit_running") and not st.session_state.get("audit_complete"):
    config = st.session_state.get("audit_config", {})
    max_pg = st.session_state.get("audit_max_pages", 20)

    # Detect Playwright
    try:
        import playwright  # noqa: F401
    except ImportError:
        st.info("Screenshots disabled (Playwright not available in this environment).")

    progress_bar = st.progress(0, text="Initializing audit...")
    status_text = st.empty()

    pq = queue.Queue()

    thread = threading.Thread(target=_run_audit, args=(config, max_pg, pq), daemon=True)
    thread.start()

    last_pct = 0.0
    while True:
        try:
            msg = pq.get(timeout=1.0)
        except queue.Empty:
            if not thread.is_alive():
                # Thread died without sending Complete or Error
                if not st.session_state.get("audit_complete"):
                    st.error("Audit thread terminated unexpectedly.")
                    st.session_state["audit_running"] = False
                break
            continue

        phase = msg.get("phase", "")
        detail = msg.get("detail", "")
        status = msg.get("status", "")

        pct = PHASE_PROGRESS.get(phase, last_pct)
        if pct > last_pct:
            last_pct = pct
        progress_bar.progress(min(last_pct, 1.0), text=f"{phase}: {detail}")
        status_text.caption(f"Status: {phase} -- {detail}")

        if status == "failed":
            st.session_state["audit_running"] = False
            st.session_state["audit_error"] = detail
            st.error(f"Audit failed: {detail}")
            break

        if phase == "Complete" and status == "completed":
            st.session_state["audit_report"] = msg.get("report")
            st.session_state["audit_context"] = msg.get("context")
            st.session_state["audit_html"] = msg.get("html_content", "")
            st.session_state["audit_report_path"] = msg.get("report_path", "")
            st.session_state["audit_complete"] = True
            st.session_state["audit_running"] = False
            progress_bar.progress(1.0, text="Audit complete!")
            break

    thread.join(timeout=5)

# ---------------------------------------------------------------------------
# Section C: Report display (persists across reruns via session_state)
# ---------------------------------------------------------------------------

if st.session_state.get("audit_complete"):
    report = st.session_state.get("audit_report")
    html_content = st.session_state.get("audit_html", "")

    if report is None:
        st.warning("Report data is unavailable. Please re-run the audit.")
    else:
        st.success(f"Audit Complete: {report.company_name}")

        # Overall metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Overall Score", f"{report.overall_percentage:.0f}%")
        col2.metric("Grade", report.overall_outcome.value)
        col3.metric("Recommendations", len(report.get_all_recommendations()))

        # Module scores
        st.subheader("Module Scores")
        num_modules = len(report.modules)
        cols_per_row = 4
        for row_start in range(0, num_modules, cols_per_row):
            cols = st.columns(cols_per_row)
            for i, module in enumerate(report.modules[row_start : row_start + cols_per_row]):
                with cols[i]:
                    weight_str = f" ({module.weight}x)" if module.weight > 1 else ""
                    st.metric(f"{module.name}{weight_str}", f"{module.percentage:.0f}%")

        # Strategic friction point
        friction = getattr(report, "strategic_friction", None)
        if friction:
            st.subheader("Strategic Friction Point")
            st.warning(f"**{friction.title}**: {friction.description}")
            fc1, fc2 = st.columns(2)
            fc1.markdown(f"**Primary Symptom:** {friction.primary_symptom}")
            fc2.markdown(f"**Business Impact:** {friction.business_impact}")

        # Quick wins
        quick_wins = report.get_quick_wins(3)
        if quick_wins:
            st.subheader("Top Quick Wins")
            for i, win in enumerate(quick_wins, 1):
                st.markdown(f"**{i}.** {win.recommendation}")

        # Full HTML report
        if html_content:
            st.subheader("Full Report")
            components.html(html_content, height=800, scrolling=True)

            st.download_button(
                "Download HTML Report",
                html_content,
                file_name=f"{report.company_name}_audit.html",
                mime="text/html",
            )

        # Reset button
        if st.button("Run Another Audit"):
            for key in [
                "audit_report",
                "audit_context",
                "audit_complete",
                "audit_running",
                "audit_error",
                "audit_html",
                "audit_report_path",
                "audit_config",
                "audit_max_pages",
            ]:
                st.session_state.pop(key, None)
            st.rerun()

# Show error state if audit failed without results
if st.session_state.get("audit_error") and not st.session_state.get("audit_complete"):
    st.error(f"Last audit failed: {st.session_state['audit_error']}")
    if st.button("Clear Error and Try Again"):
        for key in [
            "audit_report",
            "audit_context",
            "audit_complete",
            "audit_running",
            "audit_error",
            "audit_html",
            "audit_report_path",
            "audit_config",
            "audit_max_pages",
        ]:
            st.session_state.pop(key, None)
        st.rerun()
