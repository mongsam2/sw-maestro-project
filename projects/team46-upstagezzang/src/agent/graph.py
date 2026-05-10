import json
import operator
import uuid
from datetime import datetime, timezone
from typing import Annotated

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from src.agent.prompts import (
    EXTRACT_PROMPT,
    GREETING,
    NEXT_QUESTION_PROMPT,
    SIMILARITY_ANALYSIS_PROMPT,
)
from src.config import settings
from src.core.embedding import get_embedding
from src.core.llm import get_llm
from src.core.parser import parse_llm_json
from src.db.metadata_store import MetadataStore
from src.db.vector_store import VectorStore
from src.models import AnalysisReport, ProjectCard, SimilarityResult
from src.service.analyzer import (
    extract_embedding_text,
    generate_cross_insights,
    generate_mentoring_summary,
)
from src.service.checker import check as run_self_check

metadata_store = MetadataStore()
vector_store = VectorStore()


def _new_card() -> ProjectCard:
    now = datetime.now(timezone.utc).isoformat()
    return ProjectCard(
        project_id=str(uuid.uuid4())[:8],
        created_at=now,
        updated_at=now,
    )


def _generate_question(card: ProjectCard, missing_fields: list[str]) -> str:
    if not settings.openai_api_key:
        prompts: dict[str, str] = {
            "title": "어떤 프로젝트를 기획 중이신가요? 서비스 이름이나 주제를 알려주세요.",
            "team_name": "팀명이 어떻게 되시나요?",
            "problem": "이 프로젝트가 해결하려는 구체적인 문제는 무엇인가요?",
            "target_user": "어떤 사람들이 주 사용자가 될까요? (연령대, 직업, 상황 등)",
            "solution": "이 문제를 어떤 방식으로 해결할 계획인가요?",
            "tech_stack": "사용할 기술 스택은 무엇인가요? (언어, 프레임워크, 라이브러리 등)",
            "key_features": "MVP에서 보여줄 핵심 기능 2~3가지를 알려주세요.",
            "mvp_scope": "짧은 기간에 구현할 데모 범위는 어느 정도인가요?",
        }
        for f in missing_fields:
            if f in prompts:
                return prompts[f]
        return "더 알려주실 내용이 있나요?"

    llm = get_llm()
    card_json = card.model_dump_json(exclude={"project_id", "created_at", "updated_at"})
    response = llm.invoke(
        NEXT_QUESTION_PROMPT.format(
            card_json=card_json,
            missing_fields=", ".join(missing_fields),
        )
    )
    return response.content.strip()


# ============================================================
# Interactive chat graph (Streamlit)
# ============================================================


class ChatState(dict):
    messages: Annotated[list[dict], operator.add] = []
    card: dict | None = None
    missing_fields: list[str] = []
    current_question: str = ""
    self_check: dict | None = None
    report: dict | None = None
    phase: str = ""


def greeting_node(state: dict) -> dict:
    card = _new_card()
    return {
        "messages": [{"role": "assistant", "content": GREETING}],
        "card": card.model_dump(),
        "phase": "collecting",
    }


def wait_input_node(state: dict) -> dict:
    user_input = interrupt("input")
    return {
        "messages": [{"role": "user", "content": user_input}],
    }


def extract_node(state: dict) -> dict:
    card = ProjectCard(**state["card"]) if state.get("card") else _new_card()
    messages = state.get("messages", [])
    if not messages:
        return {"card": card.model_dump()}

    conversation = "\n".join(f"{m['role']}: {m['content']}" for m in messages[-12:])

    if not settings.openai_api_key:
        last_user = messages[-1]["content"] if messages else ""
        for field in ["title", "team_name", "problem", "target_user", "solution"]:
            if not getattr(card, field) or len(str(getattr(card, field, "")).strip()) < 2:
                setattr(card, field, last_user)
                return {"card": card.model_dump()}
        if not card.tech_stack:
            card.tech_stack = [t.strip() for t in last_user.replace(",", " ").split() if t.strip()]
            return {"card": card.model_dump()}
        if not card.key_features:
            card.key_features = [f.strip() for f in last_user.replace(",", " ").split() if f.strip()]
            return {"card": card.model_dump()}
        return {"card": card.model_dump()}

    llm = get_llm()
    card_json = json.dumps(
        card.model_dump(exclude={"project_id", "created_at", "updated_at"}),
        ensure_ascii=False,
        indent=2,
    )
    response = llm.invoke(
        EXTRACT_PROMPT.format(
            conversation=conversation,
            current_card=card_json,
        )
    )
    data = parse_llm_json(response.content)
    if not isinstance(data, dict) or not data:
        return {"card": card.model_dump()}

    updates = data.get("updates", {})
    for field, value in updates.items():
        if value and value != "unchanged":
            if field in ("tech_stack", "key_features"):
                if isinstance(value, list) and value:
                    setattr(card, field, value)
            elif isinstance(value, str) and value.strip():
                if hasattr(card, field):
                    setattr(card, field, value)

    return {"card": card.model_dump()}


def check_missing_node(state: dict) -> dict:
    card = ProjectCard(**state["card"]) if state.get("card") else _new_card()
    missing: list[str] = []
    checks: list[tuple[str, object]] = [
        ("title", lambda c: not c.title or len(c.title.strip()) < 2),
        ("team_name", lambda c: not c.team_name or len(c.team_name.strip()) < 2),
        ("problem", lambda c: not c.problem or len(c.problem.strip()) < 5),
        ("target_user", lambda c: not c.target_user or len(c.target_user.strip()) < 2),
        ("solution", lambda c: not c.solution or len(c.solution.strip()) < 5),
        ("tech_stack", lambda c: not c.tech_stack),
        ("key_features", lambda c: not c.key_features),
        ("mvp_scope", lambda c: not c.mvp_scope or len(c.mvp_scope.strip()) < 5),
    ]
    for field, check_fn in checks:
        if check_fn(card):
            missing.append(field)

    if missing:
        question = _generate_question(card, missing)
        return {
            "card": card.model_dump(),
            "missing_fields": missing,
            "current_question": question,
            "phase": "collecting",
        }
    return {
        "card": card.model_dump(),
        "missing_fields": [],
        "phase": "confirming",
    }


def route_after_check(state: dict) -> str:
    if state.get("missing_fields"):
        return "ask_question"
    return "self_check"


def ask_question_node(state: dict) -> dict:
    question = state.get("current_question", "더 알려주실 내용이 있나요?")
    return {
        "messages": [{"role": "assistant", "content": question}],
    }


def run_self_check_chat(state: dict) -> dict:
    card = ProjectCard(**state["card"]) if state.get("card") else _new_card()
    result = run_self_check(card)
    metadata_store.save_reports(card.project_id, self_check=result)
    return {"self_check": result.model_dump()}


def confirm_interrupt_node(state: dict) -> dict:
    action = interrupt("confirm")
    return {"phase": action}


def route_after_confirm(state: dict) -> str:
    phase = state.get("phase", "")
    if phase == "save":
        return "embed_and_store"
    elif phase == "edit":
        return "ask_question"
    elif phase == "collecting":
        return "ask_question"
    return "ask_question"


def embed_and_store_node(state: dict) -> dict:
    card = ProjectCard(**state["card"]) if state.get("card") else _new_card()
    now = datetime.now(timezone.utc).isoformat()
    card.updated_at = now

    if settings.openai_api_key:
        if card.visibility == "summary":
            text = f"{card.title} {' '.join(card.tech_stack)} {' '.join(card.key_features)}"
        else:
            text = extract_embedding_text(card)
        embedding = get_embedding(text)
        vector_store.add_project(card, embedding)
    metadata_store.save_project(card)

    return {"card": card.model_dump(), "phase": "analyzing"}


def search_similar_node(state: dict) -> dict:
    card = ProjectCard(**state["card"]) if state.get("card") else _new_card()
    report = _search_similar_impl(card)
    return {"report": report.model_dump()}


def _search_similar_impl(card: ProjectCard) -> AnalysisReport:
    if vector_store.count() <= 1:
        return AnalysisReport(
            query_project=card,
            similar_projects=[],
            cross_insights=[],
            mentoring_summary="등록된 기획안이 충분하지 않아 유사도 분석을 할 수 없습니다.",
        )

    embedding_text = extract_embedding_text(card)
    embedding = get_embedding(embedding_text)
    total = vector_store.count()
    similar = vector_store.search_similar(embedding, n_results=min(total, 20))

    similar_projects: list[tuple[ProjectCard, float]] = []
    candidates_text: list[str] = []
    for pid, dist, doc in similar:
        if pid == card.project_id:
            continue
        proj = metadata_store.get_project(pid)
        if proj is None:
            continue
        if proj.visibility == "summary":
            candidates_text.append(
                f"Project {proj.project_id}: Title: {proj.title}\n"
                f"Tech Stack: {', '.join(proj.tech_stack)}\n"
                f"Problem: [비공개]\nTarget User: [비공개]\nSolution: [비공개]"
            )
        else:
            candidates_text.append(f"Project {proj.project_id}: {doc}")
        similar_projects.append((proj, 1.0 - dist))

    if not similar_projects:
        return AnalysisReport(
            query_project=card,
            similar_projects=[],
            cross_insights=[],
            mentoring_summary="유사한 기획안을 찾을 수 없습니다.",
        )

    results: list[SimilarityResult] = []
    if settings.openai_api_key:
        llm = get_llm()
        response = llm.invoke(
            SIMILARITY_ANALYSIS_PROMPT.format(
                query_project=card.model_dump_json(),
                similar_candidates="\n\n".join(candidates_text),
                threshold_high=settings.similarity_threshold_high,
                threshold_medium=settings.similarity_threshold_medium,
            )
        )
        analysis_data = parse_llm_json(response.content)
        if not isinstance(analysis_data, list):
            analysis_data = []

        for item in analysis_data:
            pid = item.get("project_id", "")
            matched = None
            for proj, score in similar_projects:
                if proj.project_id == pid:
                    matched = proj
                    break
            if matched is None and similar_projects:
                matched = similar_projects[0][0]

            if matched:
                sanitized = _sanitize_for_display(matched)
                results.append(
                    SimilarityResult(
                        project=sanitized,
                        overall_score=item.get("overall_score", 0.0),
                        problem_score=item.get("problem_score", 0.0),
                        target_user_score=item.get("target_user_score", 0.0),
                        solution_score=item.get("solution_score", 0.0),
                        tech_stack_score=item.get("tech_stack_score", 0.0),
                        overlapping_aspects=item.get("overlapping_aspects", []),
                        distinct_aspects=item.get("distinct_aspects", []),
                        risk_level=item.get("risk_level", "Low"),
                        reasoning=item.get("reasoning", ""),
                        recommended_action=item.get("recommended_action", ""),
                    )
                )
    else:
        for proj, score in similar_projects:
            sanitized = _sanitize_for_display(proj)
            results.append(
                SimilarityResult(
                    project=sanitized,
                    overall_score=score,
                    overlapping_aspects=["문제 정의 영역에서 유사성이 감지됩니다 (API key 미설정)"],
                    distinct_aspects=["API key 설정 시 상세 분석 제공됩니다"],
                    risk_level="Medium" if score > 0.7 else "Low",
                    reasoning=f"전체 유사도 점수: {score:.2f}",
                    recommended_action="OpenAI API key를 설정하고 다시 분석해보세요.",
                )
            )

    return AnalysisReport(
        query_project=card,
        similar_projects=results,
        cross_insights=[],
        mentoring_summary="",
        mentoring_one_minute=None,
        expected_questions=[],
    )


def _sanitize_for_display(proj: ProjectCard) -> ProjectCard:
    if proj.visibility == "summary":
        return ProjectCard(
            project_id=proj.project_id,
            title=proj.title,
            team_name=proj.team_name,
            problem="[비공개]",
            target_user="[비공개]",
            solution="[비공개]",
            key_features=proj.key_features,
            tech_stack=proj.tech_stack,
            mvp_scope=proj.mvp_scope,
            visibility="summary",
            created_at=proj.created_at,
            updated_at=proj.updated_at,
        )
    return proj


def cross_insights_node(state: dict) -> dict:
    if not state.get("report"):
        return {}
    report = AnalysisReport(**state["report"])
    report = generate_cross_insights(report)
    return {"report": report.model_dump()}


def mentoring_node(state: dict) -> dict:
    if not state.get("report"):
        return {}
    report = AnalysisReport(**state["report"])
    report = generate_mentoring_summary(report)
    metadata_store.save_reports(
        report.query_project.project_id,
        self_check=state.get("self_check"),
        analysis_report=report,
    )
    return {"report": report.model_dump(), "phase": "done"}


_chat_checkpointer = MemorySaver()


def build_chat_graph() -> StateGraph:
    workflow = StateGraph(ChatState)

    workflow.add_node("greeting", greeting_node)
    workflow.add_node("wait_input", wait_input_node)
    workflow.add_node("extract_fields", extract_node)
    workflow.add_node("check_missing", check_missing_node)
    workflow.add_node("ask_question", ask_question_node)
    workflow.add_node("self_check", run_self_check_chat)
    workflow.add_node("confirm", confirm_interrupt_node)
    workflow.add_node("embed_and_store", embed_and_store_node)
    workflow.add_node("search_similar", search_similar_node)
    workflow.add_node("cross_insights", cross_insights_node)
    workflow.add_node("mentoring", mentoring_node)

    workflow.set_entry_point("greeting")
    workflow.add_edge("greeting", "wait_input")
    workflow.add_edge("wait_input", "extract_fields")
    workflow.add_edge("extract_fields", "check_missing")

    workflow.add_conditional_edges(
        "check_missing",
        route_after_check,
        {
            "ask_question": "ask_question",
            "self_check": "self_check",
        },
    )

    workflow.add_edge("ask_question", "wait_input")

    workflow.add_edge("self_check", "confirm")

    workflow.add_conditional_edges(
        "confirm",
        route_after_confirm,
        {
            "embed_and_store": "embed_and_store",
            "ask_question": "ask_question",
        },
    )

    workflow.add_edge("embed_and_store", "search_similar")
    workflow.add_edge("search_similar", "cross_insights")
    workflow.add_edge("cross_insights", "mentoring")
    workflow.add_edge("mentoring", END)

    return workflow.compile(checkpointer=_chat_checkpointer)


chat_graph = build_chat_graph()
