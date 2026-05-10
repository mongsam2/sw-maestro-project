import streamlit as st

from src.agent.graph import vector_store
from src.config import settings
from src.session import reset, run_graph


def render():
    from src.ui.chat import render_card_preview

    with st.sidebar:
        st.markdown("## AI · SW 마에스트로<br>프로젝트 기획 파트너", unsafe_allow_html=True)
        st.caption("AI 기술 교육 46조 프로젝트")
        st.divider()
        st.metric("등록된 기획안", f"{vector_store.count()}개")

        if st.button(":material/refresh: 새 대화 시작", width="stretch", key="sb_new_chat"):
            reset()
            run_graph()
            st.rerun()
        if st.button(":material/list: 기획안 목록", width="stretch", key="sb_list"):
            st.session_state.graph_phase = "list"
            st.rerun()
        if st.button(":material/bar_chart: 트렌드 대시보드", width="stretch", key="sb_trend"):
            st.session_state.graph_phase = "trend"
            st.rerun()

        st.divider()
        st.caption("설정")
        api_key = st.text_input(
            "API Key", value=settings.openai_api_key, type="password",
            label_visibility="collapsed", placeholder="OpenAI 호환 API Key",
        )
        if api_key and api_key != settings.openai_api_key:
            settings.openai_api_key = api_key
            st.success(":material/check_circle: 설정 완료")

    render_card_preview()
