import streamlit as st
from datetime import datetime


def init_session_state():
    defaults: dict = {
        "chat_history": [],
        "briefing_history": [],
        "feedbacks": [],
        "routing_logs": [],
        "seen_hashes": set(),
        "filter_config": {
            "min_cvss": 7.0,
            "whitelist_keywords": [],
            "blacklist_keywords": [],
        },
        "company_context": {},
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def add_chat_message(role: str, content: str, msg_id: str = None):
    if msg_id is None:
        msg_id = f"{role}_{datetime.now().timestamp()}"
    st.session_state["chat_history"].append(
        {
            "role": role,
            "content": content,
            "id": msg_id,
            "timestamp": datetime.now().isoformat(),
        }
    )


def save_briefing(content: str):
    st.session_state["briefing_history"].append(
        {
            "content": content,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


def get_chat_history_markdown() -> str:
    lines = []
    for msg in st.session_state.get("chat_history", []):
        role = "사용자" if msg["role"] == "user" else "에이전트"
        lines.append(f"### {role} ({msg.get('timestamp', '')})")
        lines.append(msg["content"])
        lines.append("")
    return "\n".join(lines)
