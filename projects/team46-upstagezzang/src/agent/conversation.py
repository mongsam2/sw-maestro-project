import json
import uuid
from datetime import datetime, timezone

from src.agent.prompts import EXTRACT_PROMPT, GREETING, NEXT_QUESTION_PROMPT
from src.config import settings
from src.core.embedding import get_embedding
from src.core.llm import get_llm
from src.core.parser import parse_llm_json
from src.db.metadata_store import MetadataStore
from src.db.vector_store import VectorStore
from src.models import AnalysisReport, ProjectCard, SelfCheckReport
from src.service.analyzer import analyze, extract_embedding_text
from src.service.checker import check as run_self_check


def _visibility_embedding_text(card: ProjectCard) -> str:
    if card.visibility == "summary":
        return f"{card.title} {' '.join(card.tech_stack)} {' '.join(card.key_features)}"
    return extract_embedding_text(card)

metadata_store = MetadataStore()
vector_store = VectorStore()

COLLECT_FIELDS = ["title", "team_name", "problem", "target_user", "solution", "tech_stack", "key_features", "mvp_scope"]

FIELD_PROMPTS = {
    "title": "어떤 프로젝트를 기획 중이신가요? 서비스 이름이나 주제를 간단히 알려주세요.",
    "team_name": "팀명이 어떻게 되시나요? (예: SW Maestro 10기 A팀)",
    "problem": "이 프로젝트가 해결하려는 **구체적인 문제**는 무엇인가요? 사용자가 현재 겪고 있는 불편함이나痛点을 설명해주세요.",
    "target_user": "어떤 사람들이 '{title}'의 **주 사용자**가 될까요? (연령대, 직업, 상황 등)",
    "solution": "이 문제를 **어떤 방식으로 해결**할 계획인가요? 핵심 접근 방식이나 차별화 전략을 설명해주세요.",
    "tech_stack": "사용할 **기술 스택**은 무엇인가요? (언어, 프레임워크, 라이브러리 등)",
    "key_features": "MVP에서 꼭 보여줄 **핵심 기능** 2~3가지를 알려주세요.",
    "mvp_scope": "짧은 기간 안에 구현할 **데모 범위(MVP)**는 어느 정도인가요? 어떤 기능까지 포함할 계획인가요?",
}


class ConversationAgent:
    def __init__(self):
        self.card = ProjectCard(
            project_id=str(uuid.uuid4())[:8],
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self.collected_fields = set()
        self.history = []
        self.done = False

    @property
    def missing_fields(self) -> list[str]:
        missing = []
        checks = {
            "title": lambda: not self.card.title or len(self.card.title.strip()) < 2,
            "team_name": lambda: not self.card.team_name or len(self.card.team_name.strip()) < 2,
            "problem": lambda: not self.card.problem or len(self.card.problem.strip()) < 5,
            "target_user": lambda: not self.card.target_user or len(self.card.target_user.strip()) < 2,
            "solution": lambda: not self.card.solution or len(self.card.solution.strip()) < 5,
            "tech_stack": lambda: not self.card.tech_stack,
            "key_features": lambda: not self.card.key_features,
            "mvp_scope": lambda: not self.card.mvp_scope or len(self.card.mvp_scope.strip()) < 5,
        }
        for field, check in checks.items():
            if check():
                missing.append(field)
        return missing

    def start(self) -> str:
        self.history = []
        return GREETING

    def step(self, user_input: str) -> tuple[str, str]:
        self.history.append(("user", user_input))

        if settings.openai_api_key:
            return self._llm_step(user_input)
        else:
            return self._rule_step(user_input)

    def _llm_step(self, user_input: str) -> tuple[str, str]:
        llm = get_llm()
        conv_text = "\n".join(f"{role}: {msg}" for role, msg in self.history[-12:])
        card_for_llm = self.card.model_dump(exclude={"project_id", "created_at", "updated_at"})
        current_json = json.dumps(card_for_llm, ensure_ascii=False, indent=2)

        response = llm.invoke(EXTRACT_PROMPT.format(
            conversation=conv_text,
            current_card=current_json,
        ))
        data = parse_llm_json(response.content)
        if not isinstance(data, dict) or not data:
            self.history.append(("assistant", "죄송합니다, 응답을 처리하는 데 문제가 생겼어요. 다시 한 번 말씀해주시겠어요? 😅"))
            return "죄송합니다, 응답을 처리하는 데 문제가 생겼어요. 다시 한 번 말씀해주시겠어요? 😅", "collecting"

        updates = data.get("updates", {})
        for field, value in updates.items():
            if value and value != "unchanged":
                if field in ("tech_stack", "key_features"):
                    if isinstance(value, list) and value and len(value) > 0:
                        setattr(self.card, field, value)
                        self.collected_fields.add(field)
                elif isinstance(value, str) and value.strip():
                    setattr(self.card, field, value)
                    self.collected_fields.add(field)

        llm_missing = data.get("missing_fields", [])
        llm_missing = [f for f in llm_missing if f in COLLECT_FIELDS]
        computed_missing = self.missing_fields

        llm_missing = [f for f in llm_missing if f in computed_missing]

        missing = llm_missing if llm_missing else computed_missing
        if not missing and computed_missing:
            missing = computed_missing
        response_text = data.get("response", "")

        if not missing:
            self.history.append(("assistant", response_text))
            return response_text, "confirm"

        if not response_text or len(response_text) < 5:
            response_text = self._generate_next_question(missing)

        self.history.append(("assistant", response_text))
        return response_text, "collecting"

    def _generate_next_question(self, missing: list[str]) -> str:
        if settings.openai_api_key:
            llm = get_llm()
            card_for_q = self.card.model_dump(exclude={"project_id", "created_at", "updated_at"})
            response = llm.invoke(NEXT_QUESTION_PROMPT.format(
                card_json=json.dumps(card_for_q, ensure_ascii=False, indent=2),
                missing_fields=", ".join(missing),
            ))
            return response.content.strip()

        for field in COLLECT_FIELDS:
            if field in missing and field in FIELD_PROMPTS:
                prompt = FIELD_PROMPTS[field].format(title=self.card.title or "이 프로젝트")
                return prompt
        return "모든 항목이 잘 정리되었네요! 저장하고 분석을 시작할까요? 😊"

    def _rule_step(self, user_input: str) -> tuple[str, str]:
        checks = [
            ("title", "좋은 프로젝트네요! 팀명이 어떻게 되시나요?"),
            ("team_name", "知道了! 그 프로젝트가 해결하려는 **구체적인 문제**는 무엇인가요? 사용자가 어떤 불편을 겪고 있나요?"),
            ("problem", "명확한 문제 정의네요. 어떤 사람들이 주로 사용할 **대상 사용자**인가요?"),
            ("target_user", "좋아요. 그럼 이 문제를 **어떻게 해결**할 계획인지 설명해주세요."),
            ("solution", "해결 방식이 흥미롭네요! 어떤 **기술 스택**을 사용할 예정인가요?"),
            ("tech_stack", "기술 스택을 정했군요. MVP에서 보여줄 **핵심 기능**은 무엇인가요?"),
            ("key_features", "좋습니다. 데모 범위(MVP)는 어느 정도인가요? 어떤 기능까지 포함할 계획인가요?"),
            ("mvp_scope", "모든 항목이 정리되었습니다! 확인하고 저장할까요?"),
        ]
        for field, response in checks:
            val = getattr(self.card, field)
            if field in ("tech_stack", "key_features"):
                if not val:
                    setattr(self.card, field, [t.strip() for t in user_input.replace(",", " ").split() if t.strip()])
                    self.collected_fields.add(field)
                    return response, "collecting"
            elif not val or (isinstance(val, str) and len(val.strip()) < 2):
                setattr(self.card, field, user_input)
                self.collected_fields.add(field)
                return response, "collecting"
        return "모든 항목이 정리되었습니다! 확인하고 저장할까요?", "confirm"

    def get_self_check(self) -> SelfCheckReport:
        return run_self_check(self.card)

    def save_and_analyze(self) -> AnalysisReport | None:
        now = datetime.now(timezone.utc).isoformat()
        self.card.updated_at = now
        if not self.card.created_at:
            self.card.created_at = now

        if settings.openai_api_key:
            embedding_text = _visibility_embedding_text(self.card)
            embedding = get_embedding(embedding_text)
            vector_store.add_project(self.card, embedding)
        metadata_store.save_project(self.card)

        return analyze(self.card, metadata_store, vector_store)
