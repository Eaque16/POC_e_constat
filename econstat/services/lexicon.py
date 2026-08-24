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

    def literal_match(self, transcript: str, category: str) -> tuple[str, str] | None:
        """Retourne la valeur canonique et l’extrait littéral réellement présent."""
        entries = self.entries.get(category, [])
        for entry in sorted(entries, key=len, reverse=True):
            start = transcript.casefold().find(str(entry).casefold())
            if start >= 0:
                return str(entry), transcript[start : start + len(str(entry))]
        return None

    def accident_match(self, transcript: str) -> tuple[str, str] | None:
        labels = {
            "collision_arriere": "Collision arrière",
            "collision_frontale": "Collision frontale",
            "sortie_de_route": "Sortie de route",
            "accrochage": "Accrochage",
        }
        for category, variants in self.entries.get("accidents", {}).items():
            for variant in variants:
                start = transcript.casefold().find(str(variant).casefold())
                if start >= 0:
                    evidence = transcript[start : start + len(str(variant))]
                    return labels.get(category, category), evidence
        return None
