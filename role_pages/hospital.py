import streamlit as st
import pandas as pd
from datetime import date

from utils.auth import (
    require_role,
    get_authenticated_client,
    get_site_id,
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
        "Hospital Dashboard",
        "Inventory, daily usage, production and equipment monitoring",
    )

    hospital_id = get_site_id()

    try:
        inventory = fetch_data("hospital_inventory")
        transfers = fetch_data("pending_transfers")
        issues = fetch_data("open_kit_issues")
        expiry = fetch_data("kit_expiry_alerts")

    except Exception as exc:
        st.error(f"Unable to load dashboard: {exc}")
        return

    inventory = [
        row for row in inventory
        if row.get("site_id") == hospital_id
    ]

    transfers = [
        row for row in transfers
        if row.get("destination_site_id") == hospital_id
        and not row.get("received")
    ]

    issues = [
        row for row in issues
        if row.get("hospital_site_id") == hospital_id
    ]

    expiry = [
        row for row in expiry
        if row.get("site_id") == hospital_id
    ]

    available = len([
        row for row in inventory
        if row.get("status") == "HOSPITAL_AVAILABLE"
    ])

    issue_count = len({
        row.get("issue_id")
        for row in issues
    })

    pending_receipt = len(transfers)
    expiry_count = len(expiry)

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Available Kits", available)
    c2.metric("Pending Receipt", pending_receipt)
    c3.metric("Open Kit Issues", issue_count)
    c4.metric("Expiry Alerts", expiry_count)

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Inventory")

        if inventory:
            df = pd.DataFrame(inventory)

            wanted = [
                "kit_id",
                "kit_type",
                "status",
                "runs_remaining",
                "expiry_date",
            ]

            cols = [
                c for c in wanted
                if c in df.columns
            ]

            st.dataframe(
                df[cols].head(10),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info("No hospital inventory.")

    with right:
        st.subheader("Open Kit Issues")

        if issues:
            df = pd.DataFrame(issues)

            wanted = [
                "kit_id",
                "component_name",
                "runs_affected",
                "event_date",
            ]

            cols = [
                c for c in wanted
                if c in df.columns
            ]

            st.dataframe(
                df[cols].head(10),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.success("No open kit issues.")


# =========================================================
# DELIVERY CONFIRMATION
# =========================================================

def render_delivery_confirmation():
    page_header(
        "Delivery Confirmation",
        "Select all kits physically received from the warehouse",
    )

    hospital_id = get_site_id()

    try:
        transfers = fetch_data("pending_transfers")
    except Exception as exc:
        st.error(f"Unable to load pending transfers: {exc}")
        return

    transfers = [
        row for row in transfers
        if row.get("destination_site_id") == hospital_id
        and not row.get("received")
    ]

    if not transfers:
        st.success("No kits are awaiting receiving confirmation.")
        return

    df = pd.DataFrame(transfers)

    columns = [
        "transfer_id",
        "transfer_date",
        "source_site",
        "kit_id",
        "kit_type",
    ]

    st.dataframe(
        df[[c for c in columns if c in df.columns]],
        use_container_width=True,
        hide_index=True,
    )

    option_lookup = {}
    for row in transfers:
        label = (
            f'{row["kit_id"]} — '
            f'{row.get("kit_type", "")} — '
            f'{row.get("source_site", "")}'
        )
        option_lookup[label] = row["transfer_item_id"]

    with st.form("multi_receive_form"):
        selected = st.multiselect(
            "Kits Physically Received",
            list(option_lookup.keys()),
        )

        submitted = st.form_submit_button(
            "Confirm Selected Kits",
            use_container_width=True,
        )

    if submitted:
        if not selected:
            st.error("Select at least one received kit.")
            return

        supabase = get_authenticated_client()
        successful = 0
        failed = []

        for label in selected:
            try:
                supabase.rpc(
                    "confirm_transfer_item",
                    {"p_transfer_item_id": option_lookup[label]},
                ).execute()
                successful += 1
            except Exception as exc:
                failed.append(f"{label}: {exc}")

        if successful:
            st.success(f"{successful} kit(s) confirmed received.")

        if failed:
            st.warning("Some kits could not be confirmed:\n\n" + "\n\n".join(failed))

        st.rerun()


# =========================================================
# ISSUE RESOLUTION CONFIRMATION
# =========================================================

def render_issue_resolution_confirmation():
    hospital_id = get_site_id()

    try:
        supabase = get_authenticated_client()
        response = (
            supabase
            .table("kit_issues")
            .select(
                "id,kit_id,hospital_site_id,event_date,runs_affected,description,"
                "resolution_status,warehouse_resolution_date,warehouse_resolution_notes,"
                "kits(kit_id,inventory_templates(name))"
            )
            .eq("hospital_site_id", hospital_id)
            .eq("status", "OPEN")
            .eq("resolution_status", "AWAITING_HOSPITAL_CONFIRMATION")
            .execute()
        )
        issues = response.data or []
    except Exception as exc:
        st.error(f"Unable to load resolution confirmations: {exc}")
        return

    if not issues:
        st.success("No resolved issues are awaiting confirmation.")
        return

    option_lookup = {}
    for row in issues:
        kit_info = row.get("kits") or {}
        label = f'Issue #{row["id"]} — {kit_info.get("kit_id", "")}'
        option_lookup[label] = row

    selected_label = st.selectbox("Issue", list(option_lookup.keys()))
    selected = option_lookup[selected_label]

    kit_info = selected.get("kits") or {}
    template_info = kit_info.get("inventory_templates") or {}

    c1, c2, c3 = st.columns(3)
    c1.metric("Kit ID", kit_info.get("kit_id", "-"))
    c2.metric("Kit Type", template_info.get("name", "-"))
    c3.metric("Affected Runs", selected.get("runs_affected", 0))

    st.write(f'**Issue Date:** {selected.get("event_date", "")}')
    st.write(f'**Items Sent Date:** {selected.get("warehouse_resolution_date", "")}')

    if selected.get("warehouse_resolution_notes"):
        st.info(selected["warehouse_resolution_notes"])

    st.warning(
        "Confirm only after the replacement items have physically arrived and the issue is resolved."
    )

    confirm = st.button(
        "Confirm Issue Resolved",
        type="primary",
        use_container_width=True,
    )

    if confirm:
        try:
            supabase = get_authenticated_client()
            supabase.rpc(
                "confirm_issue_resolution",
                {"p_issue_id": selected["id"]},
            ).execute()
            st.success("Issue resolution confirmed. The kit is now available again.")
            st.rerun()
        except Exception as exc:
            st.error(f"Unable to confirm resolution: {exc}")


# =========================================================
# CONFIRMATION
# =========================================================

def render_confirmation():
    page_header(
        "Confirmation",
        "Confirm deliveries and resolved kit issues",
    )

    tab1, tab2 = st.tabs([
        "Delivery Confirmation",
        "Issue Resolution Confirmation",
    ])

    with tab1:
        render_delivery_confirmation()

    with tab2:
        render_issue_resolution_confirmation()


# =========================================================
# HOSPITAL INVENTORY
# =========================================================

def render_inventory():
    page_header(
        "Hospital Inventory",
        "Kits currently held at your hospital",
    )

    hospital_id = get_site_id()

    try:
        data = fetch_data("hospital_inventory")

    except Exception as exc:
        st.error(
            f"Unable to load hospital inventory: {exc}"
        )
        return

    data = [
        row for row in data
        if row.get("site_id") == hospital_id
    ]

    if not data:
        st.info("No hospital inventory found.")
        return

    df = pd.DataFrame(data)

    c1, c2, c3 = st.columns(3)

    types = ["All"]

    if "kit_type" in df.columns:
        types += sorted(
            df["kit_type"]
            .dropna()
            .unique()
            .tolist()
        )

    selected_type = c1.selectbox(
        "Kit Type",
        types,
    )

    statuses = ["All"]

    if "status" in df.columns:
        statuses += sorted(
            df["status"]
            .dropna()
            .unique()
            .tolist()
        )

    selected_status = c2.selectbox(
        "Status",
        statuses,
    )

    search = c3.text_input(
        "Search Kit ID",
        placeholder="KIT-000482",
    )

    filtered = df.copy()

    if selected_type != "All":
        filtered = filtered[
            filtered["kit_type"] == selected_type
        ]

    if selected_status != "All":
        filtered = filtered[
            filtered["status"] == selected_status
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
        "status",
        "lot_number",
        "expiry_date",
        "total_runs",
        "runs_used",
        "runs_remaining",
        "initial_volume_ml",
        "remaining_volume_ml",
    ]

    cols = [
        c for c in preferred
        if c in filtered.columns
    ]

    st.dataframe(
        filtered[cols],
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# DAILY SUMMARY + KIT USAGE
# =========================================================

def render_daily_summary():
    page_header(
        "Daily Summary",
        "Record daily patients and kit usage",
    )

    hospital_id = get_site_id()

    selected_date = st.date_input(
        "Operational Date",
        value=date.today(),
        key="daily_summary_date",
    )

    st.subheader("Patient Totals")

    with st.form("daily_patient_summary_form"):
        c1, c2 = st.columns(2)

        abt_patients = c1.number_input(
            "Patients Served by ABT",
            min_value=0,
            value=0,
            step=1,
        )

        trasis_patients = c2.number_input(
            "Patients Served by TRASIS",
            min_value=0,
            value=0,
            step=1,
        )

        notes = st.text_area(
            "Daily Notes",
            placeholder="Optional",
        )

        save_summary = st.form_submit_button(
            "Save Daily Summary",
            use_container_width=True,
        )

    if save_summary:
        try:
            supabase = get_authenticated_client()

            response = supabase.rpc(
                "save_daily_hospital_summary",
                {
                    "p_event_date":
                        selected_date.isoformat(),

                    "p_abt_patients":
                        int(abt_patients),

                    "p_trasis_patients":
                        int(trasis_patients),

                    "p_notes":
                        notes.strip() or None,
                },
            ).execute()

            st.session_state[
                "current_daily_summary_id"
            ] = response.data

            st.success(
                "Daily summary saved."
            )

        except Exception as exc:
            st.error(
                f"Unable to save summary: {exc}"
            )

    st.divider()
    st.subheader("Kit Usage")

    try:
        inventory = fetch_data("hospital_inventory")

        inventory = [
            row for row in inventory
            if row.get("site_id") == hospital_id
            and row.get("status") == "HOSPITAL_AVAILABLE"
        ]

        summaries = fetch_data(
            "daily_hospital_summaries",
            "id,hospital_site_id,event_date",
        )

    except Exception as exc:
        st.error(
            f"Unable to load kit usage data: {exc}"
        )
        return

    summary_id = None

    for row in summaries:
        if (
            row.get("hospital_site_id") == hospital_id
            and str(row.get("event_date"))
                == selected_date.isoformat()
        ):
            summary_id = row.get("id")
            break

    if summary_id is None:
        st.info(
            "Save the Daily Summary first, then kit usage can be recorded."
        )
        return

    if not inventory:
        st.info(
            "No usable hospital kits are available."
        )
        return

    kit_lookup = {
        (
            f'{row["kit_id"]} — '
            f'{row["kit_type"]} — '
            f'{row.get("runs_remaining", 0)} run(s) remaining'
        ):
        row

        for row in inventory
    }

    with st.form("kit_usage_form"):
        selected_kit_label = st.selectbox(
            "Kit",
            list(kit_lookup.keys()),
        )

        selected_kit = kit_lookup[
            selected_kit_label
        ]

        remaining = int(
            selected_kit.get(
                "runs_remaining",
                0,
            ) or 0
        )

        runs_used = st.number_input(
            "Runs Used Today",
            min_value=1,
            max_value=max(remaining, 1),
            value=1,
            step=1,
        )

        usage_notes = st.text_area(
            "Usage Notes",
            placeholder="Optional",
        )

        submit_usage = st.form_submit_button(
            "Record Kit Usage",
            use_container_width=True,
        )

    if submit_usage:
        try:
            supabase = get_authenticated_client()

            supabase.rpc(
                "record_kit_usage",
                {
                    "p_daily_summary_id":
                        summary_id,

                    "p_kit_id":
                        selected_kit["kit_pk"],

                    "p_runs_used":
                        int(runs_used),

                    "p_notes":
                        usage_notes.strip() or None,
                },
            ).execute()

            st.success(
                "Kit usage recorded."
            )

            st.rerun()

        except Exception as exc:
            st.error(
                f"Unable to record kit usage: {exc}"
            )


# =========================================================
# PRODUCTION RUNS
# =========================================================

def render_production():
    page_header(
        "Production Runs",
        "Record ABT and TRASIS production activity",
    )

    hospital_id = get_site_id()

    run_date = st.date_input(
        "Run Date",
        value=date.today(),
        key="production_run_date",
    )

    try:
        summaries = fetch_data(
            "daily_hospital_summaries",
            "id,hospital_site_id,event_date",
        )

    except Exception as exc:
        st.error(
            f"Unable to load production information: {exc}"
        )
        return

    summary_id = None

    for row in summaries:
        if (
            row.get("hospital_site_id") == hospital_id
            and str(row.get("event_date")) == run_date.isoformat()
        ):
            summary_id = row.get("id")
            break

    if summary_id is None:
        st.warning(
            "No Daily Summary exists for this date. Go to Daily Summary and save it before recording production runs."
        )

    with st.form("production_run_form"):
        machine = st.selectbox(
            "Machine",
            ["ABT", "TRASIS"],
        )

        run_number = st.number_input(
            "Run Number",
            min_value=1,
            value=1,
            step=1,
        )

        activity_mci = st.number_input(
            "Activity Produced / Received (mCi)",
            min_value=0.0,
            value=0.0,
            step=0.1,
        )

        outcome = st.selectbox(
            "Outcome",
            [
                "SUCCESSFUL",
                "OPERATOR_MISHANDLING",
                "CARD_FAULTY",
                "EQUIPMENT_FAULT",
                "OTHER",
            ],
        )

        activity_lost = st.number_input(
            "Activity Lost (mCi)",
            min_value=0.0,
            value=0.0,
            step=0.1,
        )

        notes = st.text_area(
            "Notes",
            placeholder="Optional",
        )

        submitted = st.form_submit_button(
            "Record Production Run",
            use_container_width=True,
            disabled=summary_id is None,
        )

    if submitted:
        if activity_lost > activity_mci:
            st.error(
                "Activity lost cannot be greater than the activity produced/received."
            )
            return

        try:
            supabase = get_authenticated_client()

            supabase.rpc(
                "record_production_run",
                {
                    "p_daily_summary_id": summary_id,
                    "p_machine": machine,
                    "p_kit_id": None,
                    "p_run_number": int(run_number),
                    "p_activity_mci": float(activity_mci),
                    "p_outcome": outcome,
                    "p_activity_lost_mci": float(activity_lost),
                    "p_notes": notes.strip() or None,
                },
            ).execute()

            st.success(
                f"{machine} Run #{int(run_number)} recorded successfully."
            )
            st.rerun()

        except Exception as exc:
            from utils.errors import friendly_error

            st.error(
                friendly_error(exc)
            )


# =========================================================
# REPORT KIT COMPONENT ISSUE
# =========================================================

def render_report_issue():
    page_header(
        "Report Kit Component Issue",
        "Report a defective component and the number of affected runs",
    )

    hospital_id = get_site_id()

    try:
        inventory = fetch_data(
            "hospital_inventory"
        )

    except Exception as exc:
        st.error(
            f"Unable to load hospital inventory: {exc}"
        )
        return

    available_kits = [
        row for row in inventory
        if row.get("site_id") == hospital_id
        and row.get("status") == "HOSPITAL_AVAILABLE"
    ]

    if not available_kits:
        st.info(
            "No available kits can currently have an issue reported."
        )
        return

    kit_lookup = {
        (
            f'{row["kit_id"]} — '
            f'{row["kit_type"]}'
        ):
        row

        for row in available_kits
    }

    selected_label = st.selectbox(
        "Kit ID",
        list(kit_lookup.keys()),
    )

    selected_kit = kit_lookup[
        selected_label
    ]

    kit_pk = selected_kit["kit_pk"]

    st.info(
        f'Kit Type: {selected_kit["kit_type"]}  |  '
        f'Total Runs: {selected_kit.get("total_runs", 0)}  |  '
        f'Used: {selected_kit.get("runs_used", 0)}  |  '
        f'Remaining: {selected_kit.get("runs_remaining", 0)}'
    )

    try:
        supabase = get_authenticated_client()

        physical_components = (
            supabase
            .table("kit_components")
            .select(
                "id,template_component_id,status,"
                "template_components("
                "component_name,catalogue_number)"
            )
            .eq("kit_id", kit_pk)
            .execute()
        ).data or []

    except Exception as exc:
        st.error(
            f"Unable to load kit components: {exc}"
        )
        return

    if not physical_components:
        st.warning(
            "This inventory item does not have component records."
        )
        return

    component_lookup = {}

    for row in physical_components:
        component = (
            row.get("template_components")
            or {}
        )

        name = component.get(
            "component_name",
            "Unknown Component",
        )

        catalogue = component.get(
            "catalogue_number"
        )

        label = name

        if catalogue:
            label += f" ({catalogue})"

        component_lookup[label] = row["id"]

    remaining_runs = int(
        selected_kit.get(
            "runs_remaining",
            0,
        ) or 0
    )

    if remaining_runs <= 0:
        st.warning(
            "This kit has no remaining runs."
        )
        return

    with st.form("report_kit_issue_form"):
        selected_components = st.multiselect(
            "Defective Component(s)",
            list(component_lookup.keys()),
        )

        runs_affected = st.number_input(
            "Number of Affected Runs",
            min_value=1,
            max_value=remaining_runs,
            value=1,
            step=1,
        )

        issue_date = st.date_input(
            "Issue Date",
            value=date.today(),
        )

        description = st.text_area(
            "Description",
            placeholder=(
                "Describe the component defect "
                "or problem, if needed."
            ),
        )

        submitted = st.form_submit_button(
            "Report Component Issue",
            use_container_width=True,
        )

    if submitted:
        if not selected_components:
            st.error(
                "Select at least one defective component."
            )
            return

        component_ids = [
            component_lookup[label]
            for label in selected_components
        ]

        try:
            supabase = get_authenticated_client()

            supabase.rpc(
                "report_kit_issue",
                {
                    "p_kit_id":
                        kit_pk,

                    "p_event_date":
                        issue_date.isoformat(),

                    "p_runs_affected":
                        int(runs_affected),

                    "p_component_ids":
                        component_ids,

                    "p_description":
                        description.strip() or None,
                },
            ).execute()

            st.success(
                "Kit component issue reported successfully."
            )

            st.rerun()

        except Exception as exc:
            st.error(
                f"Unable to report kit issue: {exc}"
            )


# =========================================================
# ISSUE STATUS
# =========================================================

def render_issues():
    page_header(
        "Kit Issues",
        "Review reported kit and component issues",
    )

    hospital_id = get_site_id()

    try:
        open_rows = fetch_data(
            "open_kit_issues"
        )

        history_rows = fetch_data(
            "kit_issue_history"
        )

    except Exception as exc:
        st.error(
            f"Unable to load issue information: {exc}"
        )
        return

    open_rows = [
        row
        for row in open_rows
        if row.get("hospital_site_id")
        == hospital_id
    ]

    tab1, tab2 = st.tabs(
        [
            "Kits",
            "Components by Kit",
        ]
    )

    with tab1:

        if not open_rows:
            st.success(
                "No open kit issues."
            )

        else:
            grouped = {}

            for row in open_rows:
                issue_id = row.get(
                    "issue_id"
                )

                if issue_id not in grouped:
                    grouped[issue_id] = {
                        "Issue ID":
                            issue_id,

                        "Kit ID":
                            row.get("kit_id"),

                        "Kit Type":
                            row.get("kit_type"),

                        "Issue Date":
                            row.get("event_date"),

                        "Affected Runs":
                            row.get(
                                "runs_affected"
                            ),

                        "Description":
                            row.get(
                                "description"
                            ),
                    }

            df = pd.DataFrame(
                grouped.values()
            )

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

    with tab2:

        if not open_rows:
            st.info(
                "No component issues are currently open."
            )
            return

        kit_ids = sorted(
            {
                row.get("kit_id")
                for row in open_rows
                if row.get("kit_id")
            }
        )

        selected_kit = st.selectbox(
            "Kit ID",
            kit_ids,
            key="hospital_issue_kit_filter",
        )

        filtered = [
            row
            for row in open_rows
            if row.get("kit_id")
            == selected_kit
        ]

        rows = []

        for row in filtered:
            rows.append(
                {
                    "Issue ID":
                        row.get("issue_id"),

                    "Kit ID":
                        row.get("kit_id"),

                    "Kit Type":
                        row.get("kit_type"),

                    "Component":
                        row.get(
                            "component_name"
                        ),

                    "Catalogue Number":
                        row.get(
                            "catalogue_number"
                        ),

                    "Affected Runs":
                        row.get(
                            "runs_affected"
                        ),

                    "Issue Date":
                        row.get(
                            "event_date"
                        ),
                }
            )

        if rows:
            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info(
                "No components are recorded for this kit issue."
            )


# =========================================================
# DOWNTIME
# =========================================================

def render_downtime():
    page_header(
        "Equipment Downtime",
        "Record downtime for hospital equipment",
    )

    hospital_id = get_site_id()

    try:
        equipment = fetch_data(
            "equipment",
            "id,site_id,equipment_name,equipment_type,is_active",
        )

    except Exception as exc:
        st.error(
            f"Unable to load equipment: {exc}"
        )
        return

    equipment = [
        row for row in equipment
        if row.get("site_id") == hospital_id
        and row.get("is_active")
    ]

    if not equipment:
        st.warning(
            "No active equipment is configured for this hospital."
        )
        return

    equipment_lookup = {
        row["equipment_name"]: row["id"]
        for row in equipment
    }

    with st.form("downtime_form"):
        equipment_name = st.selectbox(
            "Equipment",
            list(equipment_lookup.keys()),
        )

        event_date = st.date_input(
            "Date",
            value=date.today(),
        )

        duration = st.number_input(
            "Downtime Duration (minutes)",
            min_value=1,
            value=30,
            step=1,
        )

        reason = st.text_input(
            "Reason",
            placeholder="Equipment fault, maintenance, etc.",
        )

        notes = st.text_area(
            "Notes",
            placeholder="Optional",
        )

        submitted = st.form_submit_button(
            "Record Downtime",
            use_container_width=True,
        )

    if submitted:
        if not reason.strip():
            st.error("Reason is required.")
            return

        try:
            supabase = get_authenticated_client()

            supabase.rpc(
                "record_equipment_downtime",
                {
                    "p_equipment_id":
                        equipment_lookup[equipment_name],

                    "p_event_date":
                        event_date.isoformat(),

                    "p_duration_minutes":
                        int(duration),

                    "p_reason":
                        reason.strip(),

                    "p_notes":
                        notes.strip() or None,
                },
            ).execute()

            st.success(
                "Equipment downtime recorded."
            )

            st.rerun()

        except Exception as exc:
            st.error(
                f"Unable to record downtime: {exc}"
            )


# =========================================================
# EXPIRY
# =========================================================

def render_expiry():
    page_header(
        "Expiry Alerts",
        "Hospital kits and components approaching expiry",
    )

    hospital_id = get_site_id()

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
                if row.get("site_id") == hospital_id
            ]

        except Exception as exc:
            st.error(
                f"Unable to load kit expiry alerts: {exc}"
            )
            return

        if not alerts:
            st.success(
                "No hospital kit expiry alerts."
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
                st.subheader(
                    "Expired Kits Requiring Action"
                )
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

                with st.form("hospital_expire_kit"):
                    selected = st.selectbox(
                        "Expired Kit",
                        list(kit_lookup.keys()),
                    )

                    reason = st.text_area(
                        "Reason / Notes",
                        placeholder="Optional",
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
                    "Expiry warnings are shown above. No kit is at 0 days or less to expiry yet."
                )

    with tab2:
        try:
            alerts = fetch_data(
                "component_expiry_alerts"
            )

            alerts = [
                row for row in alerts
                if row.get("site_id") == hospital_id
            ]

        except Exception as exc:
            st.error(
                f"Unable to load component expiry alerts: {exc}"
            )
            return

        if not alerts:
            st.success(
                "No hospital component expiry alerts."
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
                st.subheader(
                    "Expired Components Requiring Action"
                )

                component_lookup = {}

                for row in expired:
                    label = (
                        f'{row.get("kit_id", "")} — '
                        f'{row.get("component_name", "")}'
                    )

                    component_lookup[label] = row.get("kit_component_id")

                with st.form("hospital_expire_component"):
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
                    "Expiry warnings are shown above. No component is at 0 days or less to expiry yet."
                )


def render_reports():
    page_header(
        "Reports & Analytics",
        "Hospital operational performance",
    )

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

    st.divider()

    c1, c2 = st.columns(2)

    start_date = c1.date_input(
        "From",
        value=date.today().replace(day=1),
        key=f"hospital_report_from_{report}",
    )

    end_date = c2.date_input(
        "To",
        value=date.today(),
        key=f"hospital_report_to_{report}",
    )

    if start_date > end_date:
        st.error("From date cannot be later than To date.")
        return

    if report == "Production Performance":
        show_production_report(None, start_date, end_date)
    elif report == "Patients & Activity":
        show_patient_report(None, start_date, end_date)
    elif report == "Production Failures":
        show_failure_report(None, start_date, end_date)
    elif report == "Equipment Downtime":
        show_downtime_report(None, start_date, end_date)
    elif report == "Kit Usage History":
        show_kit_usage_report(None, start_date, end_date)


# =========================================================
# MAIN ROUTER
# =========================================================

def render():
    require_role("hospital_manager")

    with st.sidebar:
        st.markdown("### Hospital")

        section = st.radio(
            "Navigation",
            [
                "Overview",
                "Confirmation",
                "Hospital Inventory",
                "Daily Summary",
                "Production Runs",
                "Report Kit Component Issue",
                "Kit Issues",
                "Downtime",
                "Expiry Alerts",
                "Reports & Analytics",
            ],
            label_visibility="collapsed",
            key="hospital_navigation",
        )

    if section == "Overview":
        render_overview()

    elif section == "Confirmation":
        render_confirmation()

    elif section == "Hospital Inventory":
        render_inventory()

    elif section == "Daily Summary":
        render_daily_summary()

    elif section == "Production Runs":
        render_production()

    elif section == "Report Kit Component Issue":
        render_report_issue()

    elif section == "Kit Issues":
        render_issues()

    elif section == "Downtime":
        render_downtime()

    elif section == "Reports & Analytics":
        render_reports()

    elif section == "Expiry Alerts":
        render_expiry()
