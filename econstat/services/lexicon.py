import json
from pathlib import Path

from rapidfuzz import fuzz, process


class LocalLexicon:
    def __init__(self, path: Path):
        self.entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def correct_place(self, value: str, threshold: int = 80) -> str:
        places = self.entries.get("lieux", [])
        match = process.extractOne(value, places, scorer=fuzz.WRatio)
        return match[0] if match and match[1] >= threshold else value
