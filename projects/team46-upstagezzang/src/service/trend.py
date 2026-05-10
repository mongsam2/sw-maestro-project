import json
from collections import Counter

from src.config import settings
from src.core.llm import get_llm
from src.core.parser import parse_llm_json
from src.models import ProjectCard

TREND_ANALYSIS_PROMPT = """다음은 등록된 프로젝트 기획안들의 목록이야. 각 프로젝트의 도메인(분야)을 분석해줘.

프로젝트 목록:
{projects_json}

각 프로젝트에 대해 JSON 배열로 응답:
[{{
  "project_id": "프로젝트 ID",
  "domain": "주요 도메인 (한국어, 예: 교육, 헬스, 엔터테인먼트, AI, 여행, 금융 등)",
  "target_group": "주요 대상 그룹 (한국어, 예: 20대 직장인, 대학생, 일반인 등)"
}}]

반드시 한국어로 응답하고, JSON 배열 외 아무 텍스트도 포함하지 마."""


def analyze_trends(projects: list[ProjectCard]) -> dict:
    if not projects:
        return {"domains": {}, "tech_stacks": {}, "target_groups": {}, "total": 0}

    tech_counts = Counter()
    for p in projects:
        for t in p.tech_stack:
            if t.strip():
                tech_counts[t.strip()] += 1

    domain_counts: dict[str, int] = Counter()
    target_counts: dict[str, int] = Counter()
    categorized = False

    if settings.openai_api_key and len(projects) > 0:
        try:
            llm = get_llm()
            projects_data = []
            for p in projects:
                projects_data.append({
                    "project_id": p.project_id,
                    "title": p.title,
                    "problem": p.problem,
                    "target_user": p.target_user,
                    "solution": p.solution,
                    "tech_stack": p.tech_stack,
                })
            response = llm.invoke(TREND_ANALYSIS_PROMPT.format(
                projects_json=json.dumps(projects_data, ensure_ascii=False, indent=2),
            ))
            data = parse_llm_json(response.content)
            if isinstance(data, list):
                for item in data:
                    domain = item.get("domain", "기타")
                    target = item.get("target_group", "기타")
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
                    target_counts[target] = target_counts.get(target, 0) + 1
                categorized = True
        except Exception:
            pass

    if not categorized:
        keywords = {
            "AI/ML": ["ai", "llm", "인공지능", "머신러닝", "학습", "gpt", "추천"],
            "교육": ["학습", "교육", "코딩", "강의", "과외", "수업", "스터디", "퀴즈", "온라인 저지"],
            "헬스": ["운동", "헬스", "건강", "식단", "루틴", "요가", "피트니스", "다이어트"],
            "쇼핑/커머스": ["쇼핑", "구매", "패션", "스타일링", "마켓", "중고", "쇼핑몰", "큐레이션"],
            "여행": ["여행", "맛집", "숙소", "관광", "투어", "트립", "3d 월드", "vr"],
            "커리어/취업": ["취업", "이직", "커리어", "포트폴리오", "면접", "멘토링", "자소서"],
            "소셜/커뮤니티": ["소셜", "커뮤니티", "채팅", "매칭", "모임", "친구", "소모임"],
            "생산성/도구": ["일정", "관리", "자동화", "분석", "설문", "문서", "일기"],
            "반려동물": ["반려", "동물", "펫", "강아지", "고양이"],
        }
        for p in projects:
            full_text = f"{p.title} {p.problem} {p.solution} {' '.join(p.tech_stack)}"
            matched = False
            for domain, kws in keywords.items():
                if any(kw in full_text.lower() for kw in kws):
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
                    matched = True
                    break
            if not matched:
                domain_counts["기타"] = domain_counts.get("기타", 0) + 1

            target_counts["기타"] = target_counts.get("기타", 0) + 1

    return {
        "domains": dict(domain_counts.most_common(10)),
        "tech_stacks": dict(tech_counts.most_common(15)),
        "target_groups": dict(target_counts.most_common(10)),
        "total": len(projects),
        "categorized": categorized,
    }
