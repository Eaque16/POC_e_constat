import re


def parse_phone(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("225") and len(digits) == 13:
        return f"+{digits}"
    return digits if 8 <= len(digits) <= 10 else None
