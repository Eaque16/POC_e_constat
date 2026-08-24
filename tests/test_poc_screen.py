from econstat.services.conversation import new_conversation
from econstat.ui.app import (
    activity_html,
    claim_information_html,
    current_question_text,
    mark_listening,
    start_poc_call,
)


def test_poc_call_starts_with_spoken_question_and_microphone():
    result = start_poc_call()

    assert "agent vous parle" in result[3]
    assert "nom complet" in result[5].lower()
    assert result[6]["interactive"] is True
    assert result[9]


def test_claim_panel_exposes_captured_and_missing_states():
    state = new_conversation()
    state["data"] = {"nom_assure": "Jean Kouassi"}
    panel = claim_information_html(state)

    assert "Jean Kouassi" in panel
    assert "Enregistré" in panel
    assert "À demander" in panel


def test_question_and_activity_are_explicit():
    state = new_conversation()

    assert "nom complet" in current_question_text(state).lower()
    assert "Je vous écoute" in activity_html("listening")
    assert "Transcription" in activity_html("processing")
    assert "Je vous écoute" in mark_listening(state)[0]
