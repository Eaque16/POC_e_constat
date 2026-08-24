from datetime import date

from econstat.services.conversation import new_conversation, parse_spoken_date, progress, respond


def test_conversation_collects_answer_then_asks_next_question():
    reply, state = respond("Jean Kouassi", new_conversation())

    assert state["data"]["nom_assure"] == "Jean Kouassi"
    assert state["current_field"] == "telephone_assure"
    assert "téléphone" in reply.lower()
    assert progress(state["data"]) > 0


def test_faq_answer_does_not_consume_expected_claim_field():
    state = new_conversation()
    reply, updated = respond("Quels documents faut-il fournir ?", state)

    assert "carte grise" in reply.lower()
    assert updated["data"] == {}
    assert updated["current_field"] == "nom_assure"


def test_invalid_structured_answer_is_not_recorded():
    state = new_conversation()
    state["current_field"] = "date_accident"
    reply, updated = respond("je ne sais plus", state)

    assert "date_accident" not in updated["data"]
    assert "date" in reply.lower()


def test_spoken_french_dates_are_normalized():
    assert parse_spoken_date("le 24 août 2026") == "2026-08-24"
    assert parse_spoken_date("vingt-quatre août deux mille vingt-six") == "2026-08-24"
    assert parse_spoken_date("hier", today=date(2026, 8, 24)) == "2026-08-23"


def test_ivoirian_name_place_and_insurer_are_corrected():
    state = new_conversation()
    state["current_field"] = "nom_assure"
    _, state = respond("Jean Kouasi", state)
    assert state["data"]["nom_assure"] == "Jean Kouassi"

    state["current_field"] = "assureur"
    _, state = respond("Sunu", state)
    assert state["data"]["assureur"] == "SUNU"

    state["current_field"] = "lieu"
    _, state = respond("Yopougon", state)
    assert state["data"]["lieu"] == "Yopougon"
