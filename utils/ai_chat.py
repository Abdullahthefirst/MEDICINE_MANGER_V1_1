import json
import re
import streamlit as st

from google import genai

from utils.auth import (
    get_authenticated_client,
)

GEMINI_MODEL = "gemini-3.6-flash"

SOURCE_RULES = {
    "inventory": [
        "inventory",
        "stock",
        "kit",
        "kits",
        "available",
        "expiry",
        "expire",
    ],

    "production": [
        "production",
        "abt",
        "trasis",
        "mci",
        "activity",
        "run",
        "runs",
        "failure",
    ],

    "downtime": [
        "downtime",
        "equipment",
        "fault",
        "maintenance",
        "machine",
    ],

    "issues": [
        "issue",
        "issues",
        "component",
        "defect",
        "replacement",
    ],

    "patients": [
        "patient",
        "patients",
        "served",
        "efficiency",
    ],

    "transfers": [
        "transfer",
        "transfers",
        "warehouse",
        "received",
        "shipment",
    ],
}

SOURCE_TABLES = {
    "inventory": [
        "current_inventory",
        "expiry_dashboard_summary",
    ],

    "production": [
        "daily_production_summary",
        "production_failures",
    ],

    "downtime": [
        "downtime_report",
        "monthly_downtime_summary",
    ],

    "issues": [
        "kit_issue_component_status",
        "kit_issue_history",
    ],

    "patients": [
        "daily_efficiency_metrics",
    ],

    "transfers": [
        "pending_transfers",
    ],
}


def _question_tokens(question):
    return set(re.findall(r"[a-zA-Z0-9_-]+", question.lower()))


def _select_sources(question):
    question_lower = question.lower()
    selected = []

    for category, words in SOURCE_RULES.items():
        if any(word in question_lower for word in words):
            selected.append(category)

    if not selected:
        selected = ["inventory", "production", "downtime", "issues", "patients"]

    return selected


def _row_score(row, tokens):
    text = json.dumps(row, default=str).lower()
    return sum(1 for token in tokens if token in text)


def retrieve_context(question):
    supabase = get_authenticated_client()
    categories = _select_sources(question)

    tables = []
    for category in categories:
        tables.extend(SOURCE_TABLES[category])

    tables = list(dict.fromkeys(tables))
    tokens = _question_tokens(question)
    context = {}

    for table in tables:
        try:
            response = supabase.table(table).select("*").limit(150).execute()
            rows = response.data or []
        except Exception:
            continue

        if not rows:
            continue

        ranked = sorted(rows, key=lambda row: _row_score(row, tokens), reverse=True)
        context[table] = ranked[:30]

    return context


def ask_gemini(api_key, question):
    context = retrieve_context(question)

    if not context:
        return "I could not retrieve relevant operational records for this question."

    client = genai.Client(api_key=api_key)

    prompt = f"""
You are the read-only operational AI assistant
for Medicine Manager.

Answer the administrator's question using ONLY
the supplied operational records.

Rules:
- Never invent records, totals, sites, dates, or causes.
- If the supplied data is insufficient, say so.
- Distinguish ABT from TRASIS.
- Mention the date range when the records make it clear.
- Do not expose internal database IDs unless necessary.
- Do not provide instructions to modify the database.
- Be concise but useful.
- Where appropriate, explain which records support the conclusion.

ADMIN QUESTION:
{question}

RETRIEVED OPERATIONAL CONTEXT:
{json.dumps(context, default=str)}
"""

    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return response.text
