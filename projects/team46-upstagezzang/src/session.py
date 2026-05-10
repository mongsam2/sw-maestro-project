import uuid

import streamlit as st
from langgraph.types import Command

from src.agent.graph import chat_graph


def session_config():
    return {"configurable": {"thread_id": st.session_state.thread_id}}


def init_state():
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid.uuid4())
    if "graph_messages" not in st.session_state:
        st.session_state.graph_messages = []
    if "graph_card" not in st.session_state:
        st.session_state.graph_card = {}
    if "graph_phase" not in st.session_state:
        st.session_state.graph_phase = "init"
    if "graph_report" not in st.session_state:
        st.session_state.graph_report = None
    if "graph_self_check" not in st.session_state:
        st.session_state.graph_self_check = None
    if "graph_missing" not in st.session_state:
        st.session_state.graph_missing = []
    if "pending_input" not in st.session_state:
        st.session_state.pending_input = None


def sync_state_from_graph(graph_state: dict):
    st.session_state.graph_messages = list(graph_state.get("messages", []))
    st.session_state.graph_card = graph_state.get("card") or {}
    st.session_state.graph_phase = graph_state.get("phase", "init")
    st.session_state.graph_report = graph_state.get("report")
    st.session_state.graph_self_check = graph_state.get("self_check")
    st.session_state.graph_missing = list(graph_state.get("missing_fields", []))


def run_graph(user_input: str | None = None):
    config = session_config()
    if user_input is None:
        state = chat_graph.invoke({"messages": []}, config)
    else:
        state = chat_graph.invoke(Command(resume=user_input), config)
    sync_state_from_graph(state)
    return state.get("__interrupt__") is not None


def reset():
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.graph_messages = []
    st.session_state.graph_card = {}
    st.session_state.graph_phase = "init"
    st.session_state.graph_report = None
    st.session_state.graph_self_check = None
    st.session_state.graph_missing = []
    st.session_state.pending_input = None
