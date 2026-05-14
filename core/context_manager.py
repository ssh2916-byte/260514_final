import json
import streamlit as st

DEFAULT_CONTEXT = {
    "sap_version": "S/4HANA 2023",
    "cloud": [],
    "os_stack": [],
    "sap_modules": [],
    "custom_keywords": [],
}


def get_company_context_str() -> str:
    ctx = st.session_state.get("company_context", DEFAULT_CONTEXT.copy())
    lines = [
        f"SAP 버전: {ctx.get('sap_version', '')}",
        f"클라우드: {', '.join(ctx.get('cloud', []))}",
        f"OS: {', '.join(ctx.get('os_stack', []))}",
        f"SAP 모듈: {', '.join(ctx.get('sap_modules', []))}",
        f"추가 키워드: {', '.join(ctx.get('custom_keywords', []))}",
    ]
    return "\n".join(lines)


def render_context_sidebar():
    with st.sidebar.expander("🏢 회사 IT 환경 설정"):
        ctx = st.session_state.setdefault("company_context", DEFAULT_CONTEXT.copy())

        sap_versions = ["S/4HANA 2023", "S/4HANA 2022", "S/4HANA 2021", "ECC 6.0", "기타"]
        current_ver = ctx.get("sap_version", "S/4HANA 2023")
        idx = sap_versions.index(current_ver) if current_ver in sap_versions else 0
        ctx["sap_version"] = st.selectbox("SAP 버전", sap_versions, index=idx)

        ctx["cloud"] = st.multiselect(
            "클라우드 환경",
            ["AWS", "Azure", "GCP", "온프레미스"],
            default=ctx.get("cloud", []),
        )
        ctx["os_stack"] = st.multiselect(
            "운영 OS",
            ["RHEL", "Ubuntu", "Windows Server", "SUSE", "AIX"],
            default=ctx.get("os_stack", []),
        )
        ctx["sap_modules"] = st.multiselect(
            "SAP 모듈",
            ["FI", "CO", "MM", "SD", "PP", "HR", "PM", "QM", "WM", "BI/BW", "BASIS"],
            default=ctx.get("sap_modules", []),
        )
        raw_kw = st.text_input(
            "추가 키워드 (쉼표 구분)",
            value=", ".join(ctx.get("custom_keywords", [])),
        )
        ctx["custom_keywords"] = [k.strip() for k in raw_kw.split(",") if k.strip()]
        st.session_state["company_context"] = ctx

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "💾 저장",
                data=json.dumps(ctx, ensure_ascii=False, indent=2),
                file_name="context.json",
                mime="application/json",
                use_container_width=True,
            )
        with col2:
            uploaded = st.file_uploader("📂 불러오기", type=["json"], key="ctx_uploader")
            if uploaded:
                try:
                    loaded = json.loads(uploaded.read())
                    st.session_state["company_context"] = loaded
                    st.success("불러오기 완료!")
                    st.rerun()
                except Exception as e:
                    st.error(f"파일 오류: {e}")
