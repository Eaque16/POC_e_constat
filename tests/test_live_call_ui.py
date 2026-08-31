from econstat.ui.app import end_live_call, start_live_call


def test_live_call_starts_fresh_conversation_and_enables_microphone():
    state, history, _summary, status, microphone, start, end, spoken = start_live_call()

    assert state["current_field"] == "lastname"
    assert history
    assert "Appel en cours" in status
    assert microphone["interactive"] is True
    assert start["interactive"] is False
    assert end["interactive"] is True
    assert "Bonjour" in spoken


def test_live_call_end_keeps_screen_but_disables_microphone():
    status, microphone, start, end = end_live_call()

    assert "Appel terminé" in status
    assert microphone["interactive"] is False
    assert start["interactive"] is True
    assert end["interactive"] is False
