import streamlit as st

from src.agent.graph import metadata_store, vector_store
from src.config import settings
from src.sample_data import SAMPLE_PROJECTS
from src.service.analyzer import extract_embedding_text
from src.session import init_state, run_graph
from src.ui.chat import render as render_chat
from src.ui.confirm import render as render_confirm
from src.ui.list_view import render as render_list
from src.ui.report import render as render_report
from src.ui.sidebar import render as render_sidebar
from src.ui.trend import render as render_trend


def _load_sample_data():
    from src.core.embedding import get_embedding
    existing = {p.project_id for p in metadata_store.get_all_projects()}
    for proj in SAMPLE_PROJECTS:
        if proj.project_id not in existing:
            metadata_store.save_project(proj)
            if settings.openai_api_key:
                embedding = get_embedding(extract_embedding_text(proj))
                vector_store.add_project(proj, embedding)


st.set_page_config(
    page_title="AI · SW 마에스트로 프로젝트 기획 파트너",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="expanded",
    menu_items={},
)

st.markdown("""
<style>
.stChatMessage { max-width: 700px; }
.report-box { background: #f0f2f6; padding: 1.5rem; border-radius: 1rem; margin: 1rem 0; }
</style>
""", unsafe_allow_html=True)

init_state()

if "sample_loaded" not in st.session_state:
    _load_sample_data()
    st.session_state.sample_loaded = True

render_sidebar()

if st.session_state.graph_phase == "init":
    run_graph()
    st.rerun()

phase_handlers = {
    "collecting": render_chat,
    "confirming": render_confirm,
    "analyzing": render_report,
    "done": render_report,
    "list": render_list,
    "trend": render_trend,
}

handler = phase_handlers.get(st.session_state.graph_phase, render_chat)
handler()
