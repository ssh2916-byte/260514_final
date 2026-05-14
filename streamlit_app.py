import streamlit as st
import pandas as pd
from datetime import datetime

from core.session_manager import (
    init_session_state,
    add_chat_message,
    save_briefing,
    get_chat_history_markdown,
)
from core.context_manager import render_context_sidebar, get_company_context_str
from core.feedback import render_feedback
from core.notifier import send_slack

from pipelines.risk.collector import FeedCollector
from pipelines.risk.dedup import DuplicateFilter
from pipelines.risk.rule_filter import RuleFilter
from pipelines.risk.summarizer import LLMSummarizer

from pipelines.sap.preprocessor import InputPreprocessor
from pipelines.sap.indexer import get_chroma_collection, index_url
from pipelines.sap.searcher import HybridSearcher
from pipelines.sap.rag_generator import RAGGenerator

from agents.intent_classifier import IntentClassifier

st.set_page_config(
    page_title="IT 보안·리스크 + SAP 운영 에이전트",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state()

# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.title("🛡️ IT·SAP 에이전트")
    st.divider()

    st.markdown("### 🔑 OpenAI API Key")
    api_key = st.text_input(
        "API Key",
        type="password",
        placeholder="sk-...",
        help="키는 세션 내에서만 유지되며 파일에 저장되지 않습니다.",
        label_visibility="collapsed",
    )
    if api_key:
        st.session_state["openai_api_key"] = api_key
        st.success("API Key 설정됨 ✅")
    else:
        st.warning("사이드바에 OpenAI API Key를 입력하세요.")
        st.stop()

    st.divider()
    render_context_sidebar()

    st.divider()
    with st.expander("⚙️ 리스크 필터 설정"):
        cfg = st.session_state.setdefault("filter_config", {})
        cfg["min_cvss"] = st.slider(
            "최소 CVSS 점수",
            0.0,
            10.0,
            float(cfg.get("min_cvss", 7.0)),
            0.1,
        )
        wl_raw = st.text_area(
            "화이트리스트 키워드 (줄 구분)",
            value="\n".join(cfg.get("whitelist_keywords", [])),
            height=80,
        )
        bl_raw = st.text_area(
            "블랙리스트 키워드 (줄 구분)",
            value="\n".join(cfg.get("blacklist_keywords", [])),
            height=80,
        )
        cfg["whitelist_keywords"] = [k.strip() for k in wl_raw.split("\n") if k.strip()]
        cfg["blacklist_keywords"] = [k.strip() for k in bl_raw.split("\n") if k.strip()]
        st.session_state["filter_config"] = cfg

    st.divider()
    with st.expander("🔔 Slack 알림 (선택)"):
        webhook = st.text_input(
            "Webhook URL",
            type="password",
            value=st.session_state.get("slack_webhook_url", ""),
            placeholder="https://hooks.slack.com/...",
            label_visibility="collapsed",
        )
        if webhook:
            st.session_state["slack_webhook_url"] = webhook
            st.caption("Slack 연동 활성화 ✅")

# ── 탭 ────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(
    ["🔴 리스크 브리핑", "💬 SAP Q&A", "📊 대시보드", "⚙️ 설정·인덱싱"]
)

# ─────────────────── 탭1: 리스크 브리핑 ───────────────────
with tab1:
    col_title, col_mode = st.columns([3, 1])
    with col_title:
        st.subheader("오늘의 IT 리스크 브리핑")
    with col_mode:
        detail_mode = st.radio("요약 수준", ["상세", "간단"], horizontal=True, key="detail_mode")

    if st.button("🔄 수집 및 브리핑 생성", type="primary"):
        collector = FeedCollector()
        dedup = DuplicateFilter()
        rule_filter = RuleFilter()
        summarizer = LLMSummarizer()
        company_ctx = get_company_context_str()

        progress_bar = st.progress(0, text="수집 시작...")

        def _prog(value: float, text: str):
            progress_bar.progress(min(value, 1.0), text=text)

        with st.spinner("외부 소스 수집 중..."):
            items = collector.collect_all(progress_callback=_prog)
        progress_bar.empty()

        items = dedup.filter(items)
        items = rule_filter.apply(items)

        st.caption(f"수집·필터 후 **{len(items)}건**")

        if not items:
            st.info("오늘은 관련 리스크가 없습니다. 필터 기준을 낮추거나 다시 시도하세요.")
        else:
            critical_items = [i for i in items if i.severity == "Critical"]
            if critical_items:
                st.error(
                    f"⚠️ Critical 항목 **{len(critical_items)}건** 포함 — 즉시 확인 필요!"
                )
                send_slack(
                    f"⚠️ Critical 보안 리스크 {len(critical_items)}건 감지!\n"
                    + "\n".join(f"- {i.title}" for i in critical_items)
                )

            with st.container(border=True):
                result = summarizer.summarize(
                    items, company_ctx, detail=(detail_mode == "상세")
                )

            if result:
                save_briefing(result)
                st.download_button(
                    "📋 브리핑 내보내기 (.md)",
                    data=result,
                    file_name=f"briefing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown",
                )

    if st.session_state.get("briefing_history"):
        with st.expander(
            f"📜 브리핑 이력 ({len(st.session_state['briefing_history'])}건)"
        ):
            for b in reversed(st.session_state["briefing_history"]):
                st.markdown(f"**{b['created_at']}**")
                st.markdown(b["content"])
                st.divider()

# ─────────────────── 탭2: SAP Q&A ───────────────────
with tab2:
    st.subheader("SAP 운영 Q&A")

    col_r, col_e, _ = st.columns([1, 1, 4])
    with col_r:
        if st.button("🗑️ 대화 초기화"):
            st.session_state["chat_history"] = []
            st.rerun()
    with col_e:
        history_md = get_chat_history_markdown()
        if history_md:
            st.download_button(
                "📥 내보내기",
                data=history_md,
                file_name=f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
            )

    # 이전 대화 표시
    for i, msg in enumerate(st.session_state.get("chat_history", [])):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                render_feedback(msg.get("id", f"hist_{i}"))

    # 새 입력 처리
    if prompt := st.chat_input("SAP 오류 메시지 또는 T-code를 입력하세요..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        add_chat_message("user", prompt)

        preprocessor = InputPreprocessor()
        classifier = IntentClassifier()
        searcher = HybridSearcher()
        rag = RAGGenerator()
        company_ctx = get_company_context_str()

        processed = preprocessor.preprocess(prompt)

        with st.spinner("의도 분류 중..."):
            intent = classifier.classify(prompt)

        st.session_state.setdefault("routing_logs", []).append(
            {
                "query": prompt,
                "intent": intent.intent,
                "confidence": intent.confidence,
                "timestamp": datetime.now().isoformat(),
            }
        )

        msg_id = f"asst_{datetime.now().timestamp()}"

        with st.chat_message("assistant"):
            if intent.confidence < 0.7:
                answer = (
                    f"의도를 명확히 파악하지 못했습니다 (신뢰도: {intent.confidence:.0%}). "
                    "질문을 더 구체적으로 입력해 주세요."
                )
                st.warning(answer)

            elif intent.intent == "risk_query":
                answer = (
                    "이 질문은 **리스크 브리핑** 탭(탭 1)에서 처리됩니다. "
                    "'🔴 리스크 브리핑' 탭으로 이동하여 수집 및 브리핑을 실행하세요."
                )
                st.info(answer)

            elif intent.intent == "other":
                answer = "SAP 운영 또는 IT 보안 관련 질문만 지원합니다."
                st.info(answer)

            else:  # sap_qa | cross
                with st.spinner("관련 문서 검색 중..."):
                    docs = searcher.search(processed, top_k=5)

                if not docs:
                    st.caption(
                        "⚠️ 인덱싱된 문서에서 관련 내용을 찾지 못했습니다. 일반 지식으로 답변합니다."
                    )

                answer = rag.generate(processed, docs, company_ctx)
                render_feedback(msg_id)

        add_chat_message("assistant", answer, msg_id)

# ─────────────────── 탭3: 대시보드 ───────────────────
with tab3:
    st.subheader("📊 운영 현황 대시보드")

    fbs = st.session_state.get("feedbacks", [])
    chat_hist = st.session_state.get("chat_history", [])
    briefing_hist = st.session_state.get("briefing_history", [])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("브리핑 생성 횟수", len(briefing_hist))
    c2.metric("SAP Q&A 질의 수", sum(1 for m in chat_hist if m["role"] == "user"))
    c3.metric("긍정 피드백 👍", sum(1 for f in fbs if f["rating"] == 1))
    c4.metric("부정 피드백 👎", sum(1 for f in fbs if f["rating"] == -1))

    st.divider()

    st.markdown("### 📜 브리핑 이력")
    if briefing_hist:
        df_b = pd.DataFrame(
            [
                {"생성 시각": b["created_at"], "요약 미리보기": b["content"][:120] + "..."}
                for b in briefing_hist
            ]
        )
        st.dataframe(df_b, use_container_width=True)
        st.download_button(
            "CSV 내보내기",
            data=df_b.to_csv(index=False, encoding="utf-8-sig"),
            file_name="briefing_history.csv",
            mime="text/csv",
        )
    else:
        st.info("아직 생성된 브리핑이 없습니다.")

    st.divider()

    st.markdown("### 🔀 의도 분류 이력")
    logs = st.session_state.get("routing_logs", [])
    if logs:
        df_logs = pd.DataFrame(logs)
        st.dataframe(df_logs, use_container_width=True)
        intent_counts = df_logs["intent"].value_counts()
        st.bar_chart(intent_counts)
    else:
        st.info("아직 분류된 질의가 없습니다.")

    st.divider()

    st.markdown("### 💬 피드백 현황")
    if fbs:
        df_fb = pd.DataFrame(fbs)
        st.dataframe(df_fb, use_container_width=True)
        st.download_button(
            "피드백 CSV",
            data=df_fb.to_csv(index=False, encoding="utf-8-sig"),
            file_name="feedbacks.csv",
            mime="text/csv",
        )
    else:
        st.info("아직 피드백이 없습니다.")

# ─────────────────── 탭4: 설정·인덱싱 ───────────────────
with tab4:
    st.subheader("⚙️ SAP 문서 인덱싱")

    col_desc, col_metric = st.columns([3, 1])
    with col_metric:
        try:
            coll = get_chroma_collection()
            st.metric("인덱싱된 청크 수", coll.count())
        except Exception:
            st.metric("인덱싱된 청크 수", 0)
    with col_desc:
        st.markdown(
            "SAP 공식 문서 또는 SAP Community URL을 입력하면 텍스트를 추출·임베딩하여 Q&A에 활용합니다.  \n"
            "세션이 종료되면 인메모리 인덱스는 초기화됩니다."
        )

    default_urls = (
        "https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE\n"
        "https://community.sap.com/t5/technology-blogs-by-sap/bg-p/technology-blog-sap"
    )
    urls_input = st.text_area(
        "인덱싱할 SAP 문서 URL (줄 구분)",
        value=default_urls,
        height=150,
        help="각 줄에 URL 하나씩 입력하세요.",
    )

    col_start, col_clear = st.columns([1, 1])
    with col_start:
        if st.button("▶️ 인덱싱 시작", type="primary", use_container_width=True):
            urls = [u.strip() for u in urls_input.split("\n") if u.strip()]
            if not urls:
                st.warning("URL을 입력하세요.")
            else:
                total_chunks = 0
                with st.status("인덱싱 중...", expanded=True) as status:
                    prog = st.progress(0)
                    for i, url in enumerate(urls):
                        st.write(f"처리 중: `{url}`")
                        try:
                            n = index_url(url)
                            total_chunks += n
                            st.write(f"  ✅ {n}개 청크 추가")
                        except Exception as e:
                            st.write(f"  ❌ 오류: {e}")
                        prog.progress((i + 1) / len(urls))
                    status.update(
                        label=f"✅ 인덱싱 완료! 총 {total_chunks}개 청크", state="complete"
                    )
                st.rerun()

    with col_clear:
        if st.button("🗑️ 인덱스 초기화", use_container_width=True):
            if "chroma_client" in st.session_state:
                del st.session_state["chroma_client"]
            st.success("인덱스가 초기화되었습니다.")
            st.rerun()

    st.divider()

    st.markdown("### 💾 ChromaDB 영속화 (선택)")
    st.markdown(
        "기본값은 **인메모리(세션 종료 시 초기화)** 입니다.  \n"
        "아래 버튼을 누르면 `./chroma_db` 로컬 디렉터리에 저장되어 재시작 후에도 유지됩니다."
    )
    if st.button("영속화 모드로 전환"):
        import chromadb as _chromadb
        st.session_state["chroma_client"] = _chromadb.PersistentClient(path="./chroma_db")
        st.success("영속화 모드로 전환되었습니다. `./chroma_db` 에 인덱스가 저장됩니다.")
        st.rerun()
