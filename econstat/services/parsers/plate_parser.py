import re


def parse_plate(value: str) -> str | None:
    compact = re.sub(r"[^A-Z0-9]", "", value.upper())
    if (
        not 5 <= len(compact) <= 12
        or not re.search(r"[A-Z]", compact)
        or not re.search(r"\d", compact)
    ):
        return None
    return compact
