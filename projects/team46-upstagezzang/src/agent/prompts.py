import tomllib
from pathlib import Path

_TOML_PATH = Path(__file__).parent / "prompts.toml"
with _TOML_PATH.open("rb") as f:
    _data = tomllib.load(f)

SELF_CHECK_PROMPT = _data["SELF_CHECK_PROMPT"]["text"]
SIMILARITY_ANALYSIS_PROMPT = _data["SIMILARITY_ANALYSIS_PROMPT"]["text"]
CROSS_INSIGHT_PROMPT = _data["CROSS_INSIGHT_PROMPT"]["text"]
MENTORING_SUMMARY_PROMPT = _data["MENTORING_SUMMARY_PROMPT"]["text"]
EXTRACT_PROMPT = _data["EXTRACT_PROMPT"]["text"]
NEXT_QUESTION_PROMPT = _data["NEXT_QUESTION_PROMPT"]["text"]
GREETING = _data["GREETING"]["text"]
