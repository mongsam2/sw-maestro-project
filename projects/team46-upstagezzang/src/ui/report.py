import streamlit as st
from langgraph.types import Command

from src.agent.graph import chat_graph, vector_store
from src.models import AnalysisReport, ProjectCard
from src.service.cross_insight import CATEGORY_COLORS, CATEGORY_ICONS, CATEGORY_LABELS
from src.models import AnalysisReport, ProjectCard, SelfCheckReport
from src.session import reset, run_graph, sync_state_from_graph


def _render_self_check(self_check: SelfCheckReport | None):
    if not self_check:
        st.info(":material/monitoring: 저장된 자가점검 리포트가 없습니다.")
        return

    col1, col2 = st.columns(2)
    col1.metric("명확성", f"{self_check.clarity_score}/10")
    col2.metric("완성도", f"{self_check.completeness_score}/10")
    if self_check.reasoning:
        st.info(self_check.reasoning)
    if self_check.strengths:
        st.success("**강점:** " + " · ".join(self_check.strengths))
    if self_check.weaknesses:
        st.warning("**개선 필요:** " + " · ".join(self_check.weaknesses))
    if self_check.suggestions:
        for suggestion in self_check.suggestions:
            st.caption(f":material/lightbulb: {suggestion}")
    if self_check.web_findings:
        with st.expander("외부 참고 자료"):
            st.write(self_check.web_findings)


def render():
    report = st.session_state.graph_report
    report = AnalysisReport(**report) if report else None
    self_check = st.session_state.graph_self_check
    self_check = SelfCheckReport(**self_check) if self_check else None
    card_dict = st.session_state.graph_card
    card = ProjectCard(**card_dict)

    st.markdown(f"## :material/monitoring: 분석 리포트 — *{card.title}*")

    if report and report.similar_projects:
        count = vector_store.count()
        if count <= 2:
            st.warning(f":material/warning: 등록된 기획안이 {count}개뿐입니다. 더 많은 기획이 등록되면 분석 정확도가 높아집니다.")

    st.divider()

    tabs = st.tabs([
        ":material/monitoring: 자가점검",
        ":material/search: 유사도 분석",
        ":material/psychology: Cross-Insight",
        ":material/mic: 멘토링 준비",
    ])

    # ── 탭 0: 유사도 분석 ─────────────────────────────────────────────
    with tabs[0]:
        _render_self_check(self_check)

    with tabs[1]:
        if not report or not report.similar_projects:
            st.info(":material/search: 유사한 기획안을 찾을 수 없습니다.")
        else:
            for i, sim in enumerate(report.similar_projects):
                risk_color = {"High": "red", "Medium": "orange", "Low": "green"}.get(sim.risk_level, "gray")
                risk_icon = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}.get(sim.risk_level, "⚪")

                with st.container(border=True):
                    col1, col2, col3 = st.columns([4, 1, 1])
                    with col1:
                        st.markdown(f"**{i+1}. {sim.project.title}**")
                        st.caption(f"팀: {sim.project.team_name or '—'}")
                    with col2:
                        st.markdown(f":{risk_color}[**유사도**]")
                        st.markdown(f"**{sim.overall_score:.0%}**")
                    with col3:
                        st.markdown(f":{risk_color}[**위험도**]")
                        st.markdown(f"{risk_icon} **{sim.risk_level}**")

                    axes = ["problem", "target_user", "solution", "tech_stack"]
                    if any(getattr(sim, f"{a}_score", 0) > 0 for a in axes):
                        st.divider()
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("문제 유사도", f"{sim.problem_score:.0%}")
                        c2.metric("대상 유사도", f"{sim.target_user_score:.0%}")
                        c3.metric("해결방식 유사도", f"{sim.solution_score:.0%}")
                        c4.metric("기술 유사도", f"{sim.tech_stack_score:.0%}")

                    st.divider()
                    st.markdown(f"**겹치는 부분:** {' · '.join(sim.overlapping_aspects) if sim.overlapping_aspects else '—'}")
                    if sim.distinct_aspects:
                        st.markdown(f"**차별화 가능:** {' · '.join(sim.distinct_aspects)}")
                    st.markdown(f"**:material/description: 판단 근거:** {sim.reasoning}")
                    st.markdown(f"**:material/lightbulb: 추천 조치:** {sim.recommended_action}")

    # ── 탭 2: Cross-Insight ──────────────────────────────────────────
    with tabs[2]:
        if not report or not report.cross_insights:
            st.info(":material/lightbulb: Cross-Insight를 생성할 수 없습니다. 유사 기획안이 필요합니다.")
            if report and not report.similar_projects:
                st.caption("기획안을 저장하면 등록된 유사 기획과 비교해 Cross-Insight가 자동 생성됩니다.")
        else:
            insights = report.cross_insights

            # ① 상단 안내 + 액션 버튼 (스크롤 없이 바로 접근)
            n = len(insights)
            st.caption(f"유사 기획 분석을 바탕으로 **{n}가지 관점**에서 기획을 더 선명하게 만들 아이디어를 제안합니다.")

            all_text = ("\n\n" + "=" * 50 + "\n\n").join(
                f"[{CATEGORY_LABELS.get(ins.category, ins.category)}] {CATEGORY_ICONS.get(ins.category, '')} {ins.title}\n\n"
                f"{ins.description}\n\n"
                f"▶ 변경: {ins.change_type}\n"
                f"▶ 이유: {ins.why_needed}\n"
                f"▶ 결정: {ins.next_decision}"
                + (f"\n출처: {ins.source_project_title}" if ins.source_project_title else "")
                for ins in insights
            )

            top_l, top_r = st.columns([1, 1])
            with top_l:
                st.download_button(
                    label=":material/download: 전체 내보내기",
                    data=all_text,
                    file_name="cross_insights_all.txt",
                    mime="text/plain",
                    key="ci_export_all",
                    use_container_width=True,
                )
            with top_r:
                if st.button(
                    ":material/refresh: Cross-Insight 재생성",
                    key="ci_regen",
                    use_container_width=True,
                    help="유사 기획 데이터를 바탕으로 새로운 인사이트 생성",
                ):
                    from src.service.cross_insight import generate_cross_insights as _regen
                    with st.spinner("Cross-Insight 재생성 중..."):
                        new_report = _regen(report)
                    config = {"configurable": {"thread_id": st.session_state.thread_id}}
                    chat_graph.update_state(config, {"report": new_report.model_dump()})
                    st.session_state.graph_report = new_report.model_dump()
                    st.rerun()

            st.divider()

            # ② 카테고리 필터
            all_cats = ["전체"] + [c for c in CATEGORY_LABELS if any(ins.category == c for ins in insights)]
            filter_labels = {"전체": "전체"}
            for c in CATEGORY_LABELS:
                filter_labels[c] = f"{CATEGORY_ICONS.get(c, '')} {CATEGORY_LABELS[c]}"

            selected_cat = st.radio(
                "카테고리 필터",
                options=all_cats,
                format_func=lambda x: filter_labels.get(x, x),
                horizontal=True,
                label_visibility="collapsed",
                key="ci_filter",
            )

            visible = [ins for ins in insights if selected_cat == "전체" or ins.category == selected_cat]
            if not visible:
                st.info("선택한 카테고리의 인사이트가 없습니다.")

            # ③ 인사이트 카드
            # 구조: 카테고리 뱃지 + 제목 → 설명 → 📌 결정 사항(강조) → [상세 펼치기]
            for idx, insight in enumerate(visible):
                cat = insight.category
                ico = CATEGORY_ICONS.get(cat, "💡")
                color = CATEGORY_COLORS.get(cat, "gray")
                label = CATEGORY_LABELS.get(cat, cat)

                export_text = (
                    f"[{label}] {insight.title}\n\n"
                    f"{insight.description}\n\n"
                    f"▶ 변경 사항: {insight.change_type}\n"
                    f"▶ 필요한 이유: {insight.why_needed}\n"
                    f"▶ 다음 회의 결정 사항: {insight.next_decision}"
                    + (f"\n\n출처: {insight.source_project_title}" if insight.source_project_title else "")
                )

                with st.container(border=True):
                    # 헤더: 카테고리 뱃지 + 출처 (한 줄)
                    badge = f":{color}[{ico} {label}]"
                    source = f"  ·  출처: {insight.source_project_title}" if insight.source_project_title else ""
                    st.caption(f"{badge}{source}")

                    # 제목 + 설명
                    st.markdown(f"**{insight.title}**")
                    st.markdown(insight.description)

                    # 핵심 결정 사항 — 사용자가 회의에 가져갈 것, 시각적으로 강조
                    st.warning(f":material/pin: **다음 회의에서 결정하세요**\n\n{insight.next_decision}")

                    # 상세 정보 — 기본 접힘 (읽고 싶은 사람만 펼침)
                    with st.expander("상세 보기 — 변경 사항 · 필요한 이유"):
                        st.info(f"**변경 사항:** {insight.change_type}")
                        st.success(f"**필요한 이유:** {insight.why_needed}")

                    # 개별 내보내기 — 카드 하단, 눈에 띄지 않게
                    _, dl_col = st.columns([6, 1])
                    with dl_col:
                        st.download_button(
                            label=":material/download:",
                            data=export_text,
                            file_name=f"insight_{idx+1}_{cat.lower().replace(' ', '_')}.txt",
                            mime="text/plain",
                            key=f"ci_dl_{idx}",
                            use_container_width=True,
                            help="이 인사이트 내보내기",
                        )

    # ── 탭 2: 멘토링 준비 ────────────────────────────────────────────
    with tabs[3]:
        if report:
            if report.mentoring_summary and not report.mentoring_one_minute:
                st.info(report.mentoring_summary)

            one_min = report.mentoring_one_minute
            if one_min:
                with st.container(border=True):
                    st.markdown("### :material/mic: 1분 기획 요약")
                    st.caption("멘토님이 1분 안에 읽을 수 있는 분량")
                    st.markdown(f"**:material/report_problem: 해결 문제**\n\n{one_min.problem or '—'}")
                    st.markdown(f"**:material/group: 대상 사용자**\n\n{one_min.target_user or '—'}")
                    st.markdown(f"**:material/build: 해결 방식**\n\n{one_min.solution or '—'}")
                    st.markdown(f"**:material/star: 기대 효과**\n\n{one_min.expected_value or '—'}")

            if report.differentiation_points:
                with st.container(border=True):
                    st.markdown("### :material/auto_awesome: 핵심 차별화 포인트")
                    st.caption("유사도 분석 결과를 바탕으로 도출된 우리 팀만의 강점")
                    for point in report.differentiation_points:
                        st.markdown(f"- {point}")

            if report.expected_questions:
                with st.container(border=True):
                    st.markdown("### :material/help: 멘토링 예상 질문 & 디펜스 가이드")
                    st.caption("Problem-Solution Fit · 타겟 명확성 · 가설 검증 중심")
                    for i, q in enumerate(report.expected_questions):
                        focus_label = f" · *{q.focus}*" if q.focus else ""
                        with st.expander(f"Q{i+1}. {q.question}{focus_label}"):
                            st.info(f":material/lightbulb: **준비 팁**\n\n{q.prep_tip or '준비 가이드가 비어있습니다.'}")

    # ── 하단 페이지 액션 ──────────────────────────────────────────────
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button(":material/refresh: 새 기획 입력", type="primary", use_container_width=True, key="rpt_new"):
            reset()
            run_graph()
            st.rerun()
    with col2:
        if st.button(":material/list: 기획안 목록", use_container_width=True):
            st.session_state.graph_phase = "list"
            st.rerun()
    with col3:
        if st.button(":material/edit: 대화로 수정", use_container_width=True):
            st.session_state.graph_messages = []
            st.session_state.graph_phase = "collecting"
            st.session_state.graph_report = None
            st.rerun()
    with col4:
        if st.button(":material/sync: 재분석", use_container_width=True, help="현재 기획안으로 다시 분석"):
            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            with st.spinner("재분석 중..."):
                state = chat_graph.invoke(Command(resume="save"), config)
            sync_state_from_graph(state)
            st.rerun()
