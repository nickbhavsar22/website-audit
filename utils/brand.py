"""
Shared brand styles for the Streamlit app.
Inject via inject_brand_css() at the top of each page.
"""

import streamlit as st

BRAND_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* Global typography */
html, body, [class*="css"] {
    font-family: 'Inter', 'Roboto', sans-serif;
    font-weight: 400;
}

/* Headers */
h1, h2, h3, h4, h5, h6,
[data-testid="stHeadingWithActionElements"] {
    font-family: 'Inter', 'Roboto', sans-serif !important;
    font-weight: 700 !important;
    color: #0A0A0A !important;
}

/* Dark sidebar */
[data-testid="stSidebar"] {
    background-color: #0A0A0A !important;
}

[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}

[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label {
    color: #FFFFFF !important;
}

[data-testid="stSidebar"] hr {
    border-color: #708090 !important;
}

/* Sidebar status elements */
[data-testid="stSidebar"] [data-testid="stAlertContainer"] {
    background-color: #1C1C1C !important;
    border: 1px solid #708090 !important;
}

/* Primary buttons */
.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
    background-color: #0A0A0A !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 12px 24px !important;
    font-family: 'Inter', 'Roboto', sans-serif !important;
    font-weight: 600 !important;
}

.stButton > button[kind="primary"]:hover,
.stFormSubmitButton > button[kind="primary"]:hover {
    background-color: #1C1C1C !important;
    color: #FFFFFF !important;
}

/* Secondary buttons */
.stButton > button:not([kind="primary"]),
.stDownloadButton > button {
    background-color: #FFFFFF !important;
    color: #0A0A0A !important;
    border: 1px solid #708090 !important;
    border-radius: 4px !important;
    padding: 12px 24px !important;
    font-family: 'Inter', 'Roboto', sans-serif !important;
    font-weight: 500 !important;
}

.stButton > button:not([kind="primary"]):hover,
.stDownloadButton > button:hover {
    background-color: #F0F2F6 !important;
    border-color: #0A0A0A !important;
}

/* Metrics */
[data-testid="stMetric"] {
    background-color: #F0F2F6;
    border-radius: 4px;
    padding: 16px;
}

[data-testid="stMetricValue"] {
    font-family: 'Inter', 'Roboto', sans-serif !important;
    font-weight: 700 !important;
    color: #0A0A0A !important;
}

[data-testid="stMetricLabel"] {
    color: #708090 !important;
    font-weight: 500 !important;
}

/* Progress bar */
.stProgress > div > div > div > div {
    background-color: #0A0A0A !important;
}

/* Form inputs */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    border-radius: 4px !important;
    border: 1px solid #708090 !important;
    font-family: 'Inter', 'Roboto', sans-serif !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #0A0A0A !important;
    box-shadow: 0 0 0 1px #0A0A0A !important;
}

/* Expanders */
.streamlit-expanderHeader {
    font-family: 'Inter', 'Roboto', sans-serif !important;
    font-weight: 600 !important;
}
</style>
"""


def inject_brand_css():
    """Inject brand CSS into the current Streamlit page."""
    st.markdown(BRAND_CSS, unsafe_allow_html=True)
