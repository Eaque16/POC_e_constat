from datetime import UTC, datetime

from econstat.services.conversation import new_conversation, progress, respond, validated_data


def test_conversation_separates_and_confirms_identity():
    state = new_conversation()
    reply, state = respond("Nguessan", state)
    assert "N'GUESSAN" in reply
    assert state["current_field"] == "confirmation"
    assert state["data"] == {}

    reply, state = respond("oui", state)
    assert state["data"]["lastname"] == "N'GUESSAN"
    assert state["field_records"]["lastname"]["raw_transcript"] == "Nguessan"
    assert state["field_records"]["lastname"]["confirmed"] is True
    assert state["current_field"] == "firstname"
    assert "prénom" in reply.lower()

    _, state = respond("Kouadio", state)
    _, state = respond("oui", state)
    assert validated_data(state).nom_assure == "Kouadio N'GUESSAN"
    assert progress(state["data"]) > 0


def test_rejected_name_switches_to_spelling_mode():
    state = new_conversation()
    _, state = respond("Kouamelan", state)
    reply, state = respond("non", state)
    assert "épeler" in reply
    assert state["spelling_mode"] is True

    reply, state = respond("K O U A M E L A N", state)
    assert "KOUAMELAN" in reply


def test_faq_does_not_consume_expected_slot():
    state = new_conversation()
    reply, updated = respond("Quels documents faut-il fournir ?", state)
    assert "carte grise" in reply.lower()
    assert updated["data"] == {}
    assert updated["current_field"] == "lastname"


def test_natural_datetime_is_anchored_to_call_start():
    state = new_conversation()
    state["call_started_at"] = datetime(2026, 8, 29, 10, tzinfo=UTC).isoformat()
    state["current_field"] = "accident_date"
    reply, state = respond("hier soir", state)
    assert "2026-08-28" in reply
    _, state = respond("oui", state)
    state["current_field"] = "accident_time"
    reply, _state = respond("vers huit heures du soir", state)
    assert "20:00" in reply


def test_second_unusable_answer_is_stored_as_null_and_moves_to_next_slot():
    state = new_conversation()

    first_reply, state = respond("", state, asr_confidence=0.0)
    assert state["current_field"] == "lastname"
    assert state["attempts"]["lastname"] == 1
    assert "répéter" in first_reply

    second_reply, state = respond("", state, asr_confidence=0.0)
    assert state["data"]["lastname"] is None
    assert state["field_records"]["lastname"]["normalized"] is None
    assert (
        state["field_records"]["lastname"]["metadata"]["collection_status"]
        == "missing_after_two_attempts"
    )
    assert state["field_records"]["lastname"]["metadata"]["attempt_count"] == 2
    assert state["skipped_fields"] == ["lastname"]
    assert state["current_field"] == "firstname"
    assert "prénom" in second_reply.lower()
    assert validated_data(state).nom_assure is None


def test_two_unrecognized_confirmation_answers_skip_sensitive_field():
    state = new_conversation()
    _, state = respond("Nguessan", state)
    assert state["current_field"] == "confirmation"

    first_reply, state = respond("peut-être", state)
    assert state["current_field"] == "confirmation"
    assert "oui ou non" in first_reply

    second_reply, state = respond("incertain encore", state)
    assert state["data"]["lastname"] is None
    assert state["current_field"] == "firstname"
    assert state["field_records"]["lastname"]["metadata"]["failure_reason"] == (
        "confirmation_not_understood"
    )
    assert "prénom" in second_reply.lower()


def test_second_rejected_transcription_is_not_requested_a_third_time():
    state = new_conversation()
    _, state = respond("Nimporte", state)
    _, state = respond("non", state)
    assert state["current_field"] == "lastname"
    assert state["attempts"]["lastname"] == 1

    _, state = respond("K O U A", state)
    assert state["current_field"] == "confirmation"
    final_reply, state = respond("non", state)

    assert state["data"]["lastname"] is None
    assert state["current_field"] == "firstname"
    assert state["skipped_fields"] == ["lastname"]
    assert state["field_records"]["lastname"]["metadata"]["failure_reason"] == (
        "user_rejected_two_transcriptions"
    )
    assert "prénom" in final_reply.lower()
