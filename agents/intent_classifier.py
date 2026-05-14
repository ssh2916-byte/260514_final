import json
from dataclasses import dataclass

from core.llm import call_llm

INTENT_SYSTEM = """당신은 IT 에이전트 라우터입니다. 사용자 입력의 의도를 분류하여 JSON으로만 응답하세요.

intent 값:
- sap_qa: SAP 운영/오류코드/T-code/모듈 관련 질문
- risk_query: 보안 취약점/CVE/장애/리스크 관련 질문
- cross: SAP 시스템의 보안/취약점 관련 (둘 다 해당)
- other: 위와 관련 없는 질문

반드시 아래 JSON 형식으로만 응답하세요:
{"intent": "sap_qa", "confidence": 0.95, "reason": "분류 이유"}"""


@dataclass
class IntentResult:
    intent: str  # sap_qa | risk_query | cross | other
    confidence: float
    reason: str


class IntentClassifier:
    def classify(self, query: str) -> IntentResult:
        try:
            raw = call_llm(
                prompt=f"다음 질문의 의도를 분류하세요: {query}",
                system=INTENT_SYSTEM,
                stream=False,
            )
            text = raw.strip()
            # 코드블록 래핑 제거
            if "```" in text:
                parts = text.split("```")
                text = parts[1] if len(parts) > 1 else text
                if text.startswith("json"):
                    text = text[4:]
            data = json.loads(text.strip())
            return IntentResult(
                intent=data.get("intent", "other"),
                confidence=float(data.get("confidence", 0.5)),
                reason=data.get("reason", ""),
            )
        except Exception:
            return IntentResult(intent="other", confidence=0.0, reason="분류 실패")
