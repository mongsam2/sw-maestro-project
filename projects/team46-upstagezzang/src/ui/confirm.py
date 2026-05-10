import ast

import streamlit as st
from langgraph.types import Command

from src.agent.graph import chat_graph
from src.models import ProjectCard
from src.service.checker import check as run_self_check
from src.session import reset, run_graph, sync_state_from_graph


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _card_changed(original: dict, card: ProjectCard) -> bool:
    return ProjectCard(**original).model_dump() != card.model_dump()


def _display_items(value: object) -> list[str]:
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_display_items(item))
        return items

    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return [text]
        if isinstance(parsed, list):
            return _display_items(parsed)
    return [text]


def _display_text(value: object, separator: str = "\n") -> str:
    return separator.join(_display_items(value))


def _summary_items(value: object) -> list[str]:
    items: list[str] = []
    for item in _display_items(value):
        lines = [line.strip().lstrip("- ").strip() for line in item.splitlines()]
        for line in lines:
            if not line:
                continue
            items.append(line)
    return items


def _display_summary(value: object) -> str:
    items = _summary_items(value)
    if len(items) > 1:
        return "\n".join(f"- {item}" for item in items)
    return items[0] if items else ""


def render():
    st.markdown("## :material/description: 기획안 최종 확인")
    st.caption("아래 내용을 확인하고 수정이 필요하면 직접 편집하세요.")

    card_dict = st.session_state.graph_card
    card = ProjectCard(**card_dict)

    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            card.title = st.text_input("프로젝트명 / 서비스명", value=card.title, key="cf_title")
            card.team_name = st.text_input("팀명", value=card.team_name, key="cf_team")
            card.problem = st.text_area("해결하려는 문제", value=card.problem, height=80,
                                        placeholder="사용자가 겪는 구체적인 불편함", key="cf_problem")
            card.target_user = st.text_input("대상 사용자", value=card.target_user,
                                             placeholder="연령대, 직업, 상황 등을 포함", key="cf_target")
        with col2:
            card.solution = st.text_area("해결 방식", value=card.solution, height=80,
                                         placeholder="핵심 접근 방식과 차별화 전략", key="cf_solution")
            kw = ", ".join(card.key_features)
            kw = st.text_input("핵심 기능 (쉼표 구분)", value=kw, placeholder="2~3가지 핵심 기능", key="cf_features")
            card.key_features = [x.strip() for x in kw.split(",") if x.strip()]
            ts = ", ".join(card.tech_stack)
            ts = st.text_input("기술 스택 (쉼표 구분)", value=ts, placeholder="언어, 프레임워크 등", key="cf_tech")
            card.tech_stack = [x.strip() for x in ts.split(",") if x.strip()]
            card.mvp_scope = st.text_area("MVP 범위", value=card.mvp_scope, height=60,
                                          placeholder="짧은 기간에 구현할 데모 범위", key="cf_mvp")

        is_public = st.toggle(":material/language: 전체 공개",
                              value=card.visibility == "public",
                              help="ON: 모든 내용 공개 / OFF: 제목과 기술만 공개",
                              key="cf_vis")
        card.visibility = "public" if is_public else "summary"

    self_check = st.session_state.graph_self_check
    if self_check:
        with st.expander(":material/monitoring: 셀프 체크 리포트", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("종합", f"{self_check.get('overall_score', 0)}/10")
            col2.metric("명확성", f"{self_check.get('clarity_score', 0)}/10")
            col3.metric("완성도", f"{self_check.get('completeness_score', 0)}/10")
            col4.metric("준비도", f"{self_check.get('overall_score', 0)}/10")

            if self_check.get("one_line_summary"):
                st.info(_display_summary(self_check["one_line_summary"]))
            if self_check.get("reasoning"):
                st.caption(_display_text(self_check["reasoning"]))

            if self_check.get("strengths") or self_check.get("weaknesses"):
                strong_col, weak_col = st.columns(2)
                if self_check.get("strengths"):
                    strong_col.success("**강점**\n\n" + "\n".join(f"- {s}" for s in _display_items(self_check["strengths"])))
                if self_check.get("weaknesses"):
                    weak_col.warning("**보강점**\n\n" + "\n".join(f"- {w}" for w in _display_items(self_check["weaknesses"])))

            if self_check.get("dimension_scores"):
                st.markdown("#### 루브릭 점검")
                for dimension in self_check["dimension_scores"]:
                    score = _to_int(dimension.get("score"))
                    with st.container(border=True):
                        d_col1, d_col2 = st.columns([4, 1])
                        d_col1.markdown(f"**{dimension.get('label') or dimension.get('key', '평가 항목')}**")
                        d_col2.markdown(f"**{score}/10**")
                        st.progress(min(max(score, 0), 10) / 10)
                        if dimension.get("rationale"):
                            st.caption(_display_text(dimension["rationale"]))
                        if dimension.get("evidence"):
                            st.markdown(f":material/search: {_display_text(dimension['evidence'])}")
                        if dimension.get("action"):
                            st.markdown(f":material/arrow_forward: {_display_text(dimension['action'])}")

            if self_check.get("priority_actions"):
                st.markdown("#### 우선 수정 액션")
                for action in self_check["priority_actions"]:
                    with st.container(border=True):
                        title = _display_text(action.get("title"), " ") or "수정 액션"
                        priority = _display_text(action.get("priority"), " ") or "P1"
                        st.markdown(f"**{priority} · {title}**")
                        if action.get("detail"):
                            st.write(_display_text(action["detail"]))
                        if action.get("example"):
                            st.markdown(f"> {_display_text(action['example'], ' ')}")

            extra_tabs = st.tabs(["멘토 질문", "다듬은 설명", "리스크"])
            with extra_tabs[0]:
                if self_check.get("mentor_questions"):
                    for q in _display_items(self_check["mentor_questions"]):
                        st.markdown(f"- {q}")
                else:
                    st.caption("멘토 질문이 생성되지 않았습니다.")
            with extra_tabs[1]:
                if self_check.get("revised_pitch"):
                    st.write(_display_text(self_check["revised_pitch"], " "))
                else:
                    st.caption("다듬은 설명이 생성되지 않았습니다.")
            with extra_tabs[2]:
                if self_check.get("risk_flags"):
                    for risk in _display_items(self_check["risk_flags"]):
                        st.markdown(f"- {risk}")
                else:
                    st.caption("표시할 리스크가 없습니다.")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.button(":material/done: 저장하고 유사도 분석 시작", type="primary", width="stretch", key="cf_save"):
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            state_update = {"card": card.model_dump()}
            if _card_changed(card_dict, card) or not st.session_state.graph_self_check:
                with st.spinner("셀프 체크 리포트 갱신 중..."):
                    state_update["self_check"] = run_self_check(card).model_dump()
            chat_graph.update_state(config, state_update)
            with st.spinner("임베딩 생성 및 유사도 분석 중..."):
                state = chat_graph.invoke(Command(resume="save"), config)
            sync_state_from_graph(state)
            st.rerun()
    with col2:
        if st.button(":material/undo: 다시 입력", width="stretch", key="cf_restart"):
            reset()
            run_graph()
            st.rerun()
    with col3:
        if st.button(":material/edit: 수정 요청", width="stretch", key="cf_edit"):
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            chat_graph.update_state(config, {
                "card": card.model_dump(),
                "current_question": "어떤 부분을 수정할까요? 바꾸고 싶은 내용을 알려주세요.",
                "phase": "collecting",
            })
            state = chat_graph.invoke(Command(resume="edit"), config)
            sync_state_from_graph(state)
            st.rerun()
