import pandas as pd
import plotly.express as px
import streamlit as st

from src.agent.graph import metadata_store
from src.service.trend import analyze_trends


def render():
    st.markdown("## :material/monitoring: 트렌드 대시보드")
    st.caption("등록된 모든 기획안의 도메인·기술·대상 분포를 한눈에 확인하세요.")

    projects = metadata_store.get_all_projects()
    if not projects:
        st.info("등록된 기획안이 없습니다. 먼저 기획안을 등록해주세요.")
        if st.button("← 대화로 돌아가기", width="stretch"):
            st.session_state.graph_phase = "collecting"
            st.rerun()
        return

    with st.spinner("트렌드 분석 중..."):
        trends = analyze_trends(projects)

    st.metric("총 기획안", f"{trends['total']}개")
    if not trends.get("categorized"):
        st.caption(
            ":material/warning: API key 미설정으로 키워드 기반 분류를 사용했습니다. "
            "LLM 분류를 원하면 API key를 설정하세요."
        )
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### :material/category: 도메인 분포")
        if trends["domains"]:
            df = pd.DataFrame({"도메인": list(trends["domains"].keys()),
                               "개수": list(trends["domains"].values())})
            fig = px.pie(df, names="도메인", values="개수", hole=0.3,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("도메인 데이터가 없습니다.")

    with col2:
        st.markdown("### :material/build: 기술 스택")
        if trends["tech_stacks"]:
            df = pd.DataFrame({"기술": list(trends["tech_stacks"].keys()),
                               "사용 횟수": list(trends["tech_stacks"].values())})
            fig = px.bar(df, x="사용 횟수", y="기술", orientation="h",
                         color_discrete_sequence=["#667eea"],
                         text="사용 횟수")
            fig.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10),
                              yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("기술 스택 데이터가 없습니다.")

    st.markdown("### :material/description: 기획안별 요약")
    rows = []
    for p in projects:
        rows.append({
            "프로젝트명": p.title,
            "팀명": p.team_name,
            "기술 스택": ", ".join(p.tech_stack),
            "대상 사용자": p.target_user[:30] if p.target_user else "-",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.divider()
    if st.button("← 대화로 돌아가기", width="stretch"):
        st.session_state.graph_phase = "collecting"
        st.rerun()
