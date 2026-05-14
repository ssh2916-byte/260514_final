import streamlit as st

from core.llm import call_llm
from pipelines.risk.collector import RawFeedItem

_SYSTEM = "당신은 IT 운영자를 위한 보안 리스크 분석가입니다. 한국어로 답변하세요."

_PROMPT_DETAIL = """
아래 수집된 보안·장애 공지를 분석해 오늘의 리스크를 요약하세요.

[회사 IT 환경]
{company_context}

[수집 항목 ({count}건)]
{feed_items}

출력 형식:
## 오늘의 핵심 리스크 (우선순위 순)
### 1. [리스크명] — 심각도: Critical/High/Medium
- **영향 범위**: ...
- **조치 권고**: ...
- **참고**: [링크]

## 종합 평가
[전반적인 리스크 수준 평가]

## Critical 항목 여부
- Critical: 있음/없음
"""

_PROMPT_SIMPLE = """
아래 수집된 보안·장애 공지를 간단히 요약하세요.

[회사 IT 환경]
{company_context}

[수집 항목 ({count}건)]
{feed_items}

출력 형식:
## 핵심 리스크 요약 (Top 3)
1. [리스크명] (심각도: Critical/High/Medium) — 한 줄 설명
2. ...
3. ...

## Critical 항목 여부
- Critical: 있음/없음
"""


class LLMSummarizer:
    def summarize(self, items: list[RawFeedItem], company_ctx: str, detail: bool = True) -> str:
        template = _PROMPT_DETAIL if detail else _PROMPT_SIMPLE
        feed_text = "\n".join(
            f"- [{i.source}] {i.title} (CVSS: {i.cvss_score}, 심각도: {i.severity})\n  {i.summary[:200]}"
            for i in items
        )
        prompt = template.format(
            company_context=company_ctx,
            count=len(items),
            feed_items=feed_text,
        )
        stream = call_llm(prompt, _SYSTEM, stream=True)
        return st.write_stream(stream)
