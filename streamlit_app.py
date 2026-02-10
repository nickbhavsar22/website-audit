"""
Website Audit Tool - Streamlit Application
Main entry point for the Streamlit web interface.
"""

import os
import sys
from pathlib import Path

import streamlit as st

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Load .env for local development (reused pattern from audit.py)
# ---------------------------------------------------------------------------

def load_env_file():
    """Load environment variables from .env file."""
    env_paths = [
        PROJECT_ROOT / ".env",
        Path.cwd() / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ[key.strip()] = value.strip()
            return True
    return False


load_env_file()

# Also load Streamlit Cloud secrets into os.environ so the entire app can use them
try:
    for key in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GAMMA_API_KEY", "LLM_PROVIDER"):
        if key not in os.environ:
            val = st.secrets.get(key)
            if val:
                os.environ[key] = val
except Exception:
    pass  # st.secrets unavailable (local dev without secrets.toml)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Website Audit Tool",
    page_icon="\U0001f50d",  # magnifying glass
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("Bhavsar Growth Consulting")
    st.caption("B2B SaaS Website Audit Tool")
    st.divider()

    # LLM status — check both os.environ and st.secrets (Streamlit Cloud)
    def _get_secret(key, default=None):
        val = os.environ.get(key)
        if not val:
            try:
                val = st.secrets.get(key)
            except Exception:
                pass
        return val or default

    provider = _get_secret("LLM_PROVIDER", "anthropic").lower()
    if provider == "gemini":
        api_key_available = bool(_get_secret("GEMINI_API_KEY"))
        provider_label = "Gemini"
    else:
        api_key_available = bool(_get_secret("ANTHROPIC_API_KEY"))
        provider_label = "Anthropic"

    if api_key_available:
        st.success(f"LLM: {provider_label} connected", icon="\u2705")
    else:
        st.error(f"LLM: {provider_label} key missing", icon="\u274c")

    # Screenshot availability
    playwright_available = False
    try:
        import playwright  # noqa: F401
        playwright_available = True
    except ImportError:
        pass

    if playwright_available:
        st.info("Screenshots: available", icon="\U0001f4f7")
    else:
        st.warning("Screenshots: unavailable (Playwright not installed)", icon="\U0001f6ab")

# ---------------------------------------------------------------------------
# Main content - Landing page
# ---------------------------------------------------------------------------

st.title("Website Audit Tool")
st.markdown(
    "Run comprehensive marketing audits for B2B SaaS websites. "
    "The agentic system crawls, analyzes, and scores your web presence across "
    "positioning, SEO, conversion, content, trust, and more."
)

st.divider()

# Quick stats
clients_dir = PROJECT_ROOT / "clients"
client_count = 0
report_count = 0

if clients_dir.exists():
    for d in clients_dir.iterdir():
        if d.is_dir():
            config_path = d / "config.txt"
            if config_path.exists():
                client_count += 1
            output_dir = d / "output"
            if output_dir.exists():
                report_count += len(list(output_dir.glob("*.html")))

col1, col2, col3 = st.columns(3)
col1.metric("Clients Configured", client_count)
col2.metric("Past Reports", report_count)
col3.metric("Audit Modules", 15)

st.divider()

# Quick-start guide
st.subheader("Getting Started")

st.markdown(
    """
**1. New Audit** -- Go to the *New Audit* page to configure and run a website audit.
Fill in the company details, set your crawl parameters, and click **Start Audit**.
The tool will crawl the site, run 15 specialist agents in parallel, and generate a
scored HTML report you can download.

**2. View Reports** -- Browse previously generated audit reports organized by client.
View the full HTML report inline or download it for sharing.

**3. Client Manager** -- Create and manage client configuration files so you can
re-run audits quickly without re-entering details.
"""
)
