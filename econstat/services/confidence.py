"""Indicateurs techniques explicables, non calibrés métier."""


def composite_confidence(
    components: dict[str, float], weights: dict[str, float] | None = None
) -> float:
    bounded = {name: max(0.0, min(1.0, value)) for name, value in components.items()}
    if not bounded:
        return 0.0
    active_weights = weights or {name: 1.0 for name in bounded}
    total_weight = sum(active_weights.get(name, 0.0) for name in bounded)
    if total_weight <= 0:
        return 0.0
    return round(
        sum(value * active_weights.get(name, 0.0) for name, value in bounded.items())
        / total_weight,
        3,
    )
