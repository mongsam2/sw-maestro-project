import json
from pathlib import Path

from src.models import ProjectCard

_JSON_PATH = Path(__file__).parent / "sample_data.json"
with _JSON_PATH.open() as f:
    _raw = json.load(f)

SAMPLE_PROJECTS = [ProjectCard(**item) for item in _raw]
