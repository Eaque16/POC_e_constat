"""Politique générique de confirmation des slots sensibles."""

SENSITIVE_SLOTS = frozenset(
    {
        "firstname",
        "lastname",
        "location",
        "accident_date",
        "accident_time",
        "accident_datetime",
        "phone",
        "vehicle_plate",
    }
)


def needs_confirmation(result: dict) -> bool:
    if result.get("normalized") is None:
        return False
    if result.get("slot") in {
        "firstname",
        "lastname",
        "location",
        "accident_date",
        "accident_time",
        "accident_datetime",
    }:
        return True
    if result.get("precision") in {"approximate", "ambiguous"}:
        return True
    return result.get("slot") in SENSITIVE_SLOTS and float(result.get("confidence", 0)) < 0.9
