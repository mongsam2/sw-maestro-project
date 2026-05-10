import chromadb
from chromadb.config import Settings as ChromaSettings

from src.config import settings
from src.models import ProjectCard


class VectorStore:
    def __init__(self):
        self.client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    def add_project(self, card: ProjectCard, embedding: list[float]):
        metadata = {
            "project_id": card.project_id,
            "title": card.title,
            "visibility": card.visibility,
            "team_name": card.team_name,
        }
        doc_text = (
            f"Title: {card.title}\n"
            f"Problem: {card.problem}\n"
            f"Target User: {card.target_user}\n"
            f"Solution: {card.solution}\n"
            f"Tech Stack: {', '.join(card.tech_stack)}\n"
            f"Key Features: {', '.join(card.key_features)}\n"
            f"MVP Scope: {card.mvp_scope}"
        )
        self.collection.add(
            documents=[doc_text],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[card.project_id],
        )

    def update_project(self, card: ProjectCard, embedding: list[float]):
        self.delete_project(card.project_id)
        self.add_project(card, embedding)

    def search_similar(self, embedding: list[float], n_results: int = 10) -> list[tuple[str, float, str]]:
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=n_results,
        )
        if not results["ids"]:
            return []
        pairs = []
        for i in range(len(results["ids"][0])):
            pairs.append((
                results["ids"][0][i],
                results["distances"][0][i],
                results["documents"][0][i],
            ))
        return pairs

    def delete_project(self, project_id: str):
        try:
            self.collection.delete(ids=[project_id])
        except Exception:
            pass

    def get_all_ids(self) -> list[str]:
        return self.collection.get()["ids"]

    def count(self) -> int:
        return self.collection.count()
