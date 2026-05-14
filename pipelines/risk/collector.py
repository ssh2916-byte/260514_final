import re
from datetime import datetime

import feedparser
import httpx
import streamlit as st
from pydantic import BaseModel

SOURCES = [
    {
        "name": "NVD CVE",
        "url": "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss-analyzed.xml",
        "type": "rss",
    },
    {
        "name": "CISA KEV",
        "url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        "type": "json",
    },
    {
        "name": "KrCERT",
        "url": "https://www.krcert.or.kr/rss/vulnerability.do",
        "type": "rss",
    },
    {
        "name": "AWS Status",
        "url": "https://status.aws.amazon.com/rss/all.rss",
        "type": "rss",
    },
    {
        "name": "The Hacker News",
        "url": "https://feeds.feedburner.com/TheHackersNews",
        "type": "rss",
    },
]

_CVSS_RE = re.compile(r"(?:CVSS|cvss)[:\s]+([0-9]+\.[0-9]+)", re.IGNORECASE)


class RawFeedItem(BaseModel):
    source: str
    title: str
    url: str
    summary: str
    published: str
    cvss_score: float | None = None
    severity: str = "Unknown"


def _extract_cvss(text: str) -> float | None:
    m = _CVSS_RE.search(text)
    return float(m.group(1)) if m else None


def _cvss_to_severity(score: float | None) -> str:
    if score is None:
        return "Unknown"
    if score >= 9.0:
        return "Critical"
    if score >= 7.0:
        return "High"
    if score >= 4.0:
        return "Medium"
    return "Low"


class FeedCollector:
    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def collect_all(self, progress_callback=None) -> list[RawFeedItem]:
        items: list[RawFeedItem] = []
        total = len(SOURCES)
        for idx, src in enumerate(SOURCES):
            if progress_callback:
                progress_callback(idx / total, f"{src['name']} 수집 중...")
            try:
                items.extend(self._collect_one(src))
            except Exception as e:
                st.warning(f"[{src['name']}] 수집 실패: {e}")
        if progress_callback:
            progress_callback(1.0, "수집 완료")
        return items

    def _collect_one(self, src: dict) -> list[RawFeedItem]:
        if src["type"] == "rss":
            return self._parse_rss(src)
        if src["type"] == "json":
            return self._parse_cisa_json(src)
        return []

    def _parse_rss(self, src: dict) -> list[RawFeedItem]:
        feed = feedparser.parse(src["url"])
        result = []
        for entry in feed.entries[:20]:
            title = entry.get("title", "")
            url = entry.get("link", "")
            summary = entry.get("summary", "")
            published = entry.get("published", datetime.now().isoformat())
            cvss = _extract_cvss(summary) or _extract_cvss(title)
            result.append(
                RawFeedItem(
                    source=src["name"],
                    title=title,
                    url=url,
                    summary=summary[:500],
                    published=published,
                    cvss_score=cvss,
                    severity=_cvss_to_severity(cvss),
                )
            )
        return result

    def _parse_cisa_json(self, src: dict) -> list[RawFeedItem]:
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(src["url"])
            resp.raise_for_status()
            data = resp.json()
        result = []
        for v in data.get("vulnerabilities", [])[:20]:
            raw_cvss = v.get("cvssScore")
            cvss = None
            if raw_cvss:
                try:
                    cvss = float(raw_cvss)
                except (ValueError, TypeError):
                    pass
            result.append(
                RawFeedItem(
                    source=src["name"],
                    title=f"[CISA KEV] {v.get('vulnerabilityName', '')}",
                    url=v.get("vendorProject", ""),
                    summary=v.get("shortDescription", "")[:500],
                    published=v.get("dateAdded", datetime.now().isoformat()),
                    cvss_score=cvss,
                    severity=_cvss_to_severity(cvss),
                )
            )
        return result
