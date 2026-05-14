from unittest.mock import patch

from pipelines.risk.collector import RawFeedItem
from pipelines.risk.rule_filter import RuleFilter


def _make_item(title="Test", cvss=None, severity="Unknown", summary=""):
    return RawFeedItem(
        source="test",
        title=title,
        url="http://example.com",
        summary=summary,
        published="2026-01-01",
        cvss_score=cvss,
        severity=severity,
    )


@patch("pipelines.risk.rule_filter.st")
def test_cvss_threshold(mock_st):
    mock_st.session_state = {"filter_config": {"min_cvss": 7.0}}
    items = [_make_item(cvss=9.8, severity="Critical"), _make_item(cvss=5.0, severity="Medium")]
    result = RuleFilter().apply(items)
    assert len(result) == 1
    assert result[0].cvss_score == 9.8


@patch("pipelines.risk.rule_filter.st")
def test_blacklist_excludes(mock_st):
    mock_st.session_state = {
        "filter_config": {"min_cvss": 0.0, "blacklist_keywords": ["spam"], "whitelist_keywords": []}
    }
    items = [_make_item(title="spam alert", cvss=9.0), _make_item(title="real alert", cvss=9.0)]
    result = RuleFilter().apply(items)
    assert len(result) == 1
    assert result[0].title == "real alert"


@patch("pipelines.risk.rule_filter.st")
def test_no_cvss_included(mock_st):
    mock_st.session_state = {"filter_config": {"min_cvss": 7.0, "whitelist_keywords": [], "blacklist_keywords": []}}
    items = [_make_item(cvss=None)]
    result = RuleFilter().apply(items)
    assert len(result) == 1
