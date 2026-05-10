import json

from src.config import settings
from src.core.llm import get_llm


def parse_llm_json(response_text: str, retries: int = 2) -> dict | list:
    for attempt in range(retries + 1):
        content = response_text.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            if attempt < retries and settings.openai_api_key:
                llm = get_llm()
                fix_prompt = (
                    f"Your previous JSON output was invalid. "
                    f"Please return ONLY valid JSON:\n\n{response_text[:200]}"
                )
                response_text = llm.invoke(fix_prompt).content
            else:
                return {}
    return {}
