import streamlit as st
from supabase import create_client


def get_supabase():
    """
    Create a Supabase client using Streamlit secrets.

    The app must use the public/anon/publishable key,
    never the Supabase service-role key.
    """

    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]

    except Exception as exc:
        raise RuntimeError(
            "Supabase configuration is missing. "
            "Add SUPABASE_URL and SUPABASE_KEY to Streamlit Cloud Secrets."
        ) from exc

    return create_client(url, key)
