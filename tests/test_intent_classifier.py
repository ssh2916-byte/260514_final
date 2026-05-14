from unittest.mock import patch

from agents.intent_classifier import IntentClassifier


@patch("agents.intent_classifier.call_llm")
def test_sap_intent(mock_llm):
    mock_llm.return_value = '{"intent": "sap_qa", "confidence": 0.95, "reason": "SAP 오류"}'
    result = IntentClassifier().classify("SM21 오류 해결법")
    assert result.intent == "sap_qa"
    assert result.confidence == 0.95


@patch("agents.intent_classifier.call_llm")
def test_risk_intent(mock_llm):
    mock_llm.return_value = '{"intent": "risk_query", "confidence": 0.9, "reason": "CVE"}'
    result = IntentClassifier().classify("CVE-2024-1234 패치 필요한가요?")
    assert result.intent == "risk_query"


@patch("agents.intent_classifier.call_llm")
def test_fallback_on_invalid_json(mock_llm):
    mock_llm.return_value = "분류 불가"
    result = IntentClassifier().classify("아무말")
    assert result.intent == "other"
    assert result.confidence == 0.0
