import streamlit as st

from core.llm import call_llm
from pipelines.sap.preprocessor import ProcessedQuery

_SYSTEM = """당신은 SAP 운영 전문가입니다.
반드시 제공된 참고 문서를 근거로만 답변하세요.
문서에 없는 내용은 추측하지 말고 "제공된 문서에서 확인할 수 없습니다"라고 명시하세요.
한국어로 답변하세요."""

_PROMPT_WITH_DOCS = """
[참고 문서]
{retrieved_chunks}

[회사 SAP 환경]
{company_context}

[질문]
{user_question}

답변 형식:
## 원인 분석
## 단계별 해결 절차
1. ...
## 관련 T-code / 대체 방법
## 참고 문서
- [URL]
"""

_PROMPT_NO_DOCS = """
[참고 문서 없음 — 인덱싱된 문서에서 관련 내용을 찾지 못했습니다]

[회사 SAP 환경]
{company_context}

[질문]
{user_question}

일반적인 SAP 지식을 바탕으로 답변하세요. 반드시 아래 면책 문구를 답변 첫 줄에 포함하세요:
> ⚠️ 이 답변은 인덱싱된 공식 문서 없이 생성되었습니다. SAP 공식 문서를 별도로 확인하세요.
"""


class RAGGenerator:
    def generate(self, query: ProcessedQuery, retrieved_docs: list[dict], company_ctx: str) -> str:
        if retrieved_docs:
            chunks_text = "\n\n".join(
                f"[문서 {i + 1}]\n{doc['text']}\n출처: {doc.get('meta', {}).get('url', 'N/A')}"
                for i, doc in enumerate(retrieved_docs)
            )
            prompt = _PROMPT_WITH_DOCS.format(
                retrieved_chunks=chunks_text,
                company_context=company_ctx,
                user_question=query.original,
            )
        else:
            prompt = _PROMPT_NO_DOCS.format(
                company_context=company_ctx,
                user_question=query.original,
            )

        stream = call_llm(prompt, _SYSTEM, stream=True)
        return st.write_stream(stream)
