import streamlit as st
from datetime import datetime


def render_feedback(item_id: str):
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("👍 도움됨", key=f"up_{item_id}", use_container_width=True):
            _save_feedback(item_id, 1, None)
            st.toast("피드백 감사합니다! 👍")
    with col2:
        if st.button("👎 아쉬움", key=f"down_{item_id}", use_container_width=True):
            _save_feedback(item_id, -1, "부정적")
            st.toast("피드백 감사합니다!")


def _save_feedback(item_id: str, rating: int, reason: str | None):
    fb_list = st.session_state.setdefault("feedbacks", [])
    fb_list.append(
        {
            "item_id": item_id,
            "rating": rating,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
    )
