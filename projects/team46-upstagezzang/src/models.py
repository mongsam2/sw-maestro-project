from pydantic import BaseModel


class ProjectCard(BaseModel):
    project_id: str = ""
    team_name: str = ""
    title: str = ""
    problem: str = ""
    target_user: str = ""
    solution: str = ""
    key_features: list[str] = []
    tech_stack: list[str] = []
    mvp_scope: str = ""
    visibility: str = "summary"
    created_at: str = ""
    updated_at: str = ""


class SimilarityResult(BaseModel):
    project: ProjectCard
    overall_score: float
    problem_score: float = 0.0
    target_user_score: float = 0.0
    solution_score: float = 0.0
    tech_stack_score: float = 0.0
    overlapping_aspects: list[str] = []
    distinct_aspects: list[str] = []
    risk_level: str = "Low"
    reasoning: str = ""
    recommended_action: str = ""


class CrossInsight(BaseModel):
    category: str = ""
    source_project_id: str = ""
    source_project_title: str = ""
    title: str = ""
    description: str = ""
    change_type: str = ""
    why_needed: str = ""
    next_decision: str = ""


class MentoringOneMinute(BaseModel):
    problem: str = ""
    target_user: str = ""
    solution: str = ""
    expected_value: str = ""


class DefenseGuide(BaseModel):
    focus: str = ""
    question: str = ""
    prep_tip: str = ""


class AnalysisReport(BaseModel):
    query_project: ProjectCard
    similar_projects: list[SimilarityResult] = []
    cross_insights: list[CrossInsight] = []
    mentoring_summary: str = ""
    mentoring_one_minute: MentoringOneMinute | None = None
    differentiation_points: list[str] = []
    expected_questions: list[DefenseGuide] = []


class SelfCheckDimension(BaseModel):
    key: str = ""
    label: str = ""
    score: int = 0
    rationale: str = ""
    evidence: str = ""
    action: str = ""


class SelfCheckAction(BaseModel):
    priority: str = ""
    title: str = ""
    detail: str = ""
    target_field: str = ""
    example: str = ""


class SelfCheckReport(BaseModel):
    missing_fields: list[str] = []
    suggestions: list[str] = []
    clarity_score: int = 0
    completeness_score: int = 0
    overall_score: int = 0
    readiness_level: str = ""
    one_line_summary: str = ""
    reasoning: str = ""
    strengths: list[str] = []
    weaknesses: list[str] = []
    dimension_scores: list[SelfCheckDimension] = []
    priority_actions: list[SelfCheckAction] = []
    mentor_questions: list[str] = []
    risk_flags: list[str] = []
    revised_pitch: str = ""
    web_findings: str = ""
