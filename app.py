"""Deprecated Streamlit entrypoint shim.

This file is kept only to provide a clear migration path for anyone still
trying to launch the historical Streamlit UI.
"""

from __future__ import annotations

DEPRECATION_MESSAGE = """
The legacy Streamlit entry has been retired.

Please start Self Manager with the FastAPI application instead:

    python -m uvicorn main:app --reload
""".strip()


def main() -> None:
    try:
        import streamlit as st  # type: ignore
    except ImportError:
        print(DEPRECATION_MESSAGE)
        return

    st.set_page_config(page_title="Self Manager Entry Retired", page_icon="⚠️", layout="centered")
    st.warning("历史 Streamlit 入口已废弃。")
    st.code("python -m uvicorn main:app --reload", language="powershell")
    st.info("当前主开发链路是 FastAPI + frontend/。")


main()
