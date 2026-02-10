"""
View Reports page -- browse previously generated audit reports.
"""

import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(page_title="View Reports", page_icon="\U0001f4ca", layout="wide")

st.header("Past Audit Reports")

clients_dir = PROJECT_ROOT / "clients"

if not clients_dir.exists():
    st.info("No client data found. Run an audit first from the **New Audit** page.")
    st.stop()

clients = sorted([d.name for d in clients_dir.iterdir() if d.is_dir()])

if not clients:
    st.info("No clients found. Run an audit first from the **New Audit** page.")
    st.stop()

selected_client = st.selectbox("Select Client", clients)

if selected_client:
    output_dir = clients_dir / selected_client / "output"

    if not output_dir.exists():
        st.info(f"No output directory for **{selected_client}**.")
        st.stop()

    reports = sorted(output_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not reports:
        st.info(f"No reports found for **{selected_client}**.")
        st.stop()

    selected_report = st.selectbox(
        "Select Report",
        [r.name for r in reports],
        help="Reports are listed most-recent first.",
    )

    if selected_report:
        report_path = output_dir / selected_report

        try:
            html_content = report_path.read_text(encoding="utf-8")
        except Exception as e:
            st.error(f"Could not read report: {e}")
            st.stop()

        st.divider()

        # Report metadata
        col1, col2 = st.columns(2)
        col1.markdown(f"**Client:** {selected_client}")
        stat = report_path.stat()
        from datetime import datetime

        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        col2.markdown(f"**Last Modified:** {modified}")

        # Inline HTML report
        components.html(html_content, height=800, scrolling=True)

        st.download_button(
            "Download Report",
            html_content,
            file_name=selected_report,
            mime="text/html",
        )
