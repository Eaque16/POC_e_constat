"""Attribution heuristique et explicitement réversible des rôles de parole."""

import re
from dataclasses import dataclass

from econstat.schemas.claim import TranscriptSegment

WELCOME = re.compile(r"bonjour|bienvenue|service sinistre|que puis-je|je vous écoute", re.I)


@dataclass(frozen=True)
class RoleAssignmentOutcome:
    segments: list[TranscriptSegment]
    heuristic_used: bool
    agent_raw_speaker: str | None
    reason: str

    def trace(self) -> dict:
        return {
            "role_assignment_heuristic": self.heuristic_used,
            "agent_raw_speaker": self.agent_raw_speaker,
            "role_assignment_reason": self.reason,
        }


def assign_roles(
    transcript: list[TranscriptSegment], turns: list[tuple[float, float, str]]
) -> RoleAssignmentOutcome:
    if not turns:
        return RoleAssignmentOutcome(
            segments=[segment.model_copy(update={"speaker": "INCONNU"}) for segment in transcript],
            heuristic_used=False,
            agent_raw_speaker=None,
            reason="diarization_unavailable",
        )
    raw_speakers = []
    for segment in transcript:
        overlaps = [
            (max(0.0, min(segment.end, end) - max(segment.start, start)), speaker)
            for start, end, speaker in turns
        ]
        duration, speaker = max(overlaps, default=(0.0, "INCONNU"))
        raw_speakers.append(speaker if duration > 0 else "INCONNU")

    welcomed = next(
        (
            speaker
            for segment, speaker in zip(transcript, raw_speakers, strict=True)
            if speaker != "INCONNU" and WELCOME.search(segment.text)
        ),
        None,
    )
    known_speakers = [speaker for speaker in raw_speakers if speaker != "INCONNU"]
    agent_raw = welcomed or (known_speakers[0] if known_speakers else None)
    labelled = []
    for segment, raw_speaker in zip(transcript, raw_speakers, strict=True):
        if raw_speaker == "INCONNU" or agent_raw is None:
            role = "INCONNU"
        elif raw_speaker == agent_raw:
            role = "AGENT"
        else:
            role = "ASSURE"
        labelled.append(segment.model_copy(update={"speaker": role}))
    return RoleAssignmentOutcome(
        segments=labelled,
        heuristic_used=True,
        agent_raw_speaker=agent_raw,
        reason="welcome_phrase" if welcomed else "first_detected_speaker",
    )
