import streamlit as st


def apply_light_theme():
    st.markdown(
        """
        <style>

        :root {
            color-scheme: light;
        }

        html,
        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stApp"] {
            background-color: #f7f9fc !important;
            color: #172033 !important;
        }

        [data-testid="stHeader"] {
            background-color: #f7f9fc !important;
        }

        [data-testid="stSidebar"] {
            background-color: #ffffff !important;
            border-right: 1px solid #e5e7eb;
        }

        h1, h2, h3, h4, h5, h6,
        p, span, label {
            color: #172033;
        }

        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 16px;
        }

        div[data-testid="stForm"] {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 20px;
        }

        div[data-testid="stDataFrame"] {
            background-color: #ffffff;
            border-radius: 12px;
        }

        .main-title {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }

        .subtitle {
            color: #667085;
            margin-bottom: 1.5rem;
        }

        .user-box {
            padding: 12px;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            background: #f8fafc;
            margin-bottom: 12px;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title, subtitle=None):
    st.markdown(
        f'<div class="main-title">{title}</div>',
        unsafe_allow_html=True,
    )

    if subtitle:
        st.markdown(
            f'<div class="subtitle">{subtitle}</div>',
            unsafe_allow_html=True,
        )
