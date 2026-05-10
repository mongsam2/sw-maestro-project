import json
import os
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, Text, create_engine, inspect
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import settings
from src.models import AnalysisReport, ProjectCard, SelfCheckReport

Base = declarative_base()


class ProjectRecord(Base):
    __tablename__ = "projects"

    project_id = Column(String, primary_key=True)
    team_name = Column(String, default="")
    title = Column(Text, default="")
    problem = Column(Text, default="")
    target_user = Column(Text, default="")
    solution = Column(Text, default="")
    key_features = Column(Text, default="[]")
    tech_stack = Column(Text, default="[]")
    mvp_scope = Column(Text, default="")
    visibility = Column(String, default="summary")
    self_check_report = Column(Text, default="")
    analysis_report = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class MetadataStore:
    def __init__(self):
        db_path = os.path.join(settings.data_dir, "metadata.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self._ensure_report_columns()
        self.Session = sessionmaker(bind=self.engine)

    def _ensure_report_columns(self):
        existing = {col["name"] for col in inspect(self.engine).get_columns("projects")}
        with self.engine.begin() as conn:
            if "self_check_report" not in existing:
                conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN self_check_report TEXT DEFAULT ''")
            if "analysis_report" not in existing:
                conn.exec_driver_sql("ALTER TABLE projects ADD COLUMN analysis_report TEXT DEFAULT ''")

    def save_project(self, card: ProjectCard) -> str:
        session = self.Session()
        try:
            record = session.get(ProjectRecord, card.project_id)
            if record is None:
                record = ProjectRecord(project_id=card.project_id)
                session.add(record)

            record.team_name = card.team_name
            record.title = card.title
            record.problem = card.problem
            record.target_user = card.target_user
            record.solution = card.solution
            record.key_features = json.dumps(card.key_features, ensure_ascii=False)
            record.tech_stack = json.dumps(card.tech_stack, ensure_ascii=False)
            record.mvp_scope = card.mvp_scope
            record.visibility = card.visibility
            record.created_at = datetime.fromisoformat(card.created_at) if card.created_at else datetime.now(timezone.utc)
            record.updated_at = datetime.fromisoformat(card.updated_at) if card.updated_at else datetime.now(timezone.utc)
            session.commit()
            return card.project_id
        finally:
            session.close()

    def get_project(self, project_id: str) -> ProjectCard | None:
        session = self.Session()
        try:
            record = session.get(ProjectRecord, project_id)
            if record is None:
                return None
            return self._record_to_card(record)
        finally:
            session.close()

    def get_all_projects(self) -> list[ProjectCard]:
        session = self.Session()
        try:
            records = session.query(ProjectRecord).all()
            return [self._record_to_card(r) for r in records]
        finally:
            session.close()

    def save_reports(
        self,
        project_id: str,
        self_check: SelfCheckReport | dict | None = None,
        analysis_report: AnalysisReport | dict | None = None,
    ) -> bool:
        session = self.Session()
        try:
            record = session.get(ProjectRecord, project_id)
            if record is None:
                return False
            if self_check is not None:
                record.self_check_report = self._json_dump(self_check)
            if analysis_report is not None:
                record.analysis_report = self._json_dump(analysis_report)
            session.commit()
            return True
        finally:
            session.close()

    def get_self_check_report(self, project_id: str) -> SelfCheckReport | None:
        session = self.Session()
        try:
            record = session.get(ProjectRecord, project_id)
            if not record or not record.self_check_report:
                return None
            return SelfCheckReport(**json.loads(record.self_check_report))
        finally:
            session.close()

    def get_analysis_report(self, project_id: str) -> AnalysisReport | None:
        session = self.Session()
        try:
            record = session.get(ProjectRecord, project_id)
            if not record or not record.analysis_report:
                return None
            return AnalysisReport(**json.loads(record.analysis_report))
        finally:
            session.close()

    def delete_project(self, project_id: str) -> bool:
        session = self.Session()
        try:
            record = session.get(ProjectRecord, project_id)
            if record:
                session.delete(record)
                session.commit()
                return True
            return False
        finally:
            session.close()

    def _json_dump(self, value: SelfCheckReport | AnalysisReport | dict) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        return json.dumps(value, ensure_ascii=False)

    def _record_to_card(self, record: ProjectRecord) -> ProjectCard:
        return ProjectCard(
            project_id=record.project_id,
            team_name=record.team_name or "",
            title=record.title or "",
            problem=record.problem or "",
            target_user=record.target_user or "",
            solution=record.solution or "",
            key_features=json.loads(record.key_features) if record.key_features else [],
            tech_stack=json.loads(record.tech_stack) if record.tech_stack else [],
            mvp_scope=record.mvp_scope or "",
            visibility=record.visibility or "summary",
            created_at=record.created_at.isoformat() if record.created_at else "",
            updated_at=record.updated_at.isoformat() if record.updated_at else "",
        )
