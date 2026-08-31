import re


def parse_yes_no(value: str) -> bool | None:
    plain = value.casefold().strip()
    if re.search(r"\b(non|aucun|aucune|pas du tout|ne .* pas)\b", plain):
        return False
    if re.search(r"\b(oui|exact|correct|c'est ça|tout à fait|d'accord)\b", plain):
        return True
    return None
