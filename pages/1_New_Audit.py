"""
New Audit page -- configure and run a website audit.
"""

import os
import sys
import time
import queue
import asyncio
import threading
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

# Also bridge Streamlit Cloud secrets into os.environ
try:
    for _k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GAMMA_API_KEY", "LLM_PROVIDER"):
        if _k not in os.environ:
            _v = st.secrets.get(_k)
            if _v:
                os.environ[_k] = _v
except Exception:
    pass

st.set_page_config(page_title="New Audit", page_icon="\U0001f680", layout="wide")

from utils.brand import inject_brand_css
inject_brand_css()

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

st.header("Launch a New Audit")

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


def _validate_inputs(name: str, url: str):
    """Return an error message string, or None if valid."""
    if not name.strip():
        return "Company Name is required."
    if not url.strip():
        return "Website URL is required."
    if not (url.startswith("http://") or url.startswith("https://")):
        return "Website URL must start with http:// or https://"
    return None


# ---------------------------------------------------------------------------
# Audit thread function -- serializes results for session_state safety
# ---------------------------------------------------------------------------


def _run_audit(config: dict, max_pages: int, progress_queue: queue.Queue):
    """Run the audit pipeline in a background thread."""
    try:
        from audit import setup_context_from_config, extract_logos
        from orchestrator.orchestrator import Orchestrator
        from utils.llm_client import LLMClient

        def progress_callback(phase, status, detail=""):
            progress_queue.put({"phase": phase, "status": status, "detail": detail})

        progress_queue.put(
            {"phase": "Extracting Logos", "status": "started", "detail": "Building context..."}
        )
        context = setup_context_from_config(config, max_pages)

        try:
            extract_logos(context)
        except Exception:
            pass

        progress_queue.put(
            {"phase": "Extracting Logos", "status": "completed", "detail": "Context ready"}
        )

        llm_client = LLMClient()
        orchestrator = Orchestrator(
            context, llm_client, verbose=False, progress_callback=progress_callback
        )

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

        # --- Serialize into plain dicts/strings that survive session_state ---
        modules = []
        for m in report.modules:
            modules.append({
                "name": m.name,
                "percentage": round(m.percentage, 0),
                "weight": m.weight,
                "outcome": m.outcome.value if hasattr(m.outcome, "value") else str(m.outcome),
            })

        quick_wins = []
        for w in report.get_quick_wins(3):
            quick_wins.append(w.recommendation)

        friction_data = None
        friction = getattr(report, "strategic_friction", None)
        if friction:
            friction_data = {
                "title": friction.title,
                "description": friction.description,
                "primary_symptom": friction.primary_symptom,
                "business_impact": friction.business_impact,
            }

        result_data = {
            "company_name": report.company_name,
            "overall_percentage": round(report.overall_percentage, 1),
            "overall_outcome": report.overall_outcome.value if hasattr(report.overall_outcome, "value") else str(report.overall_outcome),
            "recommendation_count": len(report.get_all_recommendations()),
            "modules": modules,
            "quick_wins": quick_wins,
            "friction": friction_data,
            "html_content": html_content,
        }

        progress_queue.put({
            "phase": "Complete",
            "status": "completed",
            "detail": "Audit finished!",
            "result": result_data,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        progress_queue.put({"phase": "Error", "status": "failed", "detail": str(e)})


# ---------------------------------------------------------------------------
# Handle form submission -- start audit thread ONCE
# ---------------------------------------------------------------------------

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

        # Reset previous state
        for key in list(st.session_state.keys()):
            if key.startswith("audit_"):
                st.session_state.pop(key, None)

        # Create queue and thread, store in session_state so reruns reuse them
        pq = queue.Queue()
        t = threading.Thread(target=_run_audit, args=(config, max_pages, pq), daemon=True)
        t.start()

        st.session_state["audit_queue"] = pq
        st.session_state["audit_thread"] = t
        st.session_state["audit_running"] = True
        st.session_state["audit_last_pct"] = 0.0
        st.session_state["audit_last_phase"] = "Initializing"
        st.rerun()

# ---------------------------------------------------------------------------
# Progress polling (non-blocking, rerun-safe)
# ---------------------------------------------------------------------------

if st.session_state.get("audit_running") and not st.session_state.get("audit_complete"):
    pq = st.session_state.get("audit_queue")
    thread = st.session_state.get("audit_thread")

    if pq is None or thread is None:
        st.error("Audit state was lost. Please start a new audit.")
        st.session_state["audit_running"] = False
        st.stop()

    # Detect Playwright
    try:
        import playwright  # noqa: F401
    except ImportError:
        st.info("Screenshots disabled (Playwright not available).")

    last_pct = st.session_state.get("audit_last_pct", 0.0)
    last_phase = st.session_state.get("audit_last_phase", "Initializing")

    # Drain all available messages (non-blocking)
    done = False
    while True:
        try:
            msg = pq.get_nowait()
        except queue.Empty:
            break

        phase = msg.get("phase", "")
        detail = msg.get("detail", "")
        status = msg.get("status", "")

        pct = PHASE_PROGRESS.get(phase, last_pct)
        if pct > last_pct:
            last_pct = pct
        last_phase = phase

        if status == "failed":
            st.session_state["audit_running"] = False
            st.session_state["audit_error"] = detail
            st.rerun()

        if phase == "Complete" and status == "completed":
            st.session_state["audit_result"] = msg.get("result", {})
            st.session_state["audit_complete"] = True
            st.session_state["audit_running"] = False
            done = True
            break

    st.session_state["audit_last_pct"] = last_pct
    st.session_state["audit_last_phase"] = last_phase

    if done:
        st.rerun()

    # Show progress
    st.progress(min(last_pct, 0.99), text=f"{last_phase}...")
    st.caption("Agents deployed. Analyzing positioning, SEO, conversion, trust, and competitive landscape.")

    # If thread still alive, wait and rerun to poll again
    if thread.is_alive():
        time.sleep(3)
        st.rerun()
    else:
        if not st.session_state.get("audit_complete"):
            st.error("Audit ended unexpectedly. Check the logs.")
            st.session_state["audit_running"] = False

# ---------------------------------------------------------------------------
# Section C: Report display (uses simple serializable dicts)
# ---------------------------------------------------------------------------

if st.session_state.get("audit_complete"):
    result = st.session_state.get("audit_result", {})

    if not result:
        st.warning("Report data is unavailable. Please re-run the audit.")
    else:
        st.success(f"Audit Complete --- {result['company_name']}")

        # Overall metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Overall Score", f"{result['overall_percentage']:.0f}%")
        col2.metric("Outcome", result["overall_outcome"])
        col3.metric("Recommendations", result["recommendation_count"])

        # Module scores
        st.subheader("Module Scores")
        modules = result.get("modules", [])
        cols_per_row = 4
        for row_start in range(0, len(modules), cols_per_row):
            cols = st.columns(cols_per_row)
            for i, mod in enumerate(modules[row_start : row_start + cols_per_row]):
                with cols[i]:
                    weight_str = f" ({mod['weight']}x)" if mod["weight"] > 1 else ""
                    st.metric(f"{mod['name']}{weight_str}", f"{mod['percentage']:.0f}%")

        # Strategic friction point
        friction = result.get("friction")
        if friction:
            st.subheader("Strategic Friction Point")
            st.warning(f"**{friction['title']}**: {friction['description']}")
            fc1, fc2 = st.columns(2)
            fc1.markdown(f"**Primary Symptom:** {friction['primary_symptom']}")
            fc2.markdown(f"**Business Impact:** {friction['business_impact']}")

        # Quick wins
        wins = result.get("quick_wins", [])
        if wins:
            st.subheader("Top Quick Wins")
            for i, w in enumerate(wins, 1):
                st.markdown(f"**{i}.** {w}")

        # Full HTML report
        html_content = result.get("html_content", "")
        if html_content:
            st.subheader("Full Report")
            components.html(html_content, height=800, scrolling=True)

            st.download_button(
                "Download HTML Report",
                html_content,
                file_name=f"{result['company_name']}_audit.html",
                mime="text/html",
            )

        # Reset button
        if st.button("Run Another Audit"):
            for key in list(st.session_state.keys()):
                if key.startswith("audit_"):
                    st.session_state.pop(key, None)
            st.rerun()

# Show error state
if st.session_state.get("audit_error") and not st.session_state.get("audit_complete"):
    st.error(f"Last audit failed: {st.session_state['audit_error']}")
    if st.button("Clear Error and Try Again"):
        for key in list(st.session_state.keys()):
            if key.startswith("audit_"):
                st.session_state.pop(key, None)
        st.rerun()
