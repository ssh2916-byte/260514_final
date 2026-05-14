import streamlit as st

from pipelines.risk.collector import RawFeedItem


class RuleFilter:
    def apply(self, items: list[RawFeedItem]) -> list[RawFeedItem]:
        cfg = st.session_state.get("filter_config", {})
        min_cvss: float = float(cfg.get("min_cvss", 7.0))
        whitelist: list[str] = [k.strip().lower() for k in cfg.get("whitelist_keywords", []) if k.strip()]
        blacklist: list[str] = [k.strip().lower() for k in cfg.get("blacklist_keywords", []) if k.strip()]

        result = []
        for item in items:
            text = (item.title + " " + item.summary).lower()

            if blacklist and any(kw in text for kw in blacklist):
                continue

            if whitelist:
                if any(kw in text for kw in whitelist):
                    result.append(item)
                continue

            if item.cvss_score is not None:
                if item.cvss_score >= min_cvss:
                    result.append(item)
            else:
                result.append(item)

        return result
