import streamlit as st

from utils.auth import (
    initialize_session,
    login,
    logout,
)
from utils.ui import (
    apply_light_theme,
    page_header,
)

st.set_page_config(
    page_title="Medicine Manager",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

initialize_session()
apply_light_theme()


def login_page():
    col1, col2, col3 = st.columns([1, 1.15, 1])

    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)

        page_header(
            "Medicine Manager",
            "Operational inventory and production management",
        )

        with st.form("login_form"):
            email = st.text_input(
                "Email",
                placeholder="name@example.com",
            )

            password = st.text_input(
                "Password",
                type="password",
            )

            submitted = st.form_submit_button(
                "Sign in",
                use_container_width=True,
            )

        if submitted:
            if not email or not password:
                st.error(
                    "Enter both your email and password."
                )

            else:
                try:
                    login(email, password)

                    st.success("Signed in successfully.")
                    st.rerun()

                except Exception as exc:
                    st.error(
                        f"Unable to sign in: {exc}"
                    )


def authenticated_app():
    profile = st.session_state.profile

    role = profile.get("role")
    name = profile.get("full_name") or st.session_state.email

    with st.sidebar:
        st.markdown("## Medicine Manager")

        st.markdown(
            f"""
            <div class="user-box">
                <strong>{name}</strong><br>
                <small>{role.replace("_", " ").title()}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            "Sign out",
            use_container_width=True,
        ):
            logout()
            st.rerun()

    if role == "admin":
        from pages.admin import render
        render()

    elif role == "warehouse_manager":
        from pages.warehouse import render
        render()

    elif role == "hospital_manager":
        from pages.hospital import render
        render()

    else:
        st.error(
            "Your account has an invalid application role."
        )


if not st.session_state.authenticated:
    login_page()

else:
    authenticated_app()
