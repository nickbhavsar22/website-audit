"""
Client Manager page -- create and manage client configuration files.
"""

import sys
from pathlib import Path
from datetime import datetime

import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(page_title="Client Manager", page_icon="\U0001f4c1", layout="wide")

from utils.brand import inject_brand_css
inject_brand_css()

from utils.auth import check_password
if not check_password():
    st.stop()

st.header("Client Manager")

clients_dir = PROJECT_ROOT / "clients"
clients_dir.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Helper: read config.txt into a dict
# ---------------------------------------------------------------------------


def _read_config(config_path: Path) -> dict:
    """Parse a config.txt file into a dict."""
    config = {}
    if not config_path.exists():
        return config
    for line in config_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("`"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            config[key.strip()] = value.strip()
    return config


def _write_config(config_path: Path, config: dict):
    """Write a dict to a config.txt file."""
    lines = []
    # Write main fields in a consistent order
    field_order = [
        "company_website",
        "company_name",
        "audit_date",
        "industry",
        "analyst_name",
        "analyst_company",
        "analyst_website",
        "competitors",
        "max_pages",
    ]
    for key in field_order:
        if key in config and config[key]:
            lines.append(f"{key}={config[key]}")
    # Write any extra keys not in the standard order
    for key, value in config.items():
        if key not in field_order and value:
            lines.append(f"{key}={value}")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Section 1: Create new client
# ---------------------------------------------------------------------------

st.subheader("Create New Client")

with st.form("new_client_form"):
    nc1, nc2 = st.columns(2)

    with nc1:
        new_name = st.text_input("Company Name", placeholder="Acme Corp")
        new_website = st.text_input("Website URL", placeholder="https://acme.com")
        new_industry = st.selectbox(
            "Industry",
            [
                "B2B SaaS",
                "Healthcare",
                "Fintech",
                "E-commerce",
                "Education",
                "Manufacturing",
                "Professional Services",
                "Push-to-Talk Technology",
                "Other",
            ],
        )

    with nc2:
        new_competitors = st.text_area(
            "Competitors (comma-separated)", placeholder="competitor1.com, competitor2.com"
        )
        new_analyst = st.text_input("Analyst Name", value="Nick Bhavsar")
        new_max_pages = st.slider("Default Max Pages", 5, 50, 20)

    create_submitted = st.form_submit_button("Create Client", type="primary")

if create_submitted:
    if not new_name.strip():
        st.error("Company Name is required.")
    elif not new_website.strip():
        st.error("Website URL is required.")
    elif not (new_website.startswith("http://") or new_website.startswith("https://")):
        st.error("Website URL must start with http:// or https://")
    else:
        # Build a filesystem-safe folder name
        folder_name = "".join(
            c if c.isalnum() or c in "-_" else "-" for c in new_name.strip()
        ).strip("-")
        client_path = clients_dir / folder_name
        config_path = client_path / "config.txt"

        if config_path.exists():
            st.warning(
                f"A client folder **{folder_name}** already exists. "
                "Edit it below or choose a different name."
            )
        else:
            config = {
                "company_name": new_name.strip(),
                "company_website": new_website.strip().rstrip("/"),
                "audit_date": datetime.now().strftime("%m-%d-%Y"),
                "industry": new_industry,
                "analyst_name": new_analyst.strip(),
                "analyst_company": "Bhavsar Growth Consulting",
                "analyst_website": "https://growth.llc",
                "competitors": new_competitors.strip(),
                "max_pages": str(new_max_pages),
            }
            _write_config(config_path, config)
            # Create output directory
            (client_path / "output").mkdir(parents=True, exist_ok=True)
            st.success(f"Client **{new_name.strip()}** created successfully!")
            st.rerun()

# ---------------------------------------------------------------------------
# Section 2: Existing clients
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Existing Clients")

existing_clients = sorted([d.name for d in clients_dir.iterdir() if d.is_dir()])

if not existing_clients:
    st.info("No clients yet. Create one above.")
    st.stop()

for client_name in existing_clients:
    client_path = clients_dir / client_name
    config_path = client_path / "config.txt"
    config = _read_config(config_path)

    display_name = config.get("company_name", client_name)
    website = config.get("company_website", "")
    industry = config.get("industry", "")

    with st.expander(f"{display_name}  --  {website}", expanded=False):
        if not config:
            st.warning("No config.txt found for this client.")
            continue

        # Show config as editable form
        with st.form(f"edit_{client_name}"):
            ec1, ec2 = st.columns(2)

            with ec1:
                ed_name = st.text_input("Company Name", value=config.get("company_name", ""), key=f"name_{client_name}")
                ed_website = st.text_input("Website URL", value=config.get("company_website", ""), key=f"web_{client_name}")
                ed_industry = st.text_input("Industry", value=config.get("industry", ""), key=f"ind_{client_name}")

            with ec2:
                ed_competitors = st.text_area(
                    "Competitors",
                    value=config.get("competitors", ""),
                    key=f"comp_{client_name}",
                )
                ed_analyst = st.text_input("Analyst Name", value=config.get("analyst_name", ""), key=f"analyst_{client_name}")
                ed_max_pages = st.text_input("Max Pages", value=config.get("max_pages", "20"), key=f"mp_{client_name}")

            save_clicked = st.form_submit_button("Save Changes")

        if save_clicked:
            updated = {
                "company_name": ed_name.strip(),
                "company_website": ed_website.strip().rstrip("/"),
                "audit_date": config.get("audit_date", datetime.now().strftime("%m-%d-%Y")),
                "industry": ed_industry.strip(),
                "analyst_name": ed_analyst.strip(),
                "analyst_company": config.get("analyst_company", "Bhavsar Growth Consulting"),
                "analyst_website": config.get("analyst_website", "https://growth.llc"),
                "competitors": ed_competitors.strip(),
                "max_pages": ed_max_pages.strip(),
            }
            _write_config(config_path, updated)
            st.success(f"Saved changes for **{ed_name.strip()}**.")
            st.rerun()

        # Report count
        output_dir = client_path / "output"
        if output_dir.exists():
            report_files = list(output_dir.glob("*.html"))
            st.caption(f"{len(report_files)} report(s) in output directory.")
        else:
            st.caption("No output directory yet.")
