import pandas as pd
import streamlit as st

from utils.auth import (
    get_authenticated_client,
    get_role,
    get_site_id,
)


def fetch_data(table, columns="*"):
    supabase = get_authenticated_client()

    response = (
        supabase
        .table(table)
        .select(columns)
        .execute()
    )

    return response.data or []


def get_filtered_hospital_data(table):
    data = fetch_data(table)

    role = get_role()

    if role == "hospital_manager":
        site_id = get_site_id()

        data = [
            row for row in data
            if row.get("hospital_site_id") == site_id
        ]

    return data


def show_production_report():
    st.subheader("Production Performance")

    try:
        data = get_filtered_hospital_data(
            "daily_production_summary"
        )

    except Exception as exc:
        st.error(
            f"Unable to load production report: {exc}"
        )
        return

    if not data:
        st.info("No production data available.")
        return

    df = pd.DataFrame(data)

    total_runs = (
        df["total_runs"].sum()
        if "total_runs" in df.columns
        else 0
    )

    successful_runs = (
        df["successful_runs"].sum()
        if "successful_runs" in df.columns
        else 0
    )

    failed_runs = (
        df["failed_runs"].sum()
        if "failed_runs" in df.columns
        else 0
    )

    total_activity = (
        df["total_activity_mci"].sum()
        if "total_activity_mci" in df.columns
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Runs", int(total_runs))
    c2.metric("Successful Runs", int(successful_runs))
    c3.metric("Failed Runs", int(failed_runs))
    c4.metric(
        "Total Activity",
        f"{float(total_activity):.2f} mCi",
    )

    if "event_date" in df.columns:
        df["event_date"] = pd.to_datetime(
            df["event_date"]
        )

    if (
        "event_date" in df.columns
        and "total_runs" in df.columns
    ):
        trend = (
            df.groupby("event_date")["total_runs"]
            .sum()
            .reset_index()
        )

        st.line_chart(
            trend,
            x="event_date",
            y="total_runs",
        )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def show_patient_report():
    st.subheader("Patients & Activity")

    try:
        data = fetch_data(
            "daily_efficiency_metrics"
        )

    except Exception as exc:
        st.error(
            f"Unable to load patient report: {exc}"
        )
        return

    if get_role() == "hospital_manager":
        site_id = get_site_id()

        data = [
            row for row in data
            if row.get("hospital_site_id") == site_id
        ]

    if not data:
        st.info(
            "No patient performance data available."
        )
        return

    df = pd.DataFrame(data)

    total_patients = (
        df["total_patients"].sum()
        if "total_patients" in df.columns
        else 0
    )

    total_activity = (
        df["total_activity_mci"].sum()
        if "total_activity_mci" in df.columns
        else 0
    )

    abt_patients = (
        df["abt_patients"].sum()
        if "abt_patients" in df.columns
        else 0
    )

    trasis_patients = (
        df["trasis_patients"].sum()
        if "trasis_patients" in df.columns
        else 0
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Total Patients",
        int(total_patients),
    )

    c2.metric(
        "ABT Patients",
        int(abt_patients),
    )

    c3.metric(
        "TRASIS Patients",
        int(trasis_patients),
    )

    if total_patients > 0:
        avg_mci = total_activity / total_patients
    else:
        avg_mci = 0

    c4.metric(
        "Average mCi / Patient",
        f"{avg_mci:.2f}",
    )

    if "event_date" in df.columns:
        df["event_date"] = pd.to_datetime(
            df["event_date"]
        )

        trend = (
            df.groupby("event_date")[
                [
                    "abt_patients",
                    "trasis_patients",
                ]
            ]
            .sum()
            .reset_index()
        )

        st.line_chart(
            trend,
            x="event_date",
            y=[
                "abt_patients",
                "trasis_patients",
            ],
        )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def show_failure_report():
    st.subheader("Production Failures")

    try:
        data = fetch_data(
            "production_failures"
        )

    except Exception as exc:
        st.error(
            f"Unable to load failure report: {exc}"
        )
        return

    if get_role() == "hospital_manager":
        site_id = get_site_id()

        data = [
            row for row in data
            if row.get("hospital_site_id") == site_id
        ]

    if not data:
        st.success(
            "No production failures recorded."
        )
        return

    df = pd.DataFrame(data)

    if "outcome" in df.columns:
        counts = (
            df["outcome"]
            .value_counts()
            .reset_index()
        )

        counts.columns = [
            "Failure Type",
            "Count",
        ]

        st.bar_chart(
            counts,
            x="Failure Type",
            y="Count",
        )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def show_downtime_report():
    st.subheader("Equipment Downtime")

    try:
        data = fetch_data(
            "downtime_report"
        )

    except Exception as exc:
        st.error(
            f"Unable to load downtime report: {exc}"
        )
        return

    if get_role() == "hospital_manager":
        site_id = get_site_id()

        data = [
            row for row in data
            if row.get("hospital_site_id") == site_id
        ]

    if not data:
        st.info(
            "No downtime data available."
        )
        return

    df = pd.DataFrame(data)

    total_minutes = (
        df["duration_minutes"].sum()
        if "duration_minutes" in df.columns
        else 0
    )

    total_hours = total_minutes / 60

    c1, c2 = st.columns(2)

    c1.metric(
        "Downtime Events",
        len(df),
    )

    c2.metric(
        "Total Downtime",
        f"{total_hours:.2f} hours",
    )

    if "equipment_name" in df.columns:
        by_equipment = (
            df.groupby("equipment_name")[
                "duration_minutes"
            ]
            .sum()
            .reset_index()
        )

        st.bar_chart(
            by_equipment,
            x="equipment_name",
            y="duration_minutes",
        )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


def show_kit_usage_report():
    st.subheader("Kit Consumption")

    try:
        data = fetch_data(
            "kit_usage",
            "id,event_date,runs_used,kit_id,"
            "daily_summary_id,created_at",
        )

        kits = fetch_data(
            "kit_traceability"
        )

    except Exception as exc:
        st.error(
            f"Unable to load kit usage report: {exc}"
        )
        return

    if not data:
        st.info("No kit usage records available.")
        return

    kit_map = {
        row["kit_pk"]: {
            "kit_id": row.get("kit_id"),
            "kit_type": row.get("kit_type"),
            "current_site": row.get("current_site"),
        }
        for row in kits
    }

    rows = []

    for row in data:
        info = kit_map.get(
            row.get("kit_id"),
            {},
        )

        rows.append(
            {
                "event_date": row.get(
                    "event_date"
                ),
                "kit_id": info.get(
                    "kit_id"
                ),
                "kit_type": info.get(
                    "kit_type"
                ),
                "site": info.get(
                    "current_site"
                ),
                "runs_used": row.get(
                    "runs_used"
                ),
            }
        )

    df = pd.DataFrame(rows)

    if get_role() == "hospital_manager":
        hospital_id = get_site_id()

        try:
            summaries = fetch_data(
                "daily_hospital_summaries",
                "id,hospital_site_id",
            )

            permitted_summary_ids = {
                row["id"]
                for row in summaries
                if row.get("hospital_site_id")
                == hospital_id
            }

            original = pd.DataFrame(data)

            allowed_usage_ids = set(
                original[
                    original["daily_summary_id"]
                    .isin(permitted_summary_ids)
                ]["id"]
            )

            if allowed_usage_ids:
                df = df.iloc[
                    [
                        i
                        for i, row
                        in enumerate(data)
                        if row["id"]
                        in allowed_usage_ids
                    ]
                ]

        except Exception:
            pass

    total_runs_used = (
        df["runs_used"].sum()
        if "runs_used" in df.columns
        else 0
    )

    c1, c2 = st.columns(2)

    c1.metric(
        "Usage Transactions",
        len(df),
    )

    c2.metric(
        "Total Runs Used",
        int(total_runs_used),
    )

    if (
        "kit_type" in df.columns
        and not df.empty
    ):
        by_type = (
            df.groupby("kit_type")[
                "runs_used"
            ]
            .sum()
            .reset_index()
        )

        st.bar_chart(
            by_type,
            x="kit_type",
            y="runs_used",
        )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )
