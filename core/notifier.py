import streamlit as st
import httpx


def send_slack(message: str):
    webhook_url = st.session_state.get("slack_webhook_url")
    if not webhook_url:
        return
    try:
        httpx.post(webhook_url, json={"text": message}, timeout=10)
    except Exception as e:
        st.warning(f"Slack 알림 발송 실패: {e}")
