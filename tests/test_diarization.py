from econstat.schemas.claim import TranscriptSegment
from econstat.services.diarization import align_and_label


def test_two_speakers_welcome_heuristic():
    segments = [
        TranscriptSegment(start=0, end=2, text="Bonjour service sinistre"),
        TranscriptSegment(start=2, end=5, text="Je viens déclarer un accident"),
    ]
    result = align_and_label(segments, [(0, 2, "S0"), (2, 5, "S1")])
    assert [s.speaker for s in result] == ["AGENT", "ASSURE"]


def test_single_speaker_edge_case():
    segments = [TranscriptSegment(start=0, end=2, text="Bonjour je déclare un accident")]
    assert align_and_label(segments, [(0, 2, "S0")])[0].speaker == "AGENT"


def test_no_diarization_fallback():
    segments = [TranscriptSegment(start=0, end=1, text="bruit hésitation")]
    assert align_and_label(segments, [])[0].speaker == "INCONNU"
