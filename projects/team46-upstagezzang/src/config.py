
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    llm_api_base: str = ""
    llm_model: str = "gpt-4o-mini"
    embedding_api_base: str = ""
    embedding_model: str = "text-embedding-3-small"

    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_collection: str = "project_plans"
    chroma_persist_path: str = "./data/chroma"

    log_level: str = "INFO"
    data_dir: str = "./data"

    similarity_threshold_high: float = 0.85
    similarity_threshold_medium: float = 0.70

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
