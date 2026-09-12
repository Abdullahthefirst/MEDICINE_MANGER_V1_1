import streamlit as st
import pandas as pd
from datetime import date

from utils.auth import (
    require_role,
    get_authenticated_client,
    get_site_id,
)
from utils.errors import friendly_error
from utils.ui import page_header


def fetch_data(table, columns="*"):
    supabase = get_authenticated_client()

    response = (
        supabase
        .table(table)
        .select(columns)
        .execute()
    )

    return response.data or []


def show_dataframe(data, empty_message="No records found."):
    if not data:
        st.info(empty_message)
        return

    st.dataframe(
        pd.DataFrame(data),
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# OVERVIEW
# =========================================================

def render_overview():
    page_header(
        "Warehouse Dashboard",
        "Inventory, transfers, component issues and expiry monitoring",
    )

    try:
        inventory = fetch_data("warehouse_inventory")
        transfers = fetch_data("pending_transfers")
        issues = fetch_data("open_kit_issues")
        expiry = fetch_data("kit_expiry_alerts")

    except Exception as exc:
        st.error(f"Unable to load dashboard: {exc}")
        return

    warehouse_site_id = get_site_id()

    inventory_count = len(inventory)

    transfer_count = len(
        {
            row.get("transfer_id")
            for row in transfers
            if row.get("source_site_id") == warehouse_site_id
        }
    )

    issue_count = len(
        {
            row.get("issue_id")
            for row in issues
        }
    )

    expiry_count = len(
        [
            row for row in expiry
            if row.get("site_id") == warehouse_site_id
        ]
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Available Kits", inventory_count)
    c2.metric("Pending Transfers", transfer_count)
    c3.metric("Open Kit Issues", issue_count)
    c4.metric("Expiry Alerts", expiry_count)

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Open Kit Issues")

        if issues:
            df = pd.DataFrame(issues)

            wanted = [
                "issue_id",
                "hospital",
                "kit_id",
                "kit_type",
                "component_name",
                "runs_affected",
                "event_date",
            ]

            cols = [
                col for col in wanted
                if col in df.columns
            ]

            st.dataframe(
                df[cols].head(10),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.success("No open kit issues.")

    with right:
        st.subheader("Warehouse Expiry Alerts")

        filtered = [
            row for row in expiry
            if row.get("site_id") == warehouse_site_id
        ]

        if filtered:
            df = pd.DataFrame(filtered)

            wanted = [
                "kit_id",
                "kit_type",
                "expiry_date",
                "days_to_expiry",
                "expiry_category",
            ]

            cols = [
                col for col in wanted
                if col in df.columns
            ]

            st.dataframe(
                df[cols].head(10),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.success("No warehouse expiry alerts.")


# =========================================================
# ADD INVENTORY
# =========================================================

def render_add_inventory():
    page_header(
        "Add Inventory",
        "Create a physical kit from an inventory template",
    )

    try:
        templates = fetch_data(
            "inventory_templates",
            "id,name,inventory_type,standard_runs,"
            "standard_volume_ml,volume_per_run_ml,is_active",
        )

    except Exception as exc:
        st.error(f"Unable to load templates: {exc}")
        return

    templates = [
        row for row in templates
        if row.get("is_active")
    ]

    if not templates:
        st.warning("No active inventory templates found.")
        return

    template_lookup = {
        row["name"]: row
        for row in templates
    }

    with st.form("warehouse_add_inventory"):
        template_name = st.selectbox(
            "Kit / Inventory Type",
            list(template_lookup.keys()),
        )

        kit_id = st.text_input(
            "Unique Kit ID",
            placeholder="KIT-000482",
        )

        lot_number = st.text_input(
            "Lot Number",
        )

        origin = st.selectbox(
            "Origin",
            ["local", "international"],
        )

        received_date = st.date_input(
            "Received Date",
            value=date.today(),
        )

        expiry_date = st.date_input(
            "Expiry Date",
            value=date.today(),
        )

        notes = st.text_area(
            "Notes",
            placeholder="Optional",
        )

        submitted = st.form_submit_button(
            "Add Inventory",
            use_container_width=True,
        )

    if submitted:
        selected = template_lookup[template_name]

        if not kit_id.strip():
            st.error("Kit ID is required.")
            return

        try:
            supabase = get_authenticated_client()

            response = supabase.rpc(
                "add_inventory_from_template",
                {
                    "p_kit_id": kit_id.strip(),
                    "p_template_id": selected["id"],
                    "p_lot_number": lot_number.strip() or None,
                    "p_origin": origin,
                    "p_received_date": received_date.isoformat(),
                    "p_expiry_date": expiry_date.isoformat(),
                    "p_site_id": get_site_id(),
                },
            ).execute()

            st.success(
                f"{kit_id} added successfully."
            )

            st.rerun()

        except Exception as exc:
            st.error(
                friendly_error(exc)
            )


# =========================================================
# WAREHOUSE INVENTORY
# =========================================================

def render_inventory():
    page_header(
        "Warehouse Inventory",
        "Active kits currently available in your warehouse",
    )

    try:
        data = fetch_data("warehouse_inventory")

    except Exception as exc:
        st.error(f"Unable to load inventory: {exc}")
        return

    if not data:
        st.info("No warehouse inventory found.")
        return

    df = pd.DataFrame(data)

    c1, c2 = st.columns(2)

    kit_types = ["All"]

    if "kit_type" in df.columns:
        kit_types += sorted(
            df["kit_type"]
            .dropna()
            .unique()
            .tolist()
        )

    selected_type = c1.selectbox(
        "Kit Type",
        kit_types,
    )

    search = c2.text_input(
        "Search Kit ID",
        placeholder="KIT-000482",
    )

    filtered = df.copy()

    if selected_type != "All":
        filtered = filtered[
            filtered["kit_type"] == selected_type
        ]

    if search:
        filtered = filtered[
            filtered["kit_id"]
            .astype(str)
            .str.contains(
                search,
                case=False,
                na=False,
            )
        ]

    preferred = [
        "kit_id",
        "kit_type",
        "lot_number",
        "origin",
        "received_date",
        "expiry_date",
        "runs_used",
        "runs_remaining",
        "initial_volume_ml",
        "remaining_volume_ml",
    ]

    cols = [
        col for col in preferred
        if col in filtered.columns
    ]

    st.caption(
        f"{len(filtered)} active warehouse item(s)"
    )

    st.dataframe(
        filtered[cols],
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# TRANSFER KITS
# =========================================================

def render_transfer():
    page_header(
        "Transfer Kits",
        "Send warehouse inventory to a hospital",
    )

    try:
        inventory = fetch_data("warehouse_inventory")

        sites = fetch_data(
            "sites",
            "id,name,site_type",
        )

    except Exception as exc:
        st.error(f"Unable to load transfer data: {exc}")
        return

    hospitals = [
        row for row in sites
        if row.get("site_type") == "hospital"
    ]

    if not inventory:
        st.info(
            "No warehouse kits are currently available for transfer."
        )
        return

    if not hospitals:
        st.warning("No hospital sites are configured.")
        return

    hospital_lookup = {
        row["name"]: row["id"]
        for row in hospitals
    }

    kit_lookup = {
        f'{row["kit_id"]} — {row["kit_type"]}':
        row["kit_pk"]
        for row in inventory
    }

    with st.form("create_transfer_form"):
        destination_name = st.selectbox(
            "Destination Hospital",
            list(hospital_lookup.keys()),
        )

        selected_kits = st.multiselect(
            "Select Kit IDs",
            list(kit_lookup.keys()),
        )

        transfer_date = st.date_input(
            "Transfer Date",
            value=date.today(),
        )

        notes = st.text_area(
            "Notes",
            placeholder="Optional transfer notes",
        )

        submitted = st.form_submit_button(
            "Create Transfer",
            use_container_width=True,
        )

    if submitted:
        if not selected_kits:
            st.error(
                "Select at least one kit."
            )
            return

        kit_ids = [
            kit_lookup[item]
            for item in selected_kits
        ]

        try:
            supabase = get_authenticated_client()

            supabase.rpc(
                "create_inventory_transfer",
                {
                    "p_source_site_id": get_site_id(),
                    "p_destination_site_id":
                        hospital_lookup[destination_name],
                    "p_transfer_date":
                        transfer_date.isoformat(),
                    "p_kit_ids": kit_ids,
                    "p_notes": notes.strip() or None,
                },
            ).execute()

            st.success(
                f"Transfer created for "
                f"{len(kit_ids)} kit(s)."
            )

            st.rerun()

        except Exception as exc:
            st.error(
                f"Unable to create transfer: {exc}"
            )


# =========================================================
# TRANSFER HISTORY / PENDING
# =========================================================

def render_transfers():
    page_header(
        "Transfers",
        "Pending and partially received transfers",
    )

    try:
        transfers = fetch_data(
            "pending_transfers"
        )

    except Exception as exc:
        st.error(
            f"Unable to load transfers: {exc}"
        )
        return

    warehouse_id = get_site_id()

    transfers = [
        row for row in transfers
        if row.get("source_site_id") == warehouse_id
    ]

    if not transfers:
        st.success(
            "No pending transfers from this warehouse."
        )
        return

    df = pd.DataFrame(transfers)

    preferred = [
        "transfer_id",
        "transfer_date",
        "destination_site",
        "kit_id",
        "kit_type",
        "transfer_status",
        "received",
        "received_at",
    ]

    cols = [
        col for col in preferred
        if col in df.columns
    ]

    st.dataframe(
        df[cols],
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# KIT ISSUES
# =========================================================

def render_issues():
    page_header(
        "Kit Issues",
        "Resolve reported issues by sending replacement items",
    )

    try:
        issues = fetch_data("open_kit_issues")
    except Exception as exc:
        st.error(f"Unable to load issues: {exc}")
        return

    if not issues:
        st.success("No open issues.")
        return

    grouped = {}

    for row in issues:
        issue_id = row["issue_id"]

        if issue_id not in grouped:
            grouped[issue_id] = {
                "issue_id": issue_id,
                "kit_id": row.get("kit_id"),
                "kit_type": row.get("kit_type"),
                "hospital": row.get("hospital"),
                "event_date": row.get("event_date"),
                "runs_affected": row.get("runs_affected"),
                "description": row.get("description"),
                "components": [],
            }

        grouped[issue_id]["components"].append(row.get("component_name"))

    issue_lookup = {}

    for issue_id, issue in grouped.items():
        label = (
            f'Issue #{issue_id} — '
            f'{issue["kit_id"]} — '
            f'{issue["hospital"]}'
        )
        issue_lookup[label] = issue

    selected_label = st.selectbox(
        "Select Issue",
        list(issue_lookup.keys()),
    )

    issue = issue_lookup[selected_label]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Kit ID", issue["kit_id"])
    c2.metric("Kit Type", issue["kit_type"])
    c3.metric("Hospital", issue["hospital"])
    c4.metric("Affected Runs", issue["runs_affected"])

    st.write(f"**Reported Date:** {issue['event_date']}")

    if issue.get("description"):
        st.write(f"**Description:** {issue['description']}")

    st.subheader("Reported Components")
    components = [comp for comp in issue["components"] if comp]
    for comp in components:
        st.write(f"- {comp}")

    st.divider()
    st.subheader("Resolve Issue")
    st.caption(
        "Use this when the required replacement items have been sent to the hospital."
    )

    with st.form("send_issue_resolution"):
        resolution_date = st.date_input(
            "Items Sent Date",
            value=date.today(),
        )

        notes = st.text_area(
            "Resolution Notes",
            placeholder="Example: Replacement components dispatched to hospital.",
        )

        submitted = st.form_submit_button(
            "Set as Resolved by Sending Items",
            use_container_width=True,
        )

    if submitted:
        try:
            supabase = get_authenticated_client()
            supabase.rpc(
                "send_issue_replacement",
                {
                    "p_issue_id": issue["issue_id"],
                    "p_resolution_date": resolution_date.isoformat(),
                    "p_notes": notes.strip() or None,
                },
            ).execute()

            st.success(
                "Issue updated successfully. "
                "Replacement items have been marked as sent "
                "and are now awaiting hospital confirmation."
            )

            st.rerun()

        except Exception as exc:
            st.error(f"Unable to update issue: {exc}")


# =========================================================
# EXPIRY
# =========================================================

def render_expiry():
    page_header(
        "Expiry Alerts",
        "Warehouse kits and components approaching expiry",
    )

    warehouse_id = get_site_id()

    tab1, tab2 = st.tabs(
        [
            "Kits",
            "Components",
        ]
    )

    with tab1:
        try:
            alerts = fetch_data(
                "kit_expiry_alerts"
            )

            alerts = [
                row for row in alerts
                if row.get("site_id") == warehouse_id
            ]

        except Exception as exc:
            st.error(
                f"Unable to load kit expiry alerts: {exc}"
            )
            return

        if not alerts:
            st.success(
                "No warehouse kit expiry alerts."
            )

        else:
            df = pd.DataFrame(alerts)

            if "days_to_expiry" in df.columns:
                df = df.sort_values(
                    "days_to_expiry"
                )

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

            expired = [
                row for row in alerts
                if row.get("days_to_expiry", 999) <= 0
            ]

            if expired:
                st.divider()
                st.subheader("Expired Kits Requiring Action")
                st.caption(
                    "Any kit with 0 days or less to expiry is considered expired and can be marked expired."
                )

                kit_lookup = {
                    (
                        f'{row["kit_id"]} — '
                        f'{row.get("kit_type", "")} — '
                        f'{row.get("expiry_date", "")}'
                    ): row.get("kit_pk") or row.get("id")
                    for row in expired
                }

                with st.form("warehouse_expire_kit"):
                    selected = st.selectbox(
                        "Expired Kit",
                        list(kit_lookup.keys()),
                    )

                    reason = st.text_area(
                        "Reason / Notes",
                        placeholder="Optional expiry notes",
                    )

                    submitted = st.form_submit_button(
                        "Mark Kit as Expired",
                        use_container_width=True,
                    )

                if submitted:
                    try:
                        supabase = get_authenticated_client()

                        supabase.rpc(
                            "mark_kit_expired",
                            {
                                "p_kit_id": kit_lookup[selected],
                                "p_reason": reason.strip() or None,
                            },
                        ).execute()

                        st.success("Kit marked as expired.")
                        st.rerun()

                    except Exception as exc:
                        st.error(
                            f"Unable to mark kit expired: {exc}"
                        )

            else:
                st.info(
                    "These kits are approaching expiry, but none are at 0 days or less to expiry yet."
                )

    with tab2:
        try:
            alerts = fetch_data(
                "component_expiry_alerts"
            )

            alerts = [
                row for row in alerts
                if row.get("site_id") == warehouse_id
            ]

        except Exception as exc:
            st.error(
                f"Unable to load component expiry alerts: {exc}"
            )
            return

        if not alerts:
            st.success(
                "No warehouse component expiry alerts."
            )

        else:
            df = pd.DataFrame(alerts)

            if "days_to_expiry" in df.columns:
                df = df.sort_values(
                    "days_to_expiry"
                )

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

            expired = [
                row for row in alerts
                if row.get("days_to_expiry", 999) <= 0
            ]

            if expired:
                st.divider()
                st.subheader("Expired Components Requiring Action")

                component_lookup = {}

                for row in expired:
                    label = (
                        f'{row.get("kit_id", "")} — '
                        f'{row.get("component_name", "")}'
                    )

                    component_lookup[label] = row.get("kit_component_id")

                with st.form("warehouse_expire_component"):
                    selected = st.selectbox(
                        "Expired Component",
                        list(component_lookup.keys()),
                    )

                    reason = st.text_area(
                        "Reason / Notes",
                        placeholder="Optional",
                    )

                    submitted = st.form_submit_button(
                        "Mark Component as Expired",
                        use_container_width=True,
                    )

                if submitted:
                    try:
                        supabase = get_authenticated_client()

                        supabase.rpc(
                            "mark_component_expired",
                            {
                                "p_kit_component_id": component_lookup[selected],
                                "p_reason": reason.strip() or None,
                            },
                        ).execute()

                        st.success("Component marked as expired.")
                        st.rerun()

                    except Exception as exc:
                        st.error(
                            f"Unable to mark component expired: {exc}"
                        )

            else:
                st.info(
                    "These components are approaching expiry, but none are at 0 days or less to expiry yet."
                )

    with tab2:
        try:
            alerts = fetch_data(
                "component_expiry_alerts"
            )

            alerts = [
                row for row in alerts
                if row.get("site_id") == warehouse_id
            ]

        except Exception as exc:
            st.error(
                f"Unable to load component expiry alerts: {exc}"
            )
            alerts = []

        if alerts:
            df = pd.DataFrame(alerts)

            if "days_to_expiry" in df.columns:
                df = df.sort_values(
                    "days_to_expiry"
                )

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.success(
                "No warehouse component expiry alerts."
            )


# =========================================================
# MAIN ROUTER
# =========================================================

def render():
    require_role("warehouse_manager")

    with st.sidebar:
        st.markdown("### Warehouse")

        section = st.radio(
            "Navigation",
            [
                "Overview",
                "Add Inventory",
                "Warehouse Inventory",
                "Transfer Kits",
                "Transfers",
                "Kit Issues",
                "Expiry Alerts",
            ],
            label_visibility="collapsed",
            key="warehouse_navigation",
        )

    if section == "Overview":
        render_overview()

    elif section == "Add Inventory":
        render_add_inventory()

    elif section == "Warehouse Inventory":
        render_inventory()

    elif section == "Transfer Kits":
        render_transfer()

    elif section == "Transfers":
        render_transfers()

    elif section == "Kit Issues":
        render_issues()

    elif section == "Expiry Alerts":
        render_expiry()
