import streamlit as st

from utils.auth import require_role
from utils.ui import page_header


def render():
    require_role("hospital_manager")

    page_header(
        "Hospital Dashboard",
        "Inventory, production, kit usage and equipment monitoring",
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Available Kits", "—")
    col2.metric("Pending Receipt", "—")
    col3.metric("Open Kit Issues", "—")
    col4.metric("Expiry Alerts", "—")

    st.info(
        "Hospital operational tools will be added next."
    )
