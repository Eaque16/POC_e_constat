import json
import logging
import os
import shutil
import threading
import uuid
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from time import perf_counter

import gradio as gr

from econstat.config import get_settings
from econstat.services.conversation import (
    SLOT_QUESTIONS,
    WELCOME_MESSAGE,
    new_conversation,
    progress,
    respond,
    summary_markdown,
    validated_data,
)
from econstat.services.geolocation import nearest_place
from econstat.services.location import LocationResolver
from econstat.services.realtime_transcription import get_realtime_transcriber
from econstat.services.transcription import Transcriber, TranscriptionError
from econstat.ui.api_client import APIError, EConstatAPI

API_URL = os.getenv("ECONSTAT_API_URL", "http://127.0.0.1:8000/api")
UI_PORT = int(os.getenv("ECONSTAT_UI_PORT", "7860"))
UI_HOST = os.getenv("ECONSTAT_UI_HOST", "127.0.0.1")
JOB_POLL_SECONDS = float(os.getenv("JOB_POLL_SECONDS", "2"))
UI_DIR = Path(__file__).resolve().parent
ASACI_LOGO = UI_DIR / "assets" / "asaci-logo.png"
ASR_FAST_LABEL = "Rapide — Whisper Tiny (~2 s)"
ASR_PRECISION_LABEL = "Précision — Whisper Small (~9 s)"
api = EConstatAPI(API_URL)
logger = logging.getLogger(__name__)
CALL_IDLE_MESSAGE = (
    "Cliquez sur **Décrocher et démarrer**. L’assistant parlera en premier, puis le "
    "microphone permettra d’enregistrer chaque réponse."
)
SPEAK_JS = """(text) => new Promise((resolve) => {
  if (!text || !window.speechSynthesis) { resolve(); return; }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'fr-FR';
  const voices = window.speechSynthesis.getVoices();
  const french = voices.find(v => v.lang && v.lang.toLowerCase().startsWith('fr'));
  if (french) utterance.voice = french;
  utterance.onend = resolve;
  utterance.onerror = resolve;
  window.speechSynthesis.speak(utterance);
})"""
GPS_JS = """() => new Promise((resolve) => {
  if (!navigator.geolocation) { resolve([null, null]); return; }
  navigator.geolocation.getCurrentPosition(
    p => resolve([p.coords.latitude, p.coords.longitude]),
    () => resolve([null, null]),
    {enableHighAccuracy: true, timeout: 10000}
  );
})"""


def require_token(_session: dict | None) -> str:
    """Le mode borne temps réel utilise le compte local sans écran de connexion."""
    return ""


def login(username: str, password: str):
    try:
        result = api.login(username.strip(), password)
    except APIError as exc:
        raise gr.Error(f"Connexion refusée : {exc}") from exc
    session = {
        "token": result["access_token"],
        "username": result["username"],
        "role": result["role"],
    }
    return session, f"Connecté : **{result['username']}** ({result['role']})"


def logout():
    return {}, "Non connecté"


def restart_conversation():
    state = new_conversation()
    return state, [(None, CALL_IDLE_MESSAGE)], "", summary_markdown(state), "", "🟢 Prêt"


def start_live_call():
    state = new_conversation()
    return (
        state,
        [(None, WELCOME_MESSAGE)],
        summary_markdown(state),
        "🔴 Appel en cours — microphone prêt",
        gr.update(interactive=True),
        gr.update(interactive=False),
        gr.update(interactive=True),
        WELCOME_MESSAGE,
    )


def end_live_call():
    return (
        "⚫ Appel terminé — les échanges restent affichés",
        gr.update(interactive=False, value=None),
        gr.update(interactive=True),
        gr.update(interactive=False),
    )


def send_chat_message(message: str, history: list, conversation: dict):
    if not message or not message.strip():
        raise gr.Error("Écrivez votre réponse ou votre question.")
    reply, conversation = respond(message, conversation)
    return (
        "",
        (history or []) + [(message.strip(), reply)],
        conversation,
        summary_markdown(conversation),
        reply,
        "🟢 Réponse prête",
    )


def process_voice_message(audio_path: str | None, history: list, conversation: dict):
    """Diffuse les étapes de transcription, réflexion et synthèse dans l’interface."""
    yield (
        "🟠 Transcription de la voix…",
        "",
        history or [],
        conversation,
        summary_markdown(conversation),
        None,
        None,
    )
    try:
        if not audio_path:
            raise gr.Error("Enregistrez d’abord la réponse de l’interlocuteur.")
        segments = Transcriber(get_settings(), profile="fast").transcribe(Path(audio_path))
        transcript = " ".join(segment.text for segment in segments).strip()
        if not transcript:
            raise gr.Error("Aucune parole n’a été détectée dans l’enregistrement.")
    except TranscriptionError as exc:
        raise gr.Error(str(exc)) from exc
    visible_history = (history or []) + [(transcript, None)]
    yield (
        "🟠 L’agent analyse la réponse…",
        transcript,
        visible_history,
        conversation,
        summary_markdown(conversation),
        None,
        None,
    )
    reply, conversation = respond(transcript, conversation)
    visible_history[-1] = (transcript, reply)
    yield (
        "🟠 Préparation de la réponse audio…",
        transcript,
        visible_history,
        conversation,
        summary_markdown(conversation),
        None,
        None,
    )
    yield (
        "🟢 Réponse prête — lecture audio en cours",
        transcript,
        visible_history,
        conversation,
        summary_markdown(conversation),
        reply,
        None,
    )


def create_claim_from_chat(session: dict, conversation: dict):
    token = require_token(session)
    if progress((conversation or {}).get("data", {})) < 100:
        raise gr.Error("Terminez les questions essentielles avant de créer le dossier.")
    try:
        data = validated_data(conversation).model_dump(mode="json")
        result = api.create_conversation_claim(token, data, conversation["transcript"])
    except (APIError, ValueError) as exc:
        raise gr.Error(f"Création du dossier impossible : {exc}") from exc
    return (
        f"Dossier **{result['claim_id']}** créé. Il est maintenant en attente du contrôle "
        "et de la validation d’un agent humain."
    )


def submit_audio(session: dict, audio_path: str | None, profile: str):
    token = require_token(session)
    if not audio_path:
        raise gr.Error("Sélectionnez ou enregistrez un fichier audio.")
    try:
        result = api.upload(token, audio_path, profile)
    except APIError as exc:
        raise gr.Error(f"Upload refusé : {exc}") from exc
    return (
        result["job_id"],
        f"Dossier **{result['id']}** mis en file. Job **{result['job_id']}**. "
        "Le worker effectuera le traitement en arrière-plan.",
    )


def refresh_jobs(session: dict):
    try:
        jobs = api.jobs(require_token(session))
    except APIError as exc:
        raise gr.Error(str(exc)) from exc
    rows = []
    for item in jobs:
        started = item.get("started_at")
        elapsed = "—"
        if started:
            started_at = datetime.fromisoformat(started.replace("Z", "+00:00"))
            elapsed = round((datetime.now(UTC) - started_at).total_seconds())
        rows.append(
            [
                item["id"],
                item["call_id"],
                item["profile"],
                item["status"],
                item["current_step"],
                item["progress_pct"],
                item.get("error_message") or "",
                elapsed,
                item["updated_at"],
            ]
        )
    return rows


def poll_jobs(session: dict):
    return refresh_jobs(session)


def retry_job(session: dict, job_id: str):
    if not job_id.strip():
        raise gr.Error("Saisissez l’identifiant du job en échec.")
    try:
        result = api.retry_job(require_token(session), job_id.strip())
    except APIError as exc:
        raise gr.Error(f"Relance impossible : {exc}") from exc
    return f"Job remis en file (tentative {result['retry_count']})."


def refresh_claims(session: dict):
    try:
        claims = api.claims(require_token(session))
    except APIError as exc:
        raise gr.Error(str(exc)) from exc
    choices = [
        (
            f"{item['id']} — {item['status']} — "
            f"{item['current_data'].get('nom_assure') or 'assuré non renseigné'}",
            item["id"],
        )
        for item in claims
    ]
    history = [
        [
            item["id"],
            item["status"],
            item["current_data"].get("nom_assure") or "—",
            item["current_data"].get("lieu") or "—",
            round(item["global_confidence"] * 100),
            item["human_corrections"],
            item["updated_at"],
        ]
        for item in claims
    ]
    selected = choices[0][1] if choices else None
    return gr.update(choices=choices, value=selected), history


def field_rows(claim: dict) -> list[list]:
    proposed = claim["proposed_data"]
    current = claim["current_data"]
    validated = claim.get("validated_data") or {}
    return [
        [
            field,
            proposed.get(field),
            claim["evidence"].get(field, ""),
            round(claim["confidence"].get(field, 0) * 100),
            current.get(field),
            validated.get(field),
        ]
        for field in sorted(set(proposed) | set(current))
    ]


def load_review(session: dict, claim_id: str):
    if not claim_id:
        raise gr.Error("Aucune déclaration disponible.")
    token = require_token(session)
    try:
        claim = api.claim(token, claim_id)
        call = api.call(token, claim["call_id"])
    except APIError as exc:
        raise gr.Error(str(exc)) from exc
    segments = [
        [index, item["start"], item["end"], item["speaker"], item["text"]]
        for index, item in enumerate(call["segments"])
    ]
    missing = ", ".join(claim["missing_fields"]) or "Aucun champ obligatoire manquant."
    questions = "\n".join(f"- {question}" for question in claim["questions"])
    return (
        claim["call_id"],
        f"Statut : **{claim['status']}** — confiance globale : "
        f"**{round(claim['global_confidence'] * 100)} %**",
        call.get("transcript_text") or "Transcription indisponible.",
        segments,
        field_rows(claim),
        json.dumps(claim["current_data"], ensure_ascii=False, indent=2),
        f"**Champs manquants :** {missing}\n\n" f"**Questions suggérées :**\n{questions or '—'}",
    )


def save_corrections(session: dict, claim_id: str, data_json: str):
    try:
        data = json.loads(data_json)
        api.update_claim(require_token(session), claim_id, data)
    except json.JSONDecodeError as exc:
        raise gr.Error(f"JSON invalide : ligne {exc.lineno}, colonne {exc.colno}.") from exc
    except APIError as exc:
        raise gr.Error(f"Correction impossible : {exc}") from exc
    return "Corrections humaines enregistrées et auditées. Rechargez la revue."


def save_speakers(session: dict, call_id: str, segments: list[list]):
    corrections = []
    allowed = {"AGENT", "ASSURE", "INCONNU"}
    for row in segments or []:
        speaker = str(row[3]).upper()
        if speaker not in allowed:
            raise gr.Error(f"Rôle invalide : {speaker}.")
        corrections.append({"segment_index": int(row[0]), "speaker": speaker})
    if not corrections:
        raise gr.Error("Aucun segment à corriger.")
    try:
        api.correct_speakers(require_token(session), call_id, corrections)
    except APIError as exc:
        raise gr.Error(f"Correction des rôles impossible : {exc}") from exc
    return "Rôles des locuteurs enregistrés et audités."


def validate_claim(session: dict, claim_id: str):
    try:
        api.validate(require_token(session), claim_id)
    except APIError as exc:
        raise gr.Error(f"Validation impossible : {exc}") from exc
    return "Déclaration validée explicitement par un humain."


def generate_json(session: dict, claim_id: str):
    try:
        result = api.export_json(require_token(session), claim_id)
    except APIError as exc:
        raise gr.Error(f"Export JSON impossible : {exc}") from exc
    return result["path"], "JSON généré après contrôle de la validation humaine."


def send_claim(session: dict, claim_id: str):
    try:
        result = api.send(require_token(session), claim_id)
    except APIError as exc:
        raise gr.Error(f"Envoi impossible : {exc}") from exc
    return f"Envoi mock réussi. Référence externe : {result['id']}"


def load_dashboard(session: dict):
    try:
        data = api.dashboard(require_token(session))
    except APIError as exc:
        raise gr.Error(f"Dashboard réservé au responsable : {exc}") from exc
    return (
        data["appels"],
        data["dossiers"],
        data["dossiers_en_cours"],
        data["dossiers_a_valider"],
        data["dossiers_valides"],
        data["dossiers_envoyes"],
        data["erreurs_traitement"],
        data["temps_moyen_traitement_secondes"] or 0,
        data["taux_dossiers_corriges_pct"],
        data["taux_dossiers_sans_correction_pct"],
        json.dumps(data["distribution_types_accident"], ensure_ascii=False, indent=2),
        json.dumps(data["distribution_erreurs"], ensure_ascii=False, indent=2),
        "\n".join(f"- {alert}" for alert in data["alertes"]) or "Aucune alerte.",
    )


def _dashboard_bars(items: dict[str, int]) -> str:
    if not items:
        return '<p class="dashboard-empty">Aucune donnée disponible.</p>'
    maximum = max(items.values()) or 1
    return "".join(
        '<div class="dashboard-bar-row">'
        f'<span>{escape(str(label))}</span>'
        '<div class="dashboard-bar-track">'
        f'<i style="width:{round(value * 100 / maximum)}%"></i></div>'
        f"<strong>{value}</strong></div>"
        for label, value in sorted(items.items(), key=lambda item: item[1], reverse=True)
    )


def dashboard_visual_html(data: dict) -> str:
    metrics = (
        ("Appels", data["appels"]),
        ("Dossiers", data["dossiers"]),
        ("En cours", data["dossiers_en_cours"]),
        ("À valider", data["dossiers_a_valider"]),
        ("Validés", data["dossiers_valides"]),
        ("Envoyés", data["dossiers_envoyes"]),
    )
    cards = "".join(
        f'<article><small>{label}</small><strong>{value}</strong></article>'
        for label, value in metrics
    )
    return (
        f'<div class="dashboard-card-grid">{cards}</div>'
        '<div class="dashboard-chart-grid">'
        '<section><h3>Dossiers par type d’accident</h3>'
        f'{_dashboard_bars(data["distribution_types_accident"])}</section>'
        '<section><h3>Qualité et traitement</h3>'
        '<div class="quality-score">'
        f'<strong>{data["taux_dossiers_sans_correction_pct"]:.0f}%</strong>'
        '<span>sans correction humaine</span></div>'
        f'<p><b>{data["erreurs_traitement"]}</b> erreur(s) de traitement</p>'
        f'<p><b>{data["taux_dossiers_corriges_pct"]:.0f}%</b> de dossiers corrigés</p>'
        "</section></div>"
    )


def load_dashboard_view(session: dict):
    try:
        data = api.dashboard(require_token(session))
        claims = api.claims(require_token(session))
    except APIError as exc:
        raise gr.Error(f"Chargement du tableau de bord impossible : {exc}") from exc
    rows = [
        [
            item["id"],
            item["status"],
            item["current_data"].get("nom_assure") or "—",
            item["current_data"].get("telephone_assure") or "—",
            item["current_data"].get("plaque") or "—",
            item["current_data"].get("lieu") or "—",
            round(item["global_confidence"] * 100),
            item["updated_at"],
            json.dumps(item["current_data"], ensure_ascii=False),
        ]
        for item in claims
    ]
    return dashboard_visual_html(data), rows


CLAIM_SECTIONS = (
    ("Interlocuteur", (("nom_assure", "Nom"), ("telephone_assure", "Téléphone"))),
    ("Véhicule", (("plaque", "Immatriculation"),)),
    (
        "Sinistre",
        (
            ("date_accident", "Date"),
            ("heure_accident", "Heure"),
            ("lieu", "Lieu"),
            ("type_accident", "Type"),
        ),
    ),
    (
        "Situation",
        (
            ("nombre_vehicules", "Véhicules impliqués"),
            ("vehicule_immobilise", "Véhicule roulant"),
        ),
    ),
    ("Dommages", (("dommages", "Description"),)),
    ("Circonstances", (("circonstances", "Récit"),)),
)
CLAIM_FIELD_COUNT = sum(len(fields) for _, fields in CLAIM_SECTIONS)


def _display_claim_value(field: str, value) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        if field == "vehicule_immobilise":
            return "Non" if value else "Oui"
        return "Oui" if value else "Non"
    return escape(str(value))


def claim_information_html(state: dict | None, analyzing: str | None = None) -> str:
    data = (state or {}).get("data", {})
    captured = sum(
        data.get(field) is not None for _, fields in CLAIM_SECTIONS for field, _ in fields
    )
    percent = round(captured * 100 / CLAIM_FIELD_COUNT)
    content = [
        '<div class="claim-progress-copy">'
        f"{captured} informations sur {CLAIM_FIELD_COUNT} recueillies</div>",
        f'<div class="claim-progress"><span style="width:{percent}%"></span></div>',
    ]
    for section, fields in CLAIM_SECTIONS:
        content.append(f'<section class="claim-section"><h3>{section}</h3>')
        for field, label in fields:
            value = data.get(field)
            if field == analyzing:
                badge = '<span class="field-state analyzing">Analyse…</span>'
            elif value is not None:
                badge = '<span class="field-state captured">✓ Enregistré</span>'
            else:
                badge = '<span class="field-state missing">À demander</span>'
            content.append(
                '<div class="claim-field">'
                f"<div><small>{label}</small><strong>"
                f"{_display_claim_value(field, value)}</strong></div>"
                f"{badge}</div>"
            )
        content.append("</section>")
    return "".join(content)


def current_question_text(state: dict | None) -> str:
    field = (state or {}).get("current_field")
    if field == "confirmation":
        return "Confirmation de l’information comprise"
    return SLOT_QUESTIONS.get(field, "Toutes les informations principales sont recueillies.")


def persist_conversation(state: dict) -> tuple[dict, str | None]:
    try:
        data = validated_data(state).model_dump(mode="json")
        result = api.create_conversation_claim(
            "",
            data,
            state.get("transcript", []),
            state.get("claim_id"),
            state.get("field_records", {}),
        )
    except (APIError, ValueError) as exc:
        return state, str(exc)
    return {**state, "claim_id": result["claim_id"]}, None


def activity_html(mode: str) -> str:
    if mode == "speaking":
        return '<div class="activity speaking">🔊 <strong>L’agent parle</strong></div>'
    if mode == "listening":
        bars = "".join("<i></i>" for _ in range(14))
        return (
            '<div class="activity listening">🎤 <strong>Je vous écoute</strong>'
            f'<div class="waveform">{bars}</div></div>'
        )
    if mode == "processing":
        return (
            '<div class="activity processing"><strong>Analyse de votre réponse…</strong>'
            "<ol><li>✓ Transcription</li><li>● Compréhension</li>"
            "<li>○ Enregistrement</li></ol></div>"
        )
    if mode == "complete":
        return '<div class="activity complete">✓ <strong>Déclaration enregistrée</strong></div>'
    return '<div class="activity ready"><strong>Prêt à commencer</strong></div>'


def start_poc_call():
    state = new_conversation()
    return (
        state,
        [(None, WELCOME_MESSAGE)],
        claim_information_html(state),
        "🔊 L’agent vous parle",
        activity_html("speaking"),
        current_question_text(state),
        gr.update(interactive=True),
        gr.update(interactive=False),
        gr.update(interactive=True),
        WELCOME_MESSAGE,
    )


def mark_listening(state: dict | None = None):
    if state and state.get("current_field") is None:
        return "✓ Déclaration terminée", activity_html("complete")
    return "🎤 Je vous écoute", activity_html("listening")


def stop_poc_call():
    return (
        "Prêt",
        activity_html("ready"),
        gr.update(interactive=False, value=None),
        gr.update(interactive=True),
        gr.update(interactive=False),
    )


def reset_poc_call():
    state = new_conversation()
    return (
        state,
        [(None, CALL_IDLE_MESSAGE)],
        claim_information_html(state),
        current_question_text(state),
        "Prêt",
        activity_html("ready"),
        "",
        gr.update(interactive=False, value=None),
        gr.update(interactive=True),
        gr.update(interactive=False),
    )


def apply_gps_location(latitude, longitude, state: dict, history: list):
    if latitude is None or longitude is None:
        raise gr.Error("Position GPS indisponible ou permission refusée.")
    place, distance = nearest_place(float(latitude), float(longitude))
    state = dict(state or new_conversation())
    state["gps"] = (float(latitude), float(longitude))
    if state.get("current_field") == "lieu":
        reply, state = respond(place, state)
        history = (history or []) + [(f"Position GPS : {place}", reply)]
    else:
        data = dict(state.get("data", {}))
        data["lieu"] = place
        state["data"] = data
        history = (history or []) + [(f"Position GPS proposée : {place}", None)]
    state, persistence_error = persist_conversation(state)
    notice = f"Zone GPS proposée : {place} (centre de référence à {distance} km)."
    if persistence_error:
        notice += f" Enregistrement SQLite en attente : {persistence_error}"
    return state, history, claim_information_html(state), current_question_text(state), notice


def process_poc_voice(
    audio_path: str | None,
    history: list,
    conversation: dict,
    asr_mode: str,
):
    turn_started = perf_counter()
    field = (conversation or {}).get("current_field")
    yield (
        "Analyse de votre réponse…",
        activity_html("processing"),
        "Transcription en cours…",
        history or [],
        conversation,
        claim_information_html(conversation, field),
        current_question_text(conversation),
        "",
        None,
    )
    try:
        if not audio_path:
            raise gr.Error("Aucune réponse vocale enregistrée.")
        settings = get_settings()
        source_audio = Path(audio_path)
        mode = "precision" if asr_mode == ASR_PRECISION_LABEL else "fast"
        realtime_result = get_realtime_transcriber(settings, mode).transcribe(
            source_audio, context=current_question_text(conversation)
        )
        transcript = realtime_result.text
    except TranscriptionError as exc:
        raise gr.Error(str(exc)) from exc
    displayed_transcript = transcript or "[Aucune parole comprise]"
    visible_history = (history or []) + [(displayed_transcript, None)]
    yield (
        "Analyse de votre réponse…",
        activity_html("processing"),
        displayed_transcript,
        visible_history,
        conversation,
        claim_information_html(conversation, field),
        current_question_text(conversation),
        "",
        None,
    )
    parser_started = perf_counter()
    audio_reference = None
    try:
        settings.recordings_dir.mkdir(parents=True, exist_ok=True)
        retained = settings.recordings_dir / f"{uuid.uuid4()}{source_audio.suffix.lower()}"
        shutil.copy2(source_audio, retained)
        audio_reference = str(retained)
    except OSError as exc:
        logger.warning("Conversation audio retention failed: %s", type(exc).__name__)
    reply, conversation = respond(
        transcript,
        conversation,
        asr_confidence=realtime_result.confidence,
        location_resolver=LocationResolver(get_settings()),
        audio_reference=audio_reference,
    )
    parser_ms = (perf_counter() - parser_started) * 1000
    visible_history[-1] = (displayed_transcript, reply)
    persistence_started = perf_counter()
    conversation, persistence_error = persist_conversation(conversation)
    persistence_ms = (perf_counter() - persistence_started) * 1000
    total_turn_ms = (perf_counter() - turn_started) * 1000
    logger.info(
        "Conversation turn parser_ms=%.1f geocoder_ms=%.1f persistence_ms=%.1f "
        "total_turn_ms=%.1f",
        parser_ms,
        0.0,
        persistence_ms,
        total_turn_ms,
    )
    complete = conversation.get("current_field") is None
    final_status = "✓ Déclaration terminée" if complete else "🔊 L’agent vous parle"
    if persistence_error:
        final_status = "⚠️ Réponse comprise — enregistrement SQLite échoué"
    yield (
        final_status,
        activity_html("complete" if complete else "speaking"),
        displayed_transcript,
        visible_history,
        conversation,
        claim_information_html(conversation),
        current_question_text(conversation),
        reply,
        None,
    )


def process_poc_text(message: str, history: list, conversation: dict):
    """Permet de remplacer une transcription erronée par la réponse réellement dite."""
    corrected = (message or "").strip()
    if not corrected:
        raise gr.Error("Saisissez la transcription correcte avant de valider.")
    reply, conversation = respond(
        corrected,
        conversation,
        asr_confidence=1.0,
        location_resolver=LocationResolver(get_settings()),
    )
    conversation, persistence_error = persist_conversation(conversation)
    history = (history or []) + [(f"✏️ {corrected}", reply)]
    complete = conversation.get("current_field") is None
    status = "✓ Déclaration terminée" if complete else "🔊 Correction prise en compte"
    if persistence_error:
        status = "⚠️ Correction comprise — enregistrement SQLite échoué"
    return (
        status,
        activity_html("complete" if complete else "speaking"),
        corrected,
        history,
        conversation,
        claim_information_html(conversation),
        current_question_text(conversation),
        reply,
        gr.update(interactive=not complete),
        "",
    )


def process_poc_stream(audio_path, history: list, conversation: dict, asr_mode: str):
    """Transcrit les tranches reçues sans réinitialiser le microphone continu."""
    for update in process_poc_voice(audio_path, history, conversation, asr_mode):
        yield (*update[:-1], gr.skip())


def build_legacy_app() -> gr.Blocks:
    css = (UI_DIR / "style.css").read_text(encoding="utf-8")
    with gr.Blocks(
        title="E-Constat IA",
        theme=gr.themes.Soft(primary_hue="orange", neutral_hue="slate"),
        css=css,
    ) as demo:
        session = gr.State({})
        call_id = gr.State("")
        conversation = gr.State(new_conversation())
        gr.Markdown(
            "# E-Constat IA\nTraitement différé sur CPU — "
            "**l’IA propose, l’humain corrige et valide.**",
            elem_id="asaci-header",
        )
        with gr.Tab("📞 Appel en direct"):
            gr.Markdown(
                "## Appeler l’assistant sinistre\n"
                "Décrochez : l’IA vous accueille à l’oral et pose la première question. "
                "Après chaque réponse enregistrée, la transcription apparaît ici "
                "immédiatement.",
                elem_id="live-call-intro",
            )
            with gr.Row():
                with gr.Column(scale=2):
                    processing_status = gr.Markdown("🟢 Prêt", elem_id="agent-processing")
                    with gr.Row():
                        start_call_btn = gr.Button(
                            "📞 Décrocher et démarrer", variant="primary", size="lg"
                        )
                        end_call_btn = gr.Button("⏹ Terminer l’appel", interactive=False, size="lg")
                    chat = gr.Chatbot(
                        value=[(None, CALL_IDLE_MESSAGE)],
                        label="Appel, transcription et réponses de l’IA",
                        height=520,
                        elem_id="claim-chat",
                    )
                    with gr.Group():
                        client_audio = gr.Audio(
                            label=(
                                "Microphone — transcription automatique dès la fin "
                                "de chaque réponse"
                            ),
                            sources=["microphone"],
                            type="filepath",
                            interactive=False,
                        )
                        transcribed_text = gr.Textbox(
                            label="Dernière transcription",
                            interactive=False,
                            placeholder="La transcription apparaîtra ici…",
                        )
                    gr.Markdown(
                        "🔊 La réponse de l’agent est lue automatiquement par le navigateur."
                    )
                    spoken_reply = gr.Textbox(visible=False)
                    message = gr.Textbox(
                        label="Votre réponse",
                        placeholder="Ex. Non, aucun blessé / Quels documents faut-il ?",
                    )
                    with gr.Row():
                        send_message_btn = gr.Button("Envoyer", variant="primary")
                        restart_btn = gr.Button("Recommencer")
                with gr.Column(scale=1):
                    gr.Markdown("### Récapitulatif en direct")
                    conversation_summary = gr.Markdown(summary_markdown(new_conversation()))
                    create_chat_claim_btn = gr.Button(
                        "Créer le dossier à valider", variant="primary"
                    )
                    conversation_status = gr.Markdown()
            text_event = send_message_btn.click(
                send_chat_message,
                [message, chat, conversation],
                [
                    message,
                    chat,
                    conversation,
                    conversation_summary,
                    spoken_reply,
                    processing_status,
                ],
            )
            text_event.then(None, spoken_reply, None, js=SPEAK_JS)
            submit_event = message.submit(
                send_chat_message,
                [message, chat, conversation],
                [
                    message,
                    chat,
                    conversation,
                    conversation_summary,
                    spoken_reply,
                    processing_status,
                ],
            )
            submit_event.then(None, spoken_reply, None, js=SPEAK_JS)
            voice_event = client_audio.stop_recording(
                process_voice_message,
                [client_audio, chat, conversation],
                [
                    processing_status,
                    transcribed_text,
                    chat,
                    conversation,
                    conversation_summary,
                    spoken_reply,
                    client_audio,
                ],
                show_progress="hidden",
            )
            voice_event.then(None, spoken_reply, None, js=SPEAK_JS)
            start_event = start_call_btn.click(
                start_live_call,
                None,
                [
                    conversation,
                    chat,
                    conversation_summary,
                    processing_status,
                    client_audio,
                    start_call_btn,
                    end_call_btn,
                    spoken_reply,
                ],
            )
            start_event.then(None, spoken_reply, None, js=SPEAK_JS)
            end_call_btn.click(
                end_live_call,
                None,
                [processing_status, client_audio, start_call_btn, end_call_btn],
            )
            restart_btn.click(
                restart_conversation,
                None,
                [
                    conversation,
                    chat,
                    message,
                    conversation_summary,
                    spoken_reply,
                    processing_status,
                ],
            )
            create_chat_claim_btn.click(
                create_claim_from_chat, [session, conversation], conversation_status
            )
        with gr.Tab("Import d’un appel"):
            audio = gr.Audio(
                label="Audio d’appel (fichier ou microphone de démonstration)",
                sources=["upload", "microphone"],
                type="filepath",
            )
            profile = gr.Radio(["fast", "quality"], value="fast", label="Profil")
            submit = gr.Button("Soumettre au worker", variant="primary")
            active_job = gr.Textbox(label="Job créé", interactive=False)
            upload_status = gr.Markdown()
            submit.click(submit_audio, [session, audio, profile], [active_job, upload_status])
        with gr.Tab("Traitements en cours"):
            jobs_timer = gr.Timer(value=JOB_POLL_SECONDS, active=True)
            refresh_jobs_btn = gr.Button("Actualiser")
            jobs_table = gr.Dataframe(
                headers=[
                    "Job",
                    "Appel",
                    "Profil",
                    "Statut",
                    "Étape",
                    "Progression %",
                    "Erreur",
                    "Durée écoulée (s)",
                    "Mise à jour",
                ],
                interactive=False,
            )
            retry_id = gr.Textbox(label="Identifiant du job à relancer")
            retry_btn = gr.Button("Relancer le job en échec")
            retry_status = gr.Markdown()
            refresh_jobs_btn.click(refresh_jobs, session, jobs_table)
            jobs_timer.tick(poll_jobs, session, jobs_table, show_progress="hidden")
            retry_btn.click(retry_job, [session, retry_id], retry_status)
        with gr.Tab("À valider"):
            refresh_claims_btn = gr.Button("Actualiser les dossiers")
            claim_selector = gr.Dropdown(label="Déclaration")
            load_btn = gr.Button("Charger la revue", variant="primary")
            review_status = gr.Markdown()
            transcript = gr.Textbox(label="Transcription horodatée", lines=10, interactive=False)
            segments = gr.Dataframe(
                headers=["Index", "Début", "Fin", "Rôle", "Texte"],
                datatype=["number", "number", "number", "str", "str"],
                label="Locuteurs — modifier uniquement la colonne Rôle",
                interactive=True,
            )
            save_speakers_btn = gr.Button("Enregistrer les rôles")
            fields = gr.Dataframe(
                headers=[
                    "Champ",
                    "Proposition IA",
                    "Preuve",
                    "Confiance %",
                    "Valeur courante",
                    "Valeur validée",
                ],
                interactive=False,
                label="Traçabilité des valeurs",
            )
            missing = gr.Markdown()
            editable = gr.Code(label="Valeurs corrigées par l’agent", language="json")
            with gr.Row():
                save_btn = gr.Button("Enregistrer les corrections")
                validate_btn = gr.Button("Valider humainement", variant="primary")
            action_status = gr.Markdown()
            hidden_history = gr.Dataframe(visible=False)
            refresh_claims_btn.click(refresh_claims, session, [claim_selector, hidden_history])
            load_btn.click(
                load_review,
                [session, claim_selector],
                [call_id, review_status, transcript, segments, fields, editable, missing],
            )
            save_speakers_btn.click(save_speakers, [session, call_id, segments], action_status)
            save_btn.click(save_corrections, [session, claim_selector, editable], action_status)
            validate_btn.click(validate_claim, [session, claim_selector], action_status)
        with gr.Tab("Export JSON et envoi mock"):
            claim_action_id = gr.Textbox(label="Identifiant de la déclaration validée")
            with gr.Row():
                json_btn = gr.Button("Générer le JSON")
                send_btn = gr.Button("Envoyer au mock E-consta", variant="primary")
            json_file = gr.File(label="Export JSON")
            external_status = gr.Markdown()
            json_btn.click(generate_json, [session, claim_action_id], [json_file, external_status])
            send_btn.click(send_claim, [session, claim_action_id], external_status)
        with gr.Tab("Historique"):
            history_btn = gr.Button("Actualiser")
            history = gr.Dataframe(
                headers=[
                    "Déclaration",
                    "Statut",
                    "Assuré",
                    "Lieu",
                    "Confiance %",
                    "Corrections",
                    "Mise à jour",
                ],
                interactive=False,
            )
            history_selector = gr.Dropdown(visible=False)
            history_btn.click(refresh_claims, session, [history_selector, history])
        with gr.Tab("Dashboard responsable"):
            dashboard_btn = gr.Button("Actualiser")
            with gr.Row():
                dashboard_calls = gr.Number(label="Appels", interactive=False)
                dashboard_claims = gr.Number(label="Dossiers", interactive=False)
                dashboard_active = gr.Number(label="En cours", interactive=False)
                dashboard_pending = gr.Number(label="À valider", interactive=False)
                dashboard_validated = gr.Number(label="Validés", interactive=False)
                dashboard_sent = gr.Number(label="Envoyés", interactive=False)
                dashboard_errors = gr.Number(label="Erreurs", interactive=False)
            with gr.Row():
                dashboard_time = gr.Number(label="Temps moyen de traitement (s)", interactive=False)
                dashboard_corrected = gr.Number(label="Dossiers corrigés (%)", interactive=False)
                dashboard_uncorrected = gr.Number(label="Sans correction (%)", interactive=False)
            with gr.Row():
                dashboard_types = gr.Code(language="json", label="Types d’accident")
                dashboard_error_types = gr.Code(language="json", label="Erreurs par code")
            dashboard_alerts = gr.Markdown()
            dashboard_btn.click(
                load_dashboard,
                session,
                [
                    dashboard_calls,
                    dashboard_claims,
                    dashboard_active,
                    dashboard_pending,
                    dashboard_validated,
                    dashboard_sent,
                    dashboard_errors,
                    dashboard_time,
                    dashboard_corrected,
                    dashboard_uncorrected,
                    dashboard_types,
                    dashboard_error_types,
                    dashboard_alerts,
                ],
            )
    return demo


def build_app() -> gr.Blocks:
    configured_mode = get_settings().realtime_asr_default_mode
    default_asr_label = (
        ASR_PRECISION_LABEL if configured_mode == "precision" else ASR_FAST_LABEL
    )
    css = (UI_DIR / "style.css").read_text(encoding="utf-8")
    with gr.Blocks(
        title="E-Constat IA",
        theme=gr.themes.Soft(primary_hue="orange", neutral_hue="slate"),
        css=css,
    ) as demo:
        conversation = gr.State(new_conversation())

        with gr.Row(elem_id="poc-header"):
            gr.Image(
                value=str(ASACI_LOGO),
                label=None,
                show_label=False,
                show_download_button=False,
                interactive=False,
                container=False,
                elem_id="asaci-brand-logo",
                height=92,
                width=92,
            )
            gr.Markdown(
                "# E-Constat IA\n"
                "### Agent conversationnel de déclaration de sinistre\n"
                "Parlez naturellement : l’assistant transcrit, structure et vous demande de "
                "confirmer les informations sensibles.",
                elem_id="poc-title",
            )
            gr.HTML(
                '<div id="system-health">'
                '<strong><i></i> NOUVELLE INTERFACE · STITCH V2</strong>'
                '<span>✓ CPU local</span><span>✓ SQLite</span><span>✓ Whisper Small</span>'
                "</div>"
            )

        gr.HTML(
            """
            <div class="journey-strip" aria-label="Étapes de la déclaration">
              <span class="active"><b>1</b> Conversation</span>
              <span><b>2</b> Transcription</span>
              <span><b>3</b> Résumé et correction</span>
              <span><b>4</b> Validation humaine</span>
            </div>
            """
        )

        conversation_status = gr.Markdown("Prêt", elem_id="conversation-status")

        with gr.Row(elem_id="poc-workspace", equal_height=True):
            with gr.Column(scale=5, elem_classes="poc-panel conversation-panel"):
                gr.Markdown("## Conversation  ·  🎤 Je vous écoute")
                chat = gr.Chatbot(
                    value=[(None, CALL_IDLE_MESSAGE)],
                    label=None,
                    height=590,
                    elem_id="poc-conversation",
                )
                live_transcript = gr.Textbox(
                    label="Dernière réponse transcrite",
                    value="En attente de l’appel…",
                    interactive=False,
                    elem_id="live-transcript",
                )

            with gr.Column(scale=4, elem_classes="poc-panel question-panel"):
                gr.Markdown("QUESTION ACTUELLE", elem_id="question-kicker")
                current_question = gr.Markdown(
                    current_question_text(new_conversation()), elem_id="current-question"
                )
                with gr.Row(elem_id="conversation-controls"):
                    start_btn = gr.Button(
                        "🎙️ Démarrer l’appel", variant="primary", size="lg"
                    )
                    stop_btn = gr.Button(
                        "⏹ Arrêter l’appel", interactive=False, size="lg"
                    )
                activity = gr.HTML(activity_html("ready"), elem_id="current-activity")
                asr_mode = gr.Radio(
                    [ASR_FAST_LABEL, ASR_PRECISION_LABEL],
                    value=default_asr_label,
                    label="Qualité de reconnaissance",
                    info="Rapide pour le dialogue ; Précision pour noms et lieux difficiles.",
                    elem_id="asr-mode",
                )
                microphone = gr.Audio(
                    label="Transcription vocale en direct",
                    sources=["microphone"],
                    type="filepath",
                    streaming=True,
                    interactive=False,
                    elem_id="poc-microphone",
                )
                gr.Markdown(
                    "Après avoir démarré l’appel, activez le microphone une seule fois : "
                    "la voix sera transcrite par séquences pendant que vous parlez.",
                    elem_id="streaming-help",
                )
                gr.Markdown(
                    "Si la transcription affichée est incorrecte, écrivez ici ce que vous "
                    "avez réellement dit.",
                    elem_id="correction-help",
                )
                with gr.Row(elem_id="transcript-correction"):
                    text_correction = gr.Textbox(
                        label="Corriger la transcription",
                        placeholder="Ex. NSIA Assurances, téléphone 07 08 09 10 11…",
                        show_label=False,
                        scale=4,
                    )
                    correction_btn = gr.Button("Valider la correction", scale=2)
                gps_btn = gr.Button("📍 Proposer ma position actuelle", size="sm")
                gps_latitude = gr.Number(visible=False)
                gps_longitude = gr.Number(visible=False)
                gps_notice = gr.Markdown(elem_id="gps-notice")
                spoken_reply = gr.Textbox(visible=False)
                restart_btn = gr.Button("↻ Recommencer", size="sm")

            with gr.Column(scale=4, elem_classes="poc-panel information-panel"):
                gr.Markdown("## Informations recueillies")
                gr.Markdown(
                    "Les informations restent modifiables et devront être validées par un agent.",
                    elem_id="review-reminder",
                )
                claim_information = gr.HTML(
                    claim_information_html(new_conversation()), elem_id="claim-information"
                )

        gr.HTML(
            """
            <div class="trust-footer">
              <strong>ÉTAT TECHNIQUE</strong>
              <span><i class="ok-dot"></i> Microphone : prêt</span>
              <span><i class="ok-dot"></i> STT : Faster-Whisper</span>
              <span><i class="ok-dot"></i> Base : SQLite</span>
              <span>◇ Validation humaine obligatoire</span>
            </div>
            """
        )

        with gr.Accordion("📊 Tableau de bord des données enregistrées", open=True):
            gr.Markdown(
                "Suivi des appels, des dossiers et de la qualité de traitement.",
                elem_id="dashboard-intro",
            )
            dashboard_btn = gr.Button("Actualiser le tableau de bord", variant="primary")
            visual_dashboard = gr.HTML(
                '<p class="dashboard-empty">Cliquez sur Actualiser pour afficher les données.</p>',
                elem_id="visual-dashboard",
            )
            dashboard_claims_table = gr.Dataframe(
                headers=[
                    "Dossier",
                    "Statut",
                    "Assuré",
                    "Téléphone",
                    "Plaque",
                    "Lieu",
                    "Confiance %",
                    "Mise à jour",
                    "Données complètes",
                ],
                label="Toutes les informations enregistrées",
                interactive=False,
                wrap=True,
            )
            with gr.Row(elem_classes="dashboard-metrics"):
                dashboard_calls = gr.Number(label="Appels", interactive=False)
                dashboard_claims = gr.Number(label="Dossiers", interactive=False)
                dashboard_active = gr.Number(label="En cours", interactive=False)
                dashboard_pending = gr.Number(label="À valider", interactive=False)
                dashboard_validated = gr.Number(label="Validés", interactive=False)
                dashboard_sent = gr.Number(label="Envoyés", interactive=False)
            with gr.Row(elem_classes="dashboard-metrics"):
                dashboard_errors = gr.Number(label="Erreurs", interactive=False)
                dashboard_time = gr.Number(
                    label="Temps moyen de traitement (s)", interactive=False
                )
                dashboard_corrected = gr.Number(label="Dossiers corrigés (%)", interactive=False)
                dashboard_uncorrected = gr.Number(label="Sans correction (%)", interactive=False)
            with gr.Row():
                dashboard_types = gr.Code(
                    language="json", label="Dossiers par type", interactive=False
                )
                dashboard_error_types = gr.Code(
                    language="json", label="Erreurs par type", interactive=False
                )
            dashboard_alerts = gr.Markdown("Aucune donnée chargée.", elem_id="dashboard-alerts")

        start_event = start_btn.click(
            start_poc_call,
            None,
            [
                conversation,
                chat,
                claim_information,
                conversation_status,
                activity,
                current_question,
                microphone,
                start_btn,
                stop_btn,
                spoken_reply,
            ],
        )
        speech_finished = start_event.then(None, spoken_reply, None, js=SPEAK_JS)
        speech_finished.then(mark_listening, conversation, [conversation_status, activity])

        voice_event = microphone.stream(
            process_poc_stream,
            [microphone, chat, conversation, asr_mode],
            [
                conversation_status,
                activity,
                live_transcript,
                chat,
                conversation,
                claim_information,
                current_question,
                spoken_reply,
                microphone,
            ],
            every=3,
            trigger_mode="always_last",
            show_progress="hidden",
        )
        voice_finished = voice_event.then(None, spoken_reply, None, js=SPEAK_JS)
        voice_finished.then(mark_listening, conversation, [conversation_status, activity])

        correction_event = correction_btn.click(
            process_poc_text,
            [text_correction, chat, conversation],
            [
                conversation_status,
                activity,
                live_transcript,
                chat,
                conversation,
                claim_information,
                current_question,
                spoken_reply,
                microphone,
                text_correction,
            ],
        )
        correction_spoken = correction_event.then(None, spoken_reply, None, js=SPEAK_JS)
        correction_spoken.then(mark_listening, conversation, [conversation_status, activity])

        dashboard_btn.click(
            load_dashboard,
            conversation,
            [
                dashboard_calls,
                dashboard_claims,
                dashboard_active,
                dashboard_pending,
                dashboard_validated,
                dashboard_sent,
                dashboard_errors,
                dashboard_time,
                dashboard_corrected,
                dashboard_uncorrected,
                dashboard_types,
                dashboard_error_types,
                dashboard_alerts,
            ],
        )
        dashboard_btn.click(
            load_dashboard_view,
            conversation,
            [visual_dashboard, dashboard_claims_table],
        )

        gps_event = gps_btn.click(None, None, [gps_latitude, gps_longitude], js=GPS_JS)
        gps_event.then(
            apply_gps_location,
            [gps_latitude, gps_longitude, conversation, chat],
            [conversation, chat, claim_information, current_question, gps_notice],
        )

        stop_btn.click(
            stop_poc_call,
            None,
            [conversation_status, activity, microphone, start_btn, stop_btn],
        )
        restart_btn.click(
            reset_poc_call,
            None,
            [
                conversation,
                chat,
                claim_information,
                current_question,
                conversation_status,
                activity,
                live_transcript,
                microphone,
                start_btn,
                stop_btn,
            ],
        )
    return demo


demo = build_app()


if __name__ == "__main__":
    if get_settings().realtime_asr_warmup:
        threading.Thread(
            target=get_realtime_transcriber(get_settings()).warm_up,
            name="realtime-asr-warmup",
            daemon=True,
        ).start()
    demo.queue(default_concurrency_limit=4, max_size=32).launch(
        server_name=UI_HOST, server_port=UI_PORT
    )
