"""
Simple password authentication for Streamlit app.
Add APP_PASSWORD to your Streamlit Cloud secrets or .env file.
"""

import os
import streamlit as st


def check_password() -> bool:
    """Returns True if the user has entered the correct password.

    The password is read from st.secrets["APP_PASSWORD"] or
    os.environ["APP_PASSWORD"]. If neither is set, authentication
    is skipped (local dev without a password configured).
    """
    # Get the expected password
    expected = None
    try:
        expected = st.secrets.get("APP_PASSWORD")
    except Exception:
        pass
    if not expected:
        expected = os.environ.get("APP_PASSWORD")
    if not expected:
        # No password configured -- allow access (local dev)
        return True

    # Already authenticated this session
    if st.session_state.get("authenticated"):
        return True

    # Show login form
    st.markdown(
        "<h2 style='text-align:center; margin-top: 4rem;'>Bhavsar Growth Consulting</h2>"
        "<p style='text-align:center; color: #708090;'>Website Audit Tool</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        password = st.text_input("Enter password to continue", type="password", key="login_pw")
        if st.button("Log in", type="primary", use_container_width=True):
            if password == expected:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")

    return False
