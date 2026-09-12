import streamlit as st

from utils.auth import require_role
from utils.ui import page_header


def render():
    require_role("admin")

    page_header(
        "Admin Dashboard",
        "System-wide operational overview",
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Active Kits", "—")
    col2.metric("Open Issues", "—")
    col3.metric("Expiry Alerts", "—")
    col4.metric("Pending Transfers", "—")

    st.info(
        "Admin modules will be added in the next development steps."
    )
