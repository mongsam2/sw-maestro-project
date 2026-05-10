from src.agent.prompts import (
    MENTORING_SUMMARY_PROMPT,
    SIMILARITY_ANALYSIS_PROMPT,
)
from src.config import settings
from src.core.embedding import get_embedding
from src.core.llm import get_llm
from src.core.parser import parse_llm_json
from src.db.metadata_store import MetadataStore
from src.db.vector_store import VectorStore
from src.models import AnalysisReport, ProjectCard, SimilarityResult
from src.service.cross_insight import generate_cross_insights  # noqa: F401 — re-exported
from src.models import (
    AnalysisReport,
    CrossInsight,
    DefenseGuide,
    MentoringOneMinute,
    ProjectCard,
    SimilarityResult,
)


def extract_embedding_text(card: ProjectCard) -> str:
    return (
        f"{card.title} {card.problem} {card.target_user} {card.solution} "
        f"{' '.join(card.tech_stack)} {' '.join(card.key_features)}"
    )


def _sanitize_for_display(proj: ProjectCard) -> ProjectCard:
    if proj.visibility == "summary":
        return ProjectCard(
            project_id=proj.project_id,
            title=proj.title,
            team_name=proj.team_name,
            problem="[요약 공개로 인해 비공개]",
            target_user="[비공개]", solution="[비공개]",
            key_features=proj.key_features, tech_stack=proj.tech_stack,
            mvp_scope=proj.mvp_scope,
            visibility="summary",
            created_at=proj.created_at, updated_at=proj.updated_at,
        )
    return proj


def search_similar(card: ProjectCard, metadata_store: MetadataStore, vector_store: VectorStore) -> AnalysisReport:
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

    similar_projects = []
    candidates_text = []
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
                f"Problem: [요약 공개로 인해 비공개]\n"
                f"Target User: [비공개]\nSolution: [비공개]"
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

    results = []
    if settings.openai_api_key:
        llm = get_llm()
        response = llm.invoke(SIMILARITY_ANALYSIS_PROMPT.format(
            query_project=card.model_dump_json(),
            similar_candidates="\n\n".join(candidates_text),
            threshold_high=settings.similarity_threshold_high,
            threshold_medium=settings.similarity_threshold_medium,
        ))
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
                results.append(SimilarityResult(
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
                ))
    else:
        for proj, score in similar_projects:
            sanitized = _sanitize_for_display(proj)
            results.append(SimilarityResult(
                project=sanitized,
                overall_score=score,
                overlapping_aspects=["문제 정의 영역에서 유사성이 감지됩니다 (API key 미설정)"],
                distinct_aspects=["API key 설정 시 상세 분석 제공됩니다"],
                risk_level="Medium" if score > 0.7 else "Low",
                reasoning=f"전체 유사도 점수: {score:.2f}",
                recommended_action="OpenAI API key를 설정하고 다시 분석해보세요.",
            ))

    return AnalysisReport(
        query_project=card,
        similar_projects=results,
        cross_insights=[],
        mentoring_summary="",
        mentoring_one_minute=None,
        expected_questions=[],
    )



def generate_mentoring_summary(report: AnalysisReport) -> AnalysisReport:
    card = report.query_project
    if not card:
        return report

    if settings.openai_api_key:
        llm = get_llm()
        analysis_summary = ""
        if report.similar_projects:
            for sp in report.similar_projects:
                analysis_summary += f"- {sp.project.title}: 유사도 {sp.overall_score:.2f}, 위험도 {sp.risk_level}\n"

        response = llm.invoke(MENTORING_SUMMARY_PROMPT.format(
            project_json=card.model_dump_json(),
            analysis_summary=analysis_summary or "유사한 프로젝트 없음",
        ))
        summary_data = parse_llm_json(response.content)
        if isinstance(summary_data, dict) and summary_data:
            one_min = summary_data.get("one_minute_summary")
            if isinstance(one_min, dict):
                report.mentoring_one_minute = MentoringOneMinute(
                    problem=one_min.get("problem", ""),
                    target_user=one_min.get("target_user", ""),
                    solution=one_min.get("solution", ""),
                    expected_value=one_min.get("expected_value", ""),
                )
            else:
                report.mentoring_one_minute = None

            diff_points = summary_data.get("differentiation_points", [])
            report.differentiation_points = [
                p for p in diff_points if isinstance(p, str)
            ] if isinstance(diff_points, list) else []

            guides: list[DefenseGuide] = []
            questions = summary_data.get("expected_questions", [])
            if isinstance(questions, list):
                for q in questions:
                    if isinstance(q, dict):
                        guides.append(DefenseGuide(
                            focus=q.get("focus", ""),
                            question=q.get("question", ""),
                            prep_tip=q.get("prep_tip") or q.get("suggested_answer", ""),
                        ))
            report.expected_questions = guides
        else:
            report.mentoring_summary = "멘토링 요약 생성에 실패했습니다."
            report.mentoring_one_minute = None
            report.differentiation_points = []
            report.expected_questions = []
    else:
        report.mentoring_one_minute = MentoringOneMinute(
            problem=card.problem,
            target_user=card.target_user,
            solution=card.solution,
            expected_value="API key 설정 후 상세 기대 효과가 생성됩니다.",
        )
        report.differentiation_points = [
            "API key 설정 시 유사도 분석 기반 차별점이 자동 생성됩니다.",
        ]
        report.expected_questions = [
            DefenseGuide(
                focus="Problem-Solution Fit",
                question="정의한 문제를 이 해결 방식이 정말 푼다는 근거는 무엇인가요?",
                prep_tip="문제 발생 빈도/강도 데이터와 기존 대안의 한계를 1~2개 정리해 가세요.",
            ),
            DefenseGuide(
                focus="타겟의 명확성",
                question="초기 사용자를 더 구체적으로 좁힐 수 있나요?",
                prep_tip="가장 절박한 사용자 1명을 페르소나로 적어보고 그 이유를 준비하세요.",
            ),
            DefenseGuide(
                focus="가설 검증 방식",
                question="MVP 기간 안에 핵심 가설을 어떻게 검증할 계획인가요?",
                prep_tip="검증 지표 1~2개와 그 측정 방법을 미리 정해두세요.",
            ),
        ]

    return report


def analyze(card: ProjectCard, metadata_store: MetadataStore, vector_store: VectorStore) -> AnalysisReport:
    report = search_similar(card, metadata_store, vector_store)
    report = generate_cross_insights(report)
    report = generate_mentoring_summary(report)
    return report
