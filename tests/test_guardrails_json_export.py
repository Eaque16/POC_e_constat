import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from econstat.services.json_export import ExportNotValidatedError, generate_claim_json


def test_json_export_contains_human_validation_trace(tmp_path: Path):
    validated_at = datetime(2026, 8, 24, 10, 30, tzinfo=UTC)
    result = generate_claim_json(
        "demo",
        {"nom_assure": "Awa Koné", "lieu": "Cocody"},
        tmp_path,
        validated_by="agent-id",
        validated_at=validated_at,
    )

    payload = json.loads(result.read_text(encoding="utf-8"))
    assert result.suffix == ".json"
    assert payload["reference_dossier"] == "demo"
    assert payload["declaration"]["nom_assure"] == "Awa Koné"
    assert payload["validation_humaine"] == {
        "validee": True,
        "validee_par": "agent-id",
        "validee_le": validated_at.isoformat(),
    }


def test_json_export_service_rejects_missing_human_validation(tmp_path: Path):
    with pytest.raises(ExportNotValidatedError, match="validation humaine"):
        generate_claim_json(
            "demo",
            {},
            tmp_path,
            validated_by=None,
            validated_at=None,
        )
