import streamlit as st
import pandas as pd

from utils.auth import (
    require_role,
    get_authenticated_client,
)
from utils.reports import (
    show_production_report,
    show_patient_report,
    show_failure_report,
    show_downtime_report,
    show_kit_usage_report,
)
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


def safe_count(table):
    try:
        return len(fetch_data(table))
    except Exception:
        return 0


def show_dataframe(data, empty_message="No records found."):
    if not data:
        st.info(empty_message)
        return

    df = pd.DataFrame(data)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------

def render_overview():
    page_header(
        "Admin Dashboard",
        "System-wide operational overview",
    )

    try:
        inventory = fetch_data("current_inventory")
        issues = fetch_data("open_kit_issues")
        transfers = fetch_data("pending_transfers")
        expiry = fetch_data("kit_expiry_alerts")

    except Exception as exc:
        st.error(
            f"Unable to load dashboard data: {exc}"
        )
        return

    active_kits = len(inventory)
    open_issues = len(
        {row.get("issue_id") for row in issues}
    )
    pending_transfers = len(
        {row.get("transfer_id") for row in transfers}
    )
    expiry_alerts = len(expiry)

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Active Kits",
        active_kits,
    )

    col2.metric(
        "Open Issues",
        open_issues,
    )

    col3.metric(
        "Expiry Alerts",
        expiry_alerts,
    )

    col4.metric(
        "Pending Transfers",
        pending_transfers,
    )

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Recent Open Issues")

        if issues:
            df = pd.DataFrame(issues)

            wanted = [
                "kit_id",
                "kit_type",
                "hospital",
                "component_name",
                "runs_affected",
                "event_date",
            ]

            existing = [
                col for col in wanted
                if col in df.columns
            ]

            st.dataframe(
                df[existing].head(10),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("No open kit issues.")

    with right:
        st.subheader("Expiry Alerts")

        if expiry:
            df = pd.DataFrame(expiry)

            wanted = [
                "kit_id",
                "site_name",
                "kit_type",
                "expiry_date",
                "days_to_expiry",
                "expiry_category",
            ]

            existing = [
                col for col in wanted
                if col in df.columns
            ]

            st.dataframe(
                df[existing].head(10),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("No current expiry alerts.")


# ---------------------------------------------------------
# INVENTORY
# ---------------------------------------------------------

def render_inventory():
    page_header(
        "Inventory",
        "View inventory across all warehouses and hospitals",
    )

    try:
        data = fetch_data("current_inventory")

    except Exception as exc:
        st.error(f"Unable to load inventory: {exc}")
        return

    if not data:
        st.info("No active inventory found.")
        return

    df = pd.DataFrame(data)

    col1, col2, col3 = st.columns(3)

    site_options = ["All"]

    if "site_name" in df.columns:
        site_options += sorted(
            df["site_name"]
            .dropna()
            .unique()
            .tolist()
        )

    selected_site = col1.selectbox(
        "Site",
        site_options,
    )

    status_options = ["All"]

    if "status" in df.columns:
        status_options += sorted(
            df["status"]
            .dropna()
            .unique()
            .tolist()
        )

    selected_status = col2.selectbox(
        "Status",
        status_options,
    )

    kit_search = col3.text_input(
        "Search Kit ID",
        placeholder="KIT-000123",
    )

    filtered = df.copy()

    if selected_site != "All":
        filtered = filtered[
            filtered["site_name"] == selected_site
        ]

    if selected_status != "All":
        filtered = filtered[
            filtered["status"] == selected_status
        ]

    if kit_search:
        filtered = filtered[
            filtered["kit_id"]
            .astype(str)
            .str.contains(
                kit_search,
                case=False,
                na=False,
            )
        ]

    preferred = [
        "kit_id",
        "kit_type",
        "site_name",
        "status",
        "lot_number",
        "origin",
        "received_date",
        "expiry_date",
        "runs_used",
        "runs_remaining",
        "remaining_volume_ml",
    ]

    columns = [
        col for col in preferred
        if col in filtered.columns
    ]

    st.caption(
        f"{len(filtered)} inventory record(s)"
    )

    st.dataframe(
        filtered[columns],
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# TRANSFERS
# ---------------------------------------------------------

def render_transfers():
    page_header(
        "Transfers",
        "Pending and partially received inventory transfers",
    )

    try:
        data = fetch_data("pending_transfers")

    except Exception as exc:
        st.error(f"Unable to load transfers: {exc}")
        return

    if not data:
        st.success("No pending transfers.")
        return

    df = pd.DataFrame(data)

    preferred = [
        "transfer_id",
        "transfer_date",
        "source_site",
        "destination_site",
        "kit_id",
        "kit_type",
        "transfer_status",
        "received",
        "received_at",
    ]

    columns = [
        col for col in preferred
        if col in df.columns
    ]

    st.dataframe(
        df[columns],
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# KIT ISSUES
# ---------------------------------------------------------

def render_issues():
    page_header(
        "Kit Component Issues",
        "Monitor component defects reported by hospitals",
    )

    tab1, tab2 = st.tabs(
        [
            "Open Issues",
            "Issue History",
        ]
    )

    with tab1:
        try:
            issues = fetch_data(
                "open_kit_issues"
            )

            if not issues:
                st.success("No open kit issues.")

            else:
                df = pd.DataFrame(issues)

                preferred = [
                    "issue_id",
                    "event_date",
                    "hospital",
                    "kit_id",
                    "kit_type",
                    "component_name",
                    "catalogue_number",
                    "runs_affected",
                    "description",
                    "reported_by",
                ]

                columns = [
                    c for c in preferred
                    if c in df.columns
                ]

                st.dataframe(
                    df[columns],
                    use_container_width=True,
                    hide_index=True,
                )

        except Exception as exc:
            st.error(
                f"Unable to load open issues: {exc}"
            )

    with tab2:
        try:
            history = fetch_data(
                "kit_issue_history"
            )

            show_dataframe(
                history,
                "No kit issue history available.",
            )

        except Exception as exc:
            st.error(
                f"Unable to load issue history: {exc}"
            )


# ---------------------------------------------------------
# EXPIRY
# ---------------------------------------------------------

def render_expiry():
    page_header(
        "Expiry Management",
        "Kits and components approaching expiry",
    )

    tab1, tab2 = st.tabs(
        [
            "Kit Alerts",
            "Component Alerts",
        ]
    )

    with tab1:
        try:
            kits = fetch_data(
                "kit_expiry_alerts"
            )

            if kits:
                df = pd.DataFrame(kits)

                if "days_to_expiry" in df.columns:
                    df = df.sort_values(
                        "days_to_expiry"
                    )

                show_dataframe(df.to_dict("records"))

            else:
                st.success(
                    "No kit expiry alerts."
                )

        except Exception as exc:
            st.error(
                f"Unable to load kit expiry alerts: {exc}"
            )

    with tab2:
        try:
            components = fetch_data(
                "component_expiry_alerts"
            )

            if components:
                df = pd.DataFrame(components)

                if "days_to_expiry" in df.columns:
                    df = df.sort_values(
                        "days_to_expiry"
                    )

                show_dataframe(df.to_dict("records"))

            else:
                st.success(
                    "No component expiry alerts."
                )

        except Exception as exc:
            st.error(
                f"Unable to load component expiry alerts: {exc}"
            )


# ---------------------------------------------------------
# PRODUCTION
# ---------------------------------------------------------

def render_production():
    page_header(
        "Production",
        "ABT and Trasis production performance",
    )

    try:
        data = fetch_data(
            "daily_production_summary"
        )

    except Exception as exc:
        st.error(
            f"Unable to load production data: {exc}"
        )
        return

    if not data:
        st.info("No production runs recorded yet.")
        return

    df = pd.DataFrame(data)

    col1, col2, col3 = st.columns(3)

    total_runs = (
        df["total_runs"].sum()
        if "total_runs" in df.columns
        else 0
    )

    successful = (
        df["successful_runs"].sum()
        if "successful_runs" in df.columns
        else 0
    )

    lost_mci = (
        df["total_activity_lost_mci"].sum()
        if "total_activity_lost_mci" in df.columns
        else 0
    )

    col1.metric(
        "Total Runs",
        int(total_runs),
    )

    col2.metric(
        "Successful Runs",
        int(successful),
    )

    col3.metric(
        "Activity Lost",
        f"{lost_mci:.2f} mCi",
    )

    st.divider()

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# DOWNTIME
# ---------------------------------------------------------

def render_downtime():
    page_header(
        "Equipment Downtime",
        "Hospital equipment downtime and maintenance events",
    )

    try:
        data = fetch_data("downtime_report")

    except Exception as exc:
        st.error(
            f"Unable to load downtime data: {exc}"
        )
        return

    show_dataframe(
        data,
        "No equipment downtime has been recorded.",
    )


# ---------------------------------------------------------
# USERS
# ---------------------------------------------------------

def render_users():
    page_header(
        "Users",
        "Application users and role assignments",
    )

    try:
        supabase = get_authenticated_client()

        profiles = (
            supabase
            .table("profiles")
            .select(
                "id, full_name, role, "
                "site_id, is_active, created_at"
            )
            .execute()
        ).data or []

        sites = fetch_data(
            "sites",
            "id,name,site_type",
        )

    except Exception as exc:
        st.error(
            f"Unable to load users: {exc}"
        )
        return

    site_lookup = {
        site["id"]: site["name"]
        for site in sites
    }

    for profile in profiles:
        profile["site_name"] = site_lookup.get(
            profile.get("site_id"),
            "All Sites"
            if profile.get("role") == "admin"
            else "Unassigned",
        )

    if profiles:
        df = pd.DataFrame(profiles)

        preferred = [
            "full_name",
            "role",
            "site_name",
            "is_active",
            "created_at",
        ]

        st.dataframe(
            df[preferred],
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info("No application users found.")

    st.caption(
        "Creating Supabase Auth accounts will be connected "
        "to the Admin interface later. For now this page "
        "shows existing application profiles."
    )


# ---------------------------------------------------------
# SITES
# ---------------------------------------------------------

def render_sites():
    page_header(
        "Sites",
        "Warehouses and hospital locations",
    )

    try:
        sites = fetch_data(
            "sites",
            "id,name,city,site_type,created_at",
        )

    except Exception as exc:
        st.error(
            f"Unable to load sites: {exc}"
        )
        return

    show_dataframe(
        sites,
        "No sites have been configured.",
    )


# ---------------------------------------------------------
# BACKDATED ENTRIES
# ---------------------------------------------------------

def render_backdated():
    page_header(
        "Backdated Entries",
        "Operational records entered after their actual event date",
    )

    try:
        data = fetch_data(
            "admin_backdated_entries_with_review"
        )

    except Exception as exc:
        st.error(
            f"Unable to load backdated entries: {exc}"
        )
        return

    if not data:
        st.success(
            "No backdated entries require review."
        )
        return

    df = pd.DataFrame(data)

    col1, col2 = st.columns(2)

    filter_review = col1.selectbox(
        "Review status",
        [
            "All",
            "Pending",
            "Reviewed",
        ],
    )

    entry_types = ["All"]

    if "entry_type" in df.columns:
        entry_types += sorted(
            df["entry_type"]
            .dropna()
            .unique()
            .tolist()
        )

    selected_type = col2.selectbox(
        "Entry type",
        entry_types,
    )

    filtered = df.copy()

    if filter_review == "Pending":
        filtered = filtered[
            filtered["reviewed"] == False
        ]

    elif filter_review == "Reviewed":
        filtered = filtered[
            filtered["reviewed"] == True
        ]

    if selected_type != "All":
        filtered = filtered[
            filtered["entry_type"]
            == selected_type
        ]

    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# AUDIT LOG
# ---------------------------------------------------------

def render_audit():
    page_header(
        "Audit Log",
        "Important actions performed throughout the system",
    )

    try:
        data = fetch_data("audit_log")

    except Exception as exc:
        st.error(
            f"Unable to load audit log: {exc}"
        )
        return

    if not data:
        st.info("No audit events have been recorded.")
        return

    df = pd.DataFrame(data)

    if "created_at" in df.columns:
        df = df.sort_values(
            "created_at",
            ascending=False,
        )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


# ---------------------------------------------------------
# MAIN ADMIN ROUTER
# ---------------------------------------------------------

def render_reports():
    page_header(
        "Reports & Analytics",
        "System-wide operational performance",
    )

    report = st.selectbox(
        "Report",
        [
            "Production Performance",
            "Patients & Activity",
            "Production Failures",
            "Equipment Downtime",
            "Kit Consumption",
        ],
    )

    st.divider()

    if report == "Production Performance":
        show_production_report()

    elif report == "Patients & Activity":
        show_patient_report()

    elif report == "Production Failures":
        show_failure_report()

    elif report == "Equipment Downtime":
        show_downtime_report()

    elif report == "Kit Consumption":
        show_kit_usage_report()


def render():
    require_role("admin")

    with st.sidebar:
        st.markdown("### Admin")

        section = st.radio(
            "Navigation",
            [
                "Overview",
                "Inventory",
                "Transfers",
                "Kit Issues",
                "Expiry",
                "Production",
                "Downtime",
                "Reports & Analytics",
                "Users",
                "Sites",
                "Backdated Entries",
                "Audit Log",
            ],
            label_visibility="collapsed",
            key="admin_navigation",
        )

    if section == "Overview":
        render_overview()

    elif section == "Inventory":
        render_inventory()

    elif section == "Transfers":
        render_transfers()

    elif section == "Kit Issues":
        render_issues()

    elif section == "Expiry":
        render_expiry()

    elif section == "Production":
        render_production()

    elif section == "Downtime":
        render_downtime()

    elif section == "Reports & Analytics":
        render_reports()

    elif section == "Users":
        render_users()

    elif section == "Sites":
        render_sites()

    elif section == "Backdated Entries":
        render_backdated()

    elif section == "Audit Log":
        render_audit()
