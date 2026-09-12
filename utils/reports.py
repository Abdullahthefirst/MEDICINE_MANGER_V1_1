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

    if "event_date" in df.columns:
        df["event_date"] = pd.to_datetime(
            df["event_date"]
        )

    if "machine" not in df.columns:
        st.error(
            "Production data does not contain the machine field."
        )
        return

    abt_df = df[
        df["machine"].astype(str).str.upper() == "ABT"
    ].copy()

    trasis_df = df[
        df["machine"].astype(str).str.upper() == "TRASIS"
    ].copy()

    tab1, tab2 = st.tabs(
        [
            "ABT",
            "TRASIS",
        ]
    )

    with tab1:
        st.subheader("ABT Performance")

        if abt_df.empty:
            st.info(
                "No ABT production data available."
            )

        else:
            total_runs = (
                abt_df["total_runs"].sum()
                if "total_runs" in abt_df.columns
                else 0
            )

            successful_runs = (
                abt_df["successful_runs"].sum()
                if "successful_runs" in abt_df.columns
                else 0
            )

            failed_runs = (
                abt_df["failed_runs"].sum()
                if "failed_runs" in abt_df.columns
                else 0
            )

            total_activity = (
                abt_df["total_activity_mci"].sum()
                if "total_activity_mci" in abt_df.columns
                else 0
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "ABT Total Runs",
                int(total_runs),
            )

            c2.metric(
                "ABT Successful Runs",
                int(successful_runs),
            )

            c3.metric(
                "ABT Failed Runs",
                int(failed_runs),
            )

            c4.metric(
                "ABT Total Activity",
                f"{float(total_activity):.2f} mCi",
            )

            if (
                "event_date" in abt_df.columns
                and "total_runs" in abt_df.columns
            ):
                abt_trend = (
                    abt_df.groupby(
                        "event_date",
                        as_index=False,
                    )["total_runs"].sum()
                )

                st.line_chart(
                    abt_trend,
                    x="event_date",
                    y="total_runs",
                )

            st.dataframe(
                abt_df,
                use_container_width=True,
                hide_index=True,
            )

    with tab2:
        st.subheader("TRASIS Performance")

        if trasis_df.empty:
            st.info(
                "No TRASIS production data available."
            )

        else:
            total_runs = (
                trasis_df["total_runs"].sum()
                if "total_runs" in trasis_df.columns
                else 0
            )

            successful_runs = (
                trasis_df["successful_runs"].sum()
                if "successful_runs" in trasis_df.columns
                else 0
            )

            failed_runs = (
                trasis_df["failed_runs"].sum()
                if "failed_runs" in trasis_df.columns
                else 0
            )

            total_activity = (
                trasis_df["total_activity_mci"].sum()
                if "total_activity_mci" in trasis_df.columns
                else 0
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "TRASIS Total Runs",
                int(total_runs),
            )

            c2.metric(
                "TRASIS Successful Runs",
                int(successful_runs),
            )

            c3.metric(
                "TRASIS Failed Runs",
                int(failed_runs),
            )

            c4.metric(
                "TRASIS Total Activity",
                f"{float(total_activity):.2f} mCi",
            )

            if (
                "event_date" in trasis_df.columns
                and "total_runs" in trasis_df.columns
            ):
                trasis_trend = (
                    trasis_df.groupby(
                        "event_date",
                        as_index=False,
                    )["total_runs"].sum()
                )

                st.line_chart(
                    trasis_trend,
                    x="event_date",
                    y="total_runs",
                )

            st.dataframe(
                trasis_df,
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
    st.subheader("Kit Usage History")

    try:
        usage = fetch_data(
            "kit_usage",
            "id,event_date,runs_used,kit_id,"
            "daily_summary_id,created_at",
        )

        kits = fetch_data(
            "kits",
            "id,kit_id,template_id,site_id,status",
        )

        templates = fetch_data(
            "inventory_templates",
            "id,name",
        )

        summaries = fetch_data(
            "daily_hospital_summaries",
            "id,hospital_site_id,event_date",
        )

        sites = fetch_data(
            "sites",
            "id,name",
        )

    except Exception as exc:
        st.error(
            f"Unable to load Kit Consumption report: {exc}"
        )
        return

    if not usage:
        st.info(
            "No kit usage has been recorded yet."
        )
        return

    template_lookup = {
        row["id"]: row["name"]
        for row in templates
    }

    site_lookup = {
        row["id"]: row["name"]
        for row in sites
    }

    kit_lookup = {
        row["id"]: row
        for row in kits
    }

    summary_lookup = {
        row["id"]: row
        for row in summaries
    }

    rows = []

    for record in usage:
        summary = summary_lookup.get(
            record.get("daily_summary_id")
        )

        if not summary:
            continue

        if get_role() == "hospital_manager":
            if summary.get("hospital_site_id") != get_site_id():
                continue

        kit = kit_lookup.get(record.get("kit_id"))

        if not kit:
            continue

        rows.append(
            {
                "Date": record.get("event_date"),
                "Hospital": site_lookup.get(
                    summary.get("hospital_site_id"),
                    "Unknown",
                ),
                "Kit ID": kit.get("kit_id"),
                "Kit Type": template_lookup.get(
                    kit.get("template_id"),
                    "Unknown",
                ),
                "Runs Used": record.get("runs_used", 0),
            }
        )

    if not rows:
        st.info(
            "No kit consumption records are available for your account."
        )
        return

    df = pd.DataFrame(rows)

    total_runs = int(df["Runs Used"].sum())
    unique_kits = df["Kit ID"].dropna().nunique()

    c1, c2 = st.columns(2)
    c1.metric("Total Runs Used", total_runs)
    c2.metric("Kits Used", unique_kits)

    by_type = (
        df.groupby("Kit Type", as_index=False)["Runs Used"]
        .sum()
    )

    st.bar_chart(
        by_type,
        x="Kit Type",
        y="Runs Used",
    )

    st.dataframe(
        df.sort_values("Date", ascending=False),
        use_container_width=True,
        hide_index=True,
    )
