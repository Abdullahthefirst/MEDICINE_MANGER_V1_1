import streamlit as st
import pandas as pd
from datetime import date

from utils.ai_chat import ask_gemini
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
        "Kit & Component Issues",
        "Monitor reported defects and replacement confirmations",
    )

    try:
        data = fetch_data("kit_issue_component_status")
    except Exception as exc:
        st.error(f"Unable to load issue information: {exc}")
        return

    if not data:
        st.info("No kit or component issues have been reported.")
        return

    df = pd.DataFrame(data)

    tab1, tab2 = st.tabs([
        "Kit Issues",
        "Component Issues",
    ])

    with tab1:
        issue_columns = [
            "issue_id",
            "kit_id",
            "kit_type",
            "event_date",
            "runs_affected",
            "issue_status",
            "description",
        ]

        issue_df = (
            df[
                [c for c in issue_columns if c in df.columns]
            ]
            .drop_duplicates(subset=["issue_id"])
        )

        st.dataframe(
            issue_df,
            use_container_width=True,
            hide_index=True,
        )

    with tab2:
        component_columns = [
            "issue_id",
            "kit_id",
            "component_name",
            "catalogue_number",
            "runs_affected",
            "component_resolution_status",
            "warehouse_resolution_date",
            "warehouse_notes",
            "hospital_confirmed_at",
        ]

        st.dataframe(
            df[
                [c for c in component_columns if c in df.columns]
            ],
            use_container_width=True,
            hide_index=True,
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
        "ABT and TRASIS production performance across all sites",
    )

    try:
        runs = fetch_data("production_runs")
        sites = fetch_data("sites", "id,name,site_type")
    except Exception as exc:
        st.error(f"Unable to load production data: {exc}")
        return

    if not runs:
        st.info("No production records available.")
        return

    df = pd.DataFrame(runs)

    site_lookup = {row["id"]: row["name"] for row in sites}

    if "hospital_site_id" in df.columns:
        df["site_name"] = df["hospital_site_id"].map(site_lookup)

    if "event_date" in df.columns:
        df["event_date"] = pd.to_datetime(df["event_date"])

    st.subheader("Filters")

    c1, c2, c3, c4 = st.columns(4)

    start_date = c1.date_input(
        "From",
        value=date.today().replace(day=1),
        key="admin_production_from",
    )

    end_date = c2.date_input(
        "To",
        value=date.today(),
        key="admin_production_to",
    )

    site_options = ["All Sites"] + sorted(
        [row["name"] for row in sites if row.get("site_type") == "hospital"]
    )

    selected_site = c3.selectbox("Site", site_options)

    selected_machine = c4.selectbox("Machine", ["All", "ABT", "TRASIS"])

    outcomes = ["All"]
    if "outcome" in df.columns:
        outcomes += sorted(
            df["outcome"].dropna().astype(str).unique().tolist()
        )

    selected_outcome = st.selectbox("Outcome", outcomes)

    filtered = df.copy()

    if "event_date" in filtered.columns:
        filtered = filtered[
            (filtered["event_date"].dt.date >= start_date)
            & (filtered["event_date"].dt.date <= end_date)
        ]

    if selected_site != "All Sites" and "site_name" in filtered.columns:
        filtered = filtered[filtered["site_name"] == selected_site]

    if selected_machine != "All" and "machine" in filtered.columns:
        filtered = filtered[
            filtered["machine"].astype(str).str.upper() == selected_machine
        ]

    if selected_outcome != "All" and "outcome" in filtered.columns:
        filtered = filtered[filtered["outcome"] == selected_outcome]

    if filtered.empty:
        st.info("No production records match these filters.")
        return

    tab1, tab2, tab3 = st.tabs(["Overview", "ABT", "TRASIS"])

    def machine_view(machine_df, machine_name):
        if machine_df.empty:
            st.info(f"No {machine_name} production data.")
            return

        total_runs = len(machine_df)
        successful = (
            machine_df["outcome"].astype(str).str.upper().eq("SUCCESSFUL").sum()
            if "outcome" in machine_df.columns else 0
        )
        failed = total_runs - successful
        total_mci = (
            machine_df["activity_mci"].fillna(0).sum()
            if "activity_mci" in machine_df.columns else 0
        )
        lost_mci = (
            machine_df["activity_lost_mci"].fillna(0).sum()
            if "activity_lost_mci" in machine_df.columns else 0
        )
        success_rate = successful / total_runs * 100 if total_runs else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric(f"{machine_name} Runs", total_runs)
        c2.metric("Successful", int(successful))
        c3.metric("Failed", int(failed))
        c4.metric("Total Activity", f"{total_mci:.2f} mCi")
        c5.metric("Success Rate", f"{success_rate:.1f}%")

        st.caption(f"Activity Lost: {lost_mci:.2f} mCi")

        if "event_date" in machine_df.columns:
            trend = (
                machine_df.groupby(machine_df["event_date"].dt.date)
                .size()
                .reset_index(name="runs")
            )
            trend.columns = ["Date", "Runs"]
            st.line_chart(trend, x="Date", y="Runs")

        preferred = [
            "event_date",
            "site_name",
            "machine",
            "run_number",
            "activity_mci",
            "outcome",
            "activity_lost_mci",
            "notes",
            "created_at",
        ]

        st.dataframe(
            machine_df[[col for col in preferred if col in machine_df.columns]],
            use_container_width=True,
            hide_index=True,
        )

    with tab1:
        total_runs = len(filtered)
        total_mci = (
            filtered["activity_mci"].fillna(0).sum()
            if "activity_mci" in filtered.columns else 0
        )
        lost_mci = (
            filtered["activity_lost_mci"].fillna(0).sum()
            if "activity_lost_mci" in filtered.columns else 0
        )
        successful = (
            filtered["outcome"].astype(str).str.upper().eq("SUCCESSFUL").sum()
            if "outcome" in filtered.columns else 0
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Runs", total_runs)
        c2.metric("Successful", int(successful))
        c3.metric("Total Activity", f"{total_mci:.2f} mCi")
        c4.metric("Activity Lost", f"{lost_mci:.2f} mCi")

        if "machine" in filtered.columns:
            counts = (
                filtered["machine"].astype(str).str.upper().value_counts().reset_index()
            )
            counts.columns = ["Machine", "Runs"]
            st.bar_chart(counts, x="Machine", y="Runs")

    with tab2:
        machine_view(
            filtered[filtered["machine"].astype(str).str.upper() == "ABT"],
            "ABT",
        )

    with tab3:
        machine_view(
            filtered[filtered["machine"].astype(str).str.upper() == "TRASIS"],
            "TRASIS",
        )


# ---------------------------------------------------------
# DOWNTIME
# ---------------------------------------------------------

def render_downtime():
    page_header(
        "Equipment Downtime",
        "Analyze downtime across hospitals and equipment",
    )

    try:
        data = fetch_data("downtime_report")
    except Exception as exc:
        st.error(f"Unable to load downtime: {exc}")
        return

    if not data:
        st.info("No downtime records available.")
        return

    df = pd.DataFrame(data)

    if "event_date" in df.columns:
        df["event_date"] = pd.to_datetime(df["event_date"])

    c1, c2, c3, c4 = st.columns(4)

    start_date = c1.date_input("From", value=date.today().replace(day=1), key="downtime_from")
    end_date = c2.date_input("To", value=date.today(), key="downtime_to")

    site_column = None
    for candidate in ["hospital", "site_name", "site"]:
        if candidate in df.columns:
            site_column = candidate
            break

    site_options = ["All Sites"]
    if site_column:
        site_options += sorted(df[site_column].dropna().astype(str).unique().tolist())

    selected_site = c3.selectbox("Site", site_options)

    equipment_options = ["All Equipment"]
    if "equipment_name" in df.columns:
        equipment_options += sorted(df["equipment_name"].dropna().astype(str).unique().tolist())

    selected_equipment = c4.selectbox("Equipment", equipment_options)

    filtered = df.copy()

    if "event_date" in filtered.columns:
        filtered = filtered[
            (filtered["event_date"].dt.date >= start_date)
            & (filtered["event_date"].dt.date <= end_date)
        ]

    if selected_site != "All Sites" and site_column:
        filtered = filtered[filtered[site_column] == selected_site]

    if selected_equipment != "All Equipment" and "equipment_name" in filtered.columns:
        filtered = filtered[filtered["equipment_name"] == selected_equipment]

    if filtered.empty:
        st.info("No downtime records match the filters.")
        return

    total_minutes = filtered["duration_minutes"].fillna(0).sum()
    event_count = len(filtered)
    avg_minutes = total_minutes / event_count if event_count else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Downtime Events", event_count)
    c2.metric("Total Downtime", f"{total_minutes / 60:.2f} hours")
    c3.metric("Average / Event", f"{avg_minutes:.1f} min")

    if site_column and "duration_minutes" in filtered.columns:
        by_site = filtered.groupby(site_column, as_index=False)["duration_minutes"].sum()
        st.subheader("Downtime by Site")
        st.bar_chart(by_site, x=site_column, y="duration_minutes")

    if "equipment_name" in filtered.columns:
        by_equipment = filtered.groupby("equipment_name", as_index=False)["duration_minutes"].sum()
        st.subheader("Downtime by Equipment")
        st.bar_chart(by_equipment, x="equipment_name", y="duration_minutes")

    st.subheader("Detailed Records")
    st.dataframe(filtered, use_container_width=True, hide_index=True)


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
        "Filter operational analytics by site and date",
    )

    try:
        sites = fetch_data("sites", "id,name,site_type")
    except Exception as exc:
        st.error(f"Unable to load sites: {exc}")
        return

    report = st.selectbox(
        "Report",
        [
            "Production Performance",
            "Patients & Activity",
            "Production Failures",
            "Equipment Downtime",
            "Kit Usage History",
        ],
    )

    st.subheader("Filters")
    c1, c2, c3 = st.columns(3)

    site_options = {"All Sites": None}
    for row in sites:
        if row.get("site_type") == "hospital":
            site_options[row["name"]] = row["id"]

    site_name = c1.selectbox("Site", list(site_options.keys()), key="reports_site")
    start_date = c2.date_input("From", value=date.today().replace(day=1), key="reports_from")
    end_date = c3.date_input("To", value=date.today(), key="reports_to")

    selected_site_id = site_options[site_name]

    st.divider()

    if report == "Production Performance":
        show_production_report(selected_site_id, start_date, end_date)
    elif report == "Patients & Activity":
        show_patient_report(selected_site_id, start_date, end_date)
    elif report == "Production Failures":
        show_failure_report(selected_site_id, start_date, end_date)
    elif report == "Equipment Downtime":
        show_downtime_report(selected_site_id, start_date, end_date)
    elif report == "Kit Usage History":
        show_kit_usage_report(selected_site_id, start_date, end_date)


def render_export_data():
    page_header(
        "Export Data",
        "Download operational data for analysis or reporting",
    )

    datasets = {
        "Current Inventory": "current_inventory",
        "Kit Traceability": "kit_traceability",
        "Pending Transfers": "pending_transfers",
        "Kit Usage": "kit_usage",
        "Production Runs": "production_runs",
        "Production Failures": "production_failures",
        "Daily Hospital Summaries": "daily_hospital_summaries",
        "Kit Issues": "kit_issue_history",
        "Component Issues": "kit_issue_component_status",
        "Downtime": "downtime_report",
        "Backdated Entries": "admin_backdated_entries_with_review",
        "Audit Log": "audit_log",
    }

    dataset_name = st.selectbox("Dataset", list(datasets.keys()))
    table = datasets[dataset_name]

    try:
        data = fetch_data(table)
    except Exception as exc:
        st.error(f"Unable to load export data: {exc}")
        return

    if not data:
        st.info("No data available for this export.")
        return

    df = pd.DataFrame(data)
    st.write(f"**Rows available:** {len(df)}")
    st.dataframe(df.head(100), use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8")
    safe_name = dataset_name.lower().replace(" ", "_")
    st.download_button(
        "Download CSV",
        data=csv,
        file_name=f"{safe_name}_{date.today().isoformat()}.csv",
        mime="text/csv",
        use_container_width=True,
    )


def render_ai_assistant():
    page_header(
        "AI Assistant",
        "Ask questions about operational data",
    )

    st.info(
        "Enter your Gemini API key to use the AI Assistant. The key is used only for this Streamlit session and is not stored in the Medicine Manager database."
    )

    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        placeholder="Enter Gemini API key",
        key="gemini_admin_api_key",
    )

    if not api_key:
        st.warning("Enter your Gemini API key to continue.")
        return

    st.caption("Model: Gemini 3.6 Flash")

    if "admin_ai_messages" not in st.session_state:
        st.session_state.admin_ai_messages = []

    for message in st.session_state.admin_ai_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Ask about inventory, production, downtime, issues...")

    if question:
        st.session_state.admin_ai_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing operational data..."):
                try:
                    answer = ask_gemini(api_key, question)
                except Exception as exc:
                    answer = f"Unable to generate an AI response. {exc}"
            st.markdown(answer)

        st.session_state.admin_ai_messages.append({"role": "assistant", "content": answer})


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
                "Export Data",
                "AI Assistant",
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

    elif section == "Export Data":
        render_export_data()

    elif section == "AI Assistant":
        render_ai_assistant()

    elif section == "Users":
        render_users()

    elif section == "Sites":
        render_sites()

    elif section == "Backdated Entries":
        render_backdated()

    elif section == "Audit Log":
        render_audit()
