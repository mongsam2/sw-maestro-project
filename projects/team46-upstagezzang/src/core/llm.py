from langchain_openai import ChatOpenAI

from src.config import settings


def get_llm():
    kwargs = dict(
        model=settings.llm_model,
        temperature=0.3,
        openai_api_key=settings.openai_api_key,
    )
    if settings.llm_api_base:
        kwargs["openai_api_base"] = settings.llm_api_base
    return ChatOpenAI(**kwargs)
