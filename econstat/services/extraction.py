from datetime import UTC, datetime

from pydantic import ValidationError

from econstat.config import Settings
from econstat.schemas.claim import QUESTION_TEMPLATES, REQUIRED_FIELDS, ClaimData, ClaimExtraction
from econstat.services.extraction_llm import OllamaExtractor
from econstat.services.extraction_rules import deterministic_extract as _deterministic_extract
from econstat.services.extraction_rules import extract_rules
from econstat.services.lexicon import LocalLexicon


def deterministic_extract(transcript: str) -> tuple[dict, dict]:
    return _deterministic_extract(transcript, LocalLexicon(Settings().lexicon_path))


class HybridExtractor:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lexicon = LocalLexicon(settings.lexicon_path)
        self.llm = OllamaExtractor(settings)

    async def extract(self, transcript: str, whisper_confidence: float = 0.75) -> ClaimExtraction:
        rules = extract_rules(transcript, self.lexicon)
        merged = dict(rules.data)
        base_confidence = dict(rules.confidence)
        evidence = dict(rules.evidence)
        rejected: dict[str, str] = {}

        llm = await self.llm.extract(transcript)
        for field_name, proposal in llm.fields.items():
            if field_name in merged:
                rejected[field_name] = "deterministic_value_kept"
                continue
            try:
                candidate = ClaimData.model_validate({field_name: proposal.value})
                normalized = candidate.model_dump(mode="json")[field_name]
            except ValidationError:
                rejected[field_name] = "schema_validation_failed"
                continue
            merged[field_name] = normalized
            evidence[field_name] = proposal.evidence
            base_confidence[field_name] = min(proposal.confidence, 0.85)

        data = ClaimData.model_validate(merged)
        missing = [field for field in REQUIRED_FIELDS if getattr(data, field) is None]
        completeness = (len(REQUIRED_FIELDS) - len(missing)) / len(REQUIRED_FIELDS)
        asr_confidence = max(0.0, min(1.0, whisper_confidence))
        confidences = {
            field_name: round(
                0.55 * field_confidence + 0.25 * asr_confidence + 0.20 * completeness,
                3,
            )
            for field_name, field_confidence in base_confidence.items()
        }
        overall = sum(confidences.values()) / len(confidences) if confidences else 0.0
        return ClaimExtraction(
            data=data,
            field_confidences=confidences,
            evidence=evidence,
            missing_fields=missing,
            suggested_questions=[QUESTION_TEMPLATES[field] for field in missing],
            overall_confidence=round(overall, 3),
            trace={
                "rules": rules.rules,
                "llm_status": llm.status,
                "llm_trace": llm.trace,
                "rejected": {**llm.rejected, **rejected},
                "asr_confidence": round(asr_confidence, 4),
                "completeness": round(completeness, 4),
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
