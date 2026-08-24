import json
from datetime import UTC, datetime
from pathlib import Path


class ExportNotValidatedError(ValueError):
    pass


def generate_claim_json(
    claim_id: str,
    data: dict,
    output_dir: Path,
    *,
    validated_by: str | None,
    validated_at: datetime | None,
) -> Path:
    """Produit un export métier lisible uniquement après validation humaine."""
    if not validated_by or validated_at is None:
        raise ExportNotValidatedError("Une validation humaine explicite est obligatoire.")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"constat-{claim_id}.json"
    payload = {
        "schema_version": "1.0",
        "reference_dossier": claim_id,
        "declaration": data,
        "validation_humaine": {
            "validee": True,
            "validee_par": validated_by,
            "validee_le": validated_at.isoformat(),
        },
        "exporte_le": datetime.now(UTC).isoformat(),
        "avertissement": "Déclaration contrôlée et validée explicitement par un humain.",
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return target
