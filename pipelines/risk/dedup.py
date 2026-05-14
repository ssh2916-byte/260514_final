import hashlib

import streamlit as st

from pipelines.risk.collector import RawFeedItem


class DuplicateFilter:
    def filter(self, items: list[RawFeedItem]) -> list[RawFeedItem]:
        seen: set = st.session_state.setdefault("seen_hashes", set())
        result = []
        for item in items:
            h = hashlib.sha256((item.url + item.title).encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                result.append(item)
        return result
