import json
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from src.agent.prompts import SELF_CHECK_PROMPT
from src.config import settings
from src.core.llm import get_llm
from src.models import ProjectCard, SelfCheckReport


class SelfCheckState(TypedDict, total=False):
    project: ProjectCard
    project_json: str
    self_check: SelfCheckReport
    fallback_reason: str


def _fallback_report(project: ProjectCard, reason: str) -> SelfCheckReport:
    missing_fields = []
    if not project.title or len(project.title.strip()) < 2:
        missing_fields.append("프로젝트명")
    if not project.team_name or len(project.team_name.strip()) < 2:
        missing_fields.append("팀명")
    if not project.problem or len(project.problem.strip()) < 10:
        missing_fields.append("해결하려는 문제")
    if not project.target_user or len(project.target_user.strip()) < 5:
        missing_fields.append("대상 사용자")
    if not project.solution or len(project.solution.strip()) < 10:
        missing_fields.append("해결 방식")
    if not project.tech_stack:
        missing_fields.append("기술 스택")
    if not project.key_features:
        missing_fields.append("핵심 기능")

    return SelfCheckReport(
        missing_fields=missing_fields,
        suggestions=["LLM 셀프 리포트 생성에 실패했습니다. 잠시 후 다시 시도해주세요."],
        clarity_score=5,
        completeness_score=5,
        overall_score=5,
        readiness_level="검토 필요",
        one_line_summary="자동 평가 결과를 생성하지 못했습니다.",
        reasoning=reason,
    )


def prepare_project_node(state: SelfCheckState) -> SelfCheckState:
    project = state["project"]
    card_json = project.model_dump(exclude={"project_id", "created_at", "updated_at"})
    return {
        "project_json": json.dumps(card_json, ensure_ascii=False, indent=2),
    }


def route_after_prepare(state: SelfCheckState) -> str:
    if not settings.openai_api_key:
        return "fallback"
    return "call_structured_llm"


def call_structured_llm_node(state: SelfCheckState) -> SelfCheckState:
    llm = get_llm().with_structured_output(SelfCheckReport)
    try:
        report = llm.invoke([
            SystemMessage(content="너는 SW Maestro 기획안을 점검하는 시니어 기획 코치야."),
            HumanMessage(content=SELF_CHECK_PROMPT.format(
                project_json=state["project_json"],
            )),
        ])
        validated = SelfCheckReport.model_validate(report)
    except Exception as exc:
        return {"fallback_reason": f"구조화 출력 생성에 실패했습니다: {exc}"}

    return {"self_check": validated}


def route_after_structured_output(state: SelfCheckState) -> str:
    if isinstance(state.get("self_check"), SelfCheckReport):
        return "done"
    return "fallback"


def fallback_node(state: SelfCheckState) -> SelfCheckState:
    reason = state.get("fallback_reason")
    if not reason and not settings.openai_api_key:
        reason = "OpenAI API key가 설정되지 않았습니다."
    return {
        "self_check": _fallback_report(
            state["project"],
            reason or "LLM 셀프 리포트 생성에 실패했습니다.",
        ),
    }


def build_self_check_graph():
    workflow = StateGraph(SelfCheckState)

    workflow.add_node("prepare_project", prepare_project_node)
    workflow.add_node("call_structured_llm", call_structured_llm_node)
    workflow.add_node("fallback", fallback_node)

    workflow.set_entry_point("prepare_project")
    workflow.add_conditional_edges("prepare_project", route_after_prepare, {
        "call_structured_llm": "call_structured_llm",
        "fallback": "fallback",
    })
    workflow.add_conditional_edges("call_structured_llm", route_after_structured_output, {
        "done": END,
        "fallback": "fallback",
    })
    workflow.add_edge("fallback", END)

    return workflow.compile()


self_check_graph = build_self_check_graph()


def check(project: ProjectCard) -> SelfCheckReport:
    result = self_check_graph.invoke({"project": project})
    report = result.get("self_check")
    if isinstance(report, SelfCheckReport):
        return report
    return _fallback_report(project, "자가점검 그래프 실행 결과가 올바르지 않습니다.")
