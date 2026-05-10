from langchain_openai import OpenAIEmbeddings

from src.config import settings


def get_embedding(text: str) -> list[float]:
    if not settings.openai_api_key:
        return [0.0] * 4096
    kwargs = dict(
        model=settings.embedding_model,
        openai_api_key=settings.openai_api_key,
        check_embedding_ctx_length=False,
        embedding_ctx_length=8191,
    )
    if settings.embedding_api_base:
        kwargs["openai_api_base"] = settings.embedding_api_base
    embeddings = OpenAIEmbeddings(**kwargs)
    return embeddings.embed_query(text)
