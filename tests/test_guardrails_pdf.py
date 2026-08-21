from pathlib import Path

import pytest

from econstat.config import Settings
from econstat.services.econsta import EConstaClient
from econstat.services.pdf import generate_claim_pdf


@pytest.mark.asyncio
async def test_send_forbidden_without_human_validation():
    with pytest.raises(PermissionError):
        await EConstaClient(Settings()).create_claim("c1", {}, False)


def test_pdf_generation(tmp_path: Path):
    result = generate_claim_pdf("demo", {"nom_assure": "Awa Koné", "lieu": "Cocody"}, tmp_path)
    assert result.exists() and result.read_bytes().startswith(b"%PDF")
