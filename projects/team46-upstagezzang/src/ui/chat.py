import streamlit as st
from langgraph.types import Command

from src.agent.graph import chat_graph
from src.session import sync_state_from_graph


def render():
    messages = st.session_state.graph_messages
    for msg in messages[-30:]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.session_state.pending_input:
        with st.chat_message("user"):
            st.markdown(st.session_state.pending_input)

        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        with st.spinner("생각 중..."):
            state = chat_graph.invoke(
                Command(resume=st.session_state.pending_input), config
            )
        sync_state_from_graph(state)
        st.session_state.pending_input = None
        st.rerun()

    prompt = st.chat_input("메시지를 입력하세요...")
    if prompt:
        st.session_state.pending_input = prompt
        st.rerun()


def render_card_preview():
    c = st.session_state.graph_card
    if not c or not c.get("title"):
        return
    info = []
    if c.get("title"):
        info.append(f"**:material/push_pin:** {c['title']}")
    if c.get("team_name"):
        info.append(f":material/label: {c['team_name']}")
    if c.get("problem"):
        p = c["problem"]
        info.append(f":material/question_mark: {p[:50]}{'...' if len(p) > 50 else ''}")
    if c.get("target_user"):
        info.append(f":material/person: {c['target_user']}")
    if c.get("solution"):
        s = c["solution"]
        info.append(f":material/lightbulb: {s[:50]}{'...' if len(s) > 50 else ''}")
    if c.get("tech_stack"):
        info.append(f":material/build: {', '.join(c['tech_stack'])}")
    if c.get("key_features"):
        info.append(f"⭐ {', '.join(c['key_features'])}")
    if c.get("mvp_scope"):
        m = c["mvp_scope"]
        info.append(f":material/target: {m[:50]}{'...' if len(m) > 50 else ''}")

    with st.sidebar:
        st.divider()
        with st.container(border=True):
            st.caption("**:material/description: 현재까지 수집된 정보**")
            for line in info:
                st.caption(line)

        missing = st.session_state.graph_missing
        if missing:
            with st.container(border=True):
                st.caption("**:material/warning: 아직 수집되지 않은 항목**")
                field_labels = {
                    "title": "프로젝트명", "team_name": "팀명",
                    "problem": "해결하려는 문제", "target_user": "대상 사용자",
                    "solution": "해결 방식", "tech_stack": "기술 스택",
                    "key_features": "핵심 기능", "mvp_scope": "MVP 범위",
                }
                for f in missing:
                    st.caption(f"• {field_labels.get(f, f)}")
