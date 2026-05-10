from src.config import settings
from src.core.llm import get_llm
from src.core.parser import parse_llm_json
from src.models import AnalysisReport, CrossInsight

CATEGORIES = [
    "Target Narrowing",
    "Problem Reframing",
    "Tech Combination",
    "MVP Sharpening",
    "Collaboration Potential",
]

CATEGORY_LABELS = {
    "Target Narrowing": "타겟 좁히기",
    "Problem Reframing": "문제 재정의",
    "Tech Combination": "기술 조합",
    "MVP Sharpening": "MVP 집중",
    "Collaboration Potential": "협업 가능성",
}

CATEGORY_ICONS = {
    "Target Narrowing": "🎯",
    "Problem Reframing": "🔄",
    "Tech Combination": "🔧",
    "MVP Sharpening": "⚡",
    "Collaboration Potential": "🤝",
}

CATEGORY_COLORS = {
    "Target Narrowing": "blue",
    "Problem Reframing": "violet",
    "Tech Combination": "green",
    "MVP Sharpening": "orange",
    "Collaboration Potential": "red",
}


def _build_similar_projects_info(report: AnalysisReport) -> str:
    parts = []
    for i, sim in enumerate(report.similar_projects, 1):
        proj = sim.project
        overlap = ", ".join(sim.overlapping_aspects) if sim.overlapping_aspects else "없음"
        distinct = ", ".join(sim.distinct_aspects) if sim.distinct_aspects else "없음"
        tech = ", ".join(proj.tech_stack) if proj.tech_stack else "미정"
        parts.append(
            f"[유사 기획 {i}] ID: {proj.project_id}\n"
            f"제목: {proj.title}\n"
            f"팀: {proj.team_name or '알 수 없음'}\n"
            f"기술 스택: {tech}\n"
            f"겹치는 항목: {overlap}\n"
            f"차별 가능 항목: {distinct}\n"
            f"중복 위험도: {sim.risk_level}  (유사도 {sim.overall_score:.0%})"
        )
    return "\n\n".join(parts)


def _build_fallback_insights(report: AnalysisReport) -> list[CrossInsight]:
    card = report.query_project
    top = report.similar_projects[0] if report.similar_projects else None
    second = report.similar_projects[1] if len(report.similar_projects) > 1 else top
    top_title = top.project.title if top else "유사 기획"
    second_title = second.project.title if second else top_title
    tech_str = ", ".join(card.tech_stack[:3]) if card.tech_stack else "현재 기술 스택"
    top_tech = ", ".join(top.project.tech_stack[:2]) if top and top.project.tech_stack else "유사 팀 기술"

    return [
        CrossInsight(
            category="Target Narrowing",
            source_project_id=top.project.project_id if top else "",
            source_project_title=top_title,
            title="타겟 사용 장면 좁히기",
            description=(
                f"'{card.target_user}' 전체를 타겟으로 잡는 것은 '{top_title}'과 겹칩니다. "
                "사용자가 서비스를 가장 절실히 필요로 하는 구체적인 상황(예: 멘토링 전날 밤, "
                "아이디어가 막힌 회의 중)으로 타겟을 좁히면 차별화가 가능합니다."
            ),
            change_type=f"{card.target_user} 전체 → 특정 상황·단계의 사용자로 좁히기",
            why_needed=f"'{top_title}'과 타겟이 겹치므로, 더 구체적인 사용 장면이 핵심 차별점이 됩니다.",
            next_decision="우리 서비스를 가장 절실하게 찾는 사용자의 구체적인 상황은 무엇인가?",
        ),
        CrossInsight(
            category="Problem Reframing",
            source_project_id=second.project.project_id if second else "",
            source_project_title=second_title,
            title="문제 정의 각도 전환",
            description=(
                f"'{card.problem}'을 '증상' 관점이 아니라 '근본 원인' 또는 '결과' 관점으로 재정의해보세요. "
                f"'{second_title}'이 같은 문제 영역을 다루고 있다면, "
                "개인이 아닌 팀·조직 수준의 문제로 재정의하면 새로운 포지셔닝이 생깁니다."
            ),
            change_type="증상·표면 문제 → 근본 원인 또는 팀/조직 레벨 문제로 재정의",
            why_needed="동일한 문제 영역에서 차별화하려면 문제를 바라보는 시각 자체를 달리해야 합니다.",
            next_decision="우리 서비스가 해결하는 문제의 궁극적인 원인은 무엇이고, 누가 가장 큰 고통을 받는가?",
        ),
        CrossInsight(
            category="Tech Combination",
            source_project_id=top.project.project_id if top else "",
            source_project_title=top_title,
            title="기술 조합으로 차별화",
            description=(
                f"현재 기술 스택({tech_str})을 '{top_title}'이 사용하는 {top_tech}와 비교해보세요. "
                "유사 서비스가 사용하지 않는 기술을 핵심 기능에 접목하면 "
                "기능적 차별점을 기술 레벨에서 만들 수 있습니다."
            ),
            change_type=f"기존 스택({tech_str}) → '{top_title}'이 없는 기술을 추가해 차별화",
            why_needed="기술 스택 차별화는 기능 차별화로 이어지며, 경쟁 포지셔닝을 기술 레벨에서 강화합니다.",
            next_decision="어떤 기술을 추가·변경하면 유사 서비스 대비 명확한 기능 차별점이 생기는가?",
        ),
        CrossInsight(
            category="MVP Sharpening",
            source_project_id=top.project.project_id if top else "",
            source_project_title=top_title,
            title="핵심 차별 장면 하나에 집중",
            description=(
                f"MVP에서 '{top_title}'과 겹치는 기능을 제거하고, "
                "우리 팀만이 보여줄 수 있는 하나의 강력한 사용 장면에 집중하세요. "
                "범위를 좁힐수록 완성도가 높아지고, 멘토링에서 더 명확한 피드백을 받을 수 있습니다."
            ),
            change_type="넓은 기능 범위 → 우리만의 핵심 차별 장면 1개에 집중한 데모",
            why_needed="겹치는 기능에 리소스를 분산하는 것보다 차별화된 장면의 완성도를 높이는 것이 임팩트가 큽니다.",
            next_decision="MVP 데모에서 반드시 보여야 할 '우리만의 핵심 차별 장면'은 무엇인가?",
        ),
        CrossInsight(
            category="Collaboration Potential",
            source_project_id=top.project.project_id if top else "",
            source_project_title=top_title,
            title=f"{top_title}팀과 역할 분담",
            description=(
                f"'{card.title}'과 '{top_title}'은 경쟁보다 협업으로 더 큰 가치를 만들 수 있습니다. "
                "예: 한 팀이 데이터 수집·입력 UX를, 다른 팀이 분석·인사이트 제공을 담당하는 방식으로 "
                "각자의 강점을 살린 보완적 구조를 만들 수 있습니다."
            ),
            change_type="경쟁 관계 → 보완적 역할 분담 구조로 재정의",
            why_needed="유사한 방향의 팀이 협업하면 각자 강점을 살려 더 완성도 높은 결과물을 만들 수 있습니다.",
            next_decision=f"'{top_title}'팀과 협업한다면 어떤 부분을 분담하고 어떤 시너지를 기대할 수 있는가?",
        ),
    ]


def generate_cross_insights(report: AnalysisReport) -> AnalysisReport:
    if not report.similar_projects:
        return report

    if settings.openai_api_key:
        from src.agent.prompts import CROSS_INSIGHT_PROMPT

        llm = get_llm()
        similar_info = _build_similar_projects_info(report)
        response = llm.invoke(CROSS_INSIGHT_PROMPT.format(
            query_project=report.query_project.model_dump_json(ensure_ascii=False),
            similar_projects_info=similar_info,
        ))
        insights_data = parse_llm_json(response.content)
        if not isinstance(insights_data, list):
            insights_data = []

        insights: list[CrossInsight] = []
        seen_categories: set[str] = set()
        for item in insights_data:
            category = item.get("category", "")
            insights.append(CrossInsight(
                category=category,
                source_project_id=item.get("source_project_id", ""),
                source_project_title=item.get("source_project_title", ""),
                title=item.get("title", ""),
                description=item.get("description", ""),
                change_type=item.get("change_type", ""),
                why_needed=item.get("why_needed", ""),
                next_decision=item.get("next_decision", ""),
            ))
            seen_categories.add(category)

        # 카테고리 누락 시 fallback 항목으로 보완
        if len(insights) < 2:
            insights = _build_fallback_insights(report)
        else:
            fallbacks = _build_fallback_insights(report)
            for fb in fallbacks:
                if fb.category not in seen_categories:
                    insights.append(fb)
                    seen_categories.add(fb.category)

        report.cross_insights = insights
    else:
        report.cross_insights = _build_fallback_insights(report)

    return report
