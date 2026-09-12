import streamlit as st

from utils.supabase_client import get_supabase


def initialize_session():
    defaults = {
        "authenticated": False,
        "user_id": None,
        "email": None,
        "access_token": None,
        "refresh_token": None,
        "profile": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def login(email: str, password: str):
    supabase = get_supabase()

    response = supabase.auth.sign_in_with_password(
        {
            "email": email.strip(),
            "password": password,
        }
    )

    if response.user is None or response.session is None:
        raise RuntimeError("Unable to sign in.")

    user = response.user
    session = response.session

    profile_response = (
        supabase
        .table("profiles")
        .select("id, full_name, role, site_id, is_active")
        .eq("id", user.id)
        .single()
        .execute()
    )

    profile = profile_response.data

    if not profile:
        try:
            supabase.auth.sign_out()
        except Exception:
            pass

        raise RuntimeError(
            "Your account does not have an application profile."
        )

    if not profile.get("is_active", False):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass

        raise RuntimeError(
            "Your application account is inactive."
        )

    st.session_state.authenticated = True
    st.session_state.user_id = str(user.id)
    st.session_state.email = user.email
    st.session_state.access_token = session.access_token
    st.session_state.refresh_token = session.refresh_token
    st.session_state.profile = profile

    return profile


def get_authenticated_client():
    """
    Return a Supabase client authenticated as the current user.

    This is important because PostgreSQL RLS uses the user's JWT.
    """

    if not st.session_state.get("authenticated"):
        raise RuntimeError("Authentication required.")

    access_token = st.session_state.get("access_token")
    refresh_token = st.session_state.get("refresh_token")

    if not access_token or not refresh_token:
        logout()
        raise RuntimeError("Your session has expired.")

    supabase = get_supabase()

    try:
        supabase.auth.set_session(
            access_token,
            refresh_token,
        )
    except Exception:
        logout()
        raise RuntimeError(
            "Your session has expired. Please sign in again."
        )

    return supabase


def logout():
    try:
        supabase = get_supabase()

        access_token = st.session_state.get("access_token")
        refresh_token = st.session_state.get("refresh_token")

        if access_token and refresh_token:
            try:
                supabase.auth.set_session(
                    access_token,
                    refresh_token,
                )
            except Exception:
                pass

        try:
            supabase.auth.sign_out()
        except Exception:
            pass

    finally:
        keys = [
            "authenticated",
            "user_id",
            "email",
            "access_token",
            "refresh_token",
            "profile",
        ]

        for key in keys:
            if key in st.session_state:
                del st.session_state[key]

        initialize_session()


def require_authentication():
    initialize_session()

    if not st.session_state.authenticated:
        st.warning("Please sign in to continue.")
        st.stop()


def get_profile():
    require_authentication()
    return st.session_state.profile


def get_role():
    profile = get_profile()
    return profile.get("role")


def get_site_id():
    profile = get_profile()
    return profile.get("site_id")


def require_role(*allowed_roles):
    require_authentication()

    role = get_role()

    if role not in allowed_roles:
        st.error(
            "You do not have permission to access this page."
        )
        st.stop()
