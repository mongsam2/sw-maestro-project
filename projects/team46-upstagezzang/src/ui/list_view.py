import streamlit as st

from src.agent.graph import metadata_store, vector_store


def _matches(project, query: str) -> bool:
    q = query.lower()
    fields = [
        project.title, project.team_name, project.problem,
        project.target_user, project.solution,
        ", ".join(project.tech_stack), ", ".join(project.key_features),
    ]
    return any(q in f.lower() for f in fields if f)


def render():
    st.markdown("## :material/list: 등록된 기획안 목록")
    projects = metadata_store.get_all_projects()
    if not projects:
        st.info("등록된 기획안이 없습니다.")
        if st.button("← 대화로 돌아가기", width="stretch"):
            st.session_state.graph_phase = "collecting"
            st.rerun()
        return

    st.caption(f"총 {len(projects)}개의 기획안이 등록되어 있습니다.")

    query = st.text_input(
        ":material/search: 기획안 검색", placeholder="제목, 팀명, 기술 스택, 설명 등으로 검색...",
    )
    if query:
        projects = [p for p in projects if _matches(p, query)]
        st.caption(f"검색 결과: {len(projects)}개")
        if not projects:
            st.info("검색 결과가 없습니다.")

    for p in projects:
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.markdown(f"**{p.title}**")
            col2.caption(f"팀: {p.team_name}")
            col3.caption(p.created_at[:10] if p.created_at else "")
            with st.expander("상세 보기"):
                if p.visibility == "summary":
                    st.markdown(f"**기술:** {', '.join(p.tech_stack) if p.tech_stack else '-'}")
                    st.caption(":material/description: 요약 공개 — 주제와 기술만 표시됩니다")
                else:
                    st.markdown(f"**문제:** {p.problem}")
                    st.markdown(f"**대상:** {p.target_user}")
                    st.markdown(f"**해결방식:** {p.solution}")
                    st.markdown(f"**기술:** {', '.join(p.tech_stack)}")
                    st.markdown(f"**MVP:** {p.mvp_scope}")
                    st.caption(f"공개 범위: {p.visibility}")
                if st.button(":material/delete: 삭제", key=f"del_{p.project_id}"):
                    vector_store.delete_project(p.project_id)
                    metadata_store.delete_project(p.project_id)
                    st.rerun()
                analysis_report = metadata_store.get_analysis_report(p.project_id)
                self_check_report = metadata_store.get_self_check_report(p.project_id)
                if analysis_report:
                    if st.button(":material/monitoring: 저장된 리포트 보기", key=f"report_{p.project_id}"):
                        st.session_state.graph_card = p.model_dump()
                        st.session_state.graph_report = analysis_report.model_dump()
                        st.session_state.graph_self_check = self_check_report.model_dump() if self_check_report else None
                        st.session_state.graph_phase = "done"
                        st.rerun()
                elif self_check_report:
                    st.caption(":material/monitoring: 자가점검 리포트가 저장되어 있습니다.")
    if st.button("← 대화로 돌아가기", width="stretch"):
        st.session_state.graph_phase = "collecting"
        st.rerun()
