import streamlit as st

from utils.auth import require_role
from utils.ui import page_header


def render():
    require_role("warehouse_manager")

    page_header(
        "Warehouse Dashboard",
        "Inventory, transfers, expiry and component issues",
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Available Kits", "—")
    col2.metric("Pending Transfers", "—")
    col3.metric("Open Issues", "—")
    col4.metric("Expiry Alerts", "—")

    st.info(
        "Warehouse inventory tools will be added next."
    )
