import json
import os
import shutil
import threading
import uuid
from pathlib import Path

import gradio as gr
import httpx
from faster_whisper import WhisperModel

from econstat.schemas.claim import QUESTION_TEMPLATES, REQUIRED_FIELDS, ClaimData
from econstat.services.extraction import deterministic_extract

API = os.getenv("ECONSTAT_API_URL", "http://localhost:8000/api")
UI_PORT = int(os.getenv("ECONSTAT_UI_PORT", "7860"))
MODEL_PATH = os.getenv("WHISPER_MODEL_PATH", "models/whisper-ct2")
UI_DIR = Path(__file__).resolve().parent
LOGO_PATH = UI_DIR / "assets" / "asaci-logo.png"
CSS_PATH = UI_DIR / "style.css"
RECORDINGS_DIR = Path(os.getenv("RECORDINGS_DIR", "data/recordings"))

_whisper = None
_whisper_lock = threading.Lock()


def api_headers():
    """L'API locale de démonstration fonctionne volontairement sans authentification."""
    return {}


def whisper_model():
    global _whisper
    if _whisper is None:
        with _whisper_lock:
            if _whisper is None:
                _whisper = WhisperModel(MODEL_PATH, device="cpu", compute_type="int8")
    return _whisper


def merge_transcript(previous, new_text):
    previous = (previous or "").strip()
    new_text = (new_text or "").strip()
    if not new_text:
        return previous
    if new_text in previous:
        return previous
    if previous and previous in new_text:
        return new_text
    return f"{previous} {new_text}".strip()


def new_live_session() -> dict:
    return {"id": str(uuid.uuid4()), "chunk": 0}


def save_audio_chunk(audio_path: str, session: dict) -> tuple[dict, Path]:
    """Conserve chaque fragment micro dans un dossier propre à l'appel."""
    session = dict(session or new_live_session())
    session["chunk"] = int(session.get("chunk", 0)) + 1
    session_dir = RECORDINGS_DIR / session["id"]
    session_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(audio_path).suffix or ".wav"
    target = session_dir / f"fragment-{session['chunk']:05d}{suffix}"
    shutil.copy2(audio_path, target)
    return session, target


def live_rows(transcript: str) -> tuple[list, str, str]:
    """Extrait les champs rapides sans attendre le modèle génératif."""
    data, confidence = deterministic_extract(transcript)
    validated = ClaimData.model_validate(data)
    rows = [
        [field.replace("_", " ").title(), str(value), confidence.get(field, 0)]
        for field, value in validated.model_dump(mode="json").items()
        if value not in (None, "", [])
    ]
    missing = [field for field in REQUIRED_FIELDS if getattr(validated, field) is None]
    questions = "\n".join(f"• {QUESTION_TEMPLATES[field]}" for field in missing[:4])
    payload = json.dumps(validated.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return rows, questions or "✅ Tous les champs obligatoires sont détectés.", payload


def live_transcribe(audio_path, transcript, session):
    """Enregistre, transcrit et analyse chaque fragment dès sa réception."""
    if not audio_path:
        rows, questions, payload = live_rows(transcript or "")
        return (
            transcript or "",
            transcript or "",
            rows,
            questions,
            payload,
            session or new_live_session(),
            "🎙️ Micro prêt : commencez à parler.",
        )
    try:
        session, saved_chunk = save_audio_chunk(audio_path, session)
        segments, _ = whisper_model().transcribe(
            str(audio_path),
            language="fr",
            beam_size=1,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        detected = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        combined = merge_transcript(transcript, detected)
        rows, questions, payload = live_rows(combined)
        message = (
            f"🔴 Direct — fragment {session['chunk']} enregistré, transcrit et analysé. "
            f"Dossier audio : {saved_chunk.parent}"
        )
        if not detected:
            message = f"🎧 Fragment {session['chunk']} enregistré, aucune parole nette détectée."
        return combined, combined, rows, questions, payload, session, message
    except Exception as exc:
        rows, questions, payload = live_rows(transcript or "")
        return (
            transcript or "",
            transcript or "",
            rows,
            questions,
            payload,
            session or new_live_session(),
            f"❌ Traitement temps réel : {exc}",
        )


def clear_session():
    return "", "", "", [], "", "{}", new_live_session(), "🎙️ Nouvelle session prête."


def format_extraction(payload):
    extraction = payload["extraction"]
    data = extraction["data"]
    confidence = extraction["field_confidences"]
    rows = [
        [field.replace("_", " ").title(), str(value), confidence.get(field, 0)]
        for field, value in data.items()
        if value not in (None, "", [])
    ]
    questions = "\n".join(f"• {item}" for item in extraction["suggested_questions"])
    questions = questions or "✅ Aucun champ obligatoire manquant détecté."
    status = (
        "✅ Transcript analysé et déclaration enregistrée en base. Confiance globale : "
        f"{round(extraction['overall_confidence'] * 100)} %"
    )
    return (
        payload["claim_id"],
        payload["call_id"],
        rows,
        questions,
        status,
        json.dumps(data, ensure_ascii=False, indent=2),
    )


def process_declaration(transcript):
    if not (transcript or "").strip():
        raise gr.Error("Parlez d'abord dans le microphone avant de lancer l'analyse.")
    try:
        response = httpx.post(
            f"{API}/calls/demo", json={"transcript": transcript}, headers=api_headers(), timeout=180
        )
        response.raise_for_status()
        return format_extraction(response.json())
    except httpx.HTTPStatusError as exc:
        raise gr.Error(f"Erreur API : {exc.response.text}") from exc
    except Exception as exc:
        raise gr.Error(f"Traitement impossible : {exc}") from exc


def update_claim(claim_id, data_json):
    if not claim_id:
        raise gr.Error("Aucune déclaration active.")
    try:
        response = httpx.put(
            f"{API}/claims/{claim_id}",
            json={"data": json.loads(data_json)},
            headers=api_headers(),
            timeout=30,
        )
        response.raise_for_status()
        return "✅ Corrections humaines enregistrées et auditées."
    except Exception as exc:
        raise gr.Error(f"Correction impossible : {exc}") from exc


def validate_claim(claim_id):
    if not claim_id:
        raise gr.Error("Aucune déclaration active.")
    response = httpx.post(f"{API}/claims/{claim_id}/validate", headers=api_headers(), timeout=30)
    if not response.is_success:
        raise gr.Error(response.text)
    return "✅ Dossier validé explicitement par l'agent humain. L'envoi est autorisé."


def generate_pdf(claim_id):
    if not claim_id:
        raise gr.Error("Aucune déclaration active.")
    response = httpx.get(f"{API}/claims/{claim_id}/pdf", headers=api_headers(), timeout=30)
    if not response.is_success:
        raise gr.Error(response.text)
    path = response.json()["path"]
    return path, f"✅ PDF généré : {path}"


def send_claim(claim_id):
    if not claim_id:
        raise gr.Error("Aucune déclaration active.")
    response = httpx.post(f"{API}/claims/{claim_id}/send", headers=api_headers(), timeout=30)
    if not response.is_success:
        raise gr.Error(response.text)
    return f"✅ Envoyé au mock E-consta. Référence : {response.json()['id']}"


def load_history():
    response = httpx.get(f"{API}/claims", headers=api_headers(), timeout=30)
    response.raise_for_status()
    return [
        [
            claim["id"],
            claim["status"],
            claim.get("data", {}).get("nom_assure", "—"),
            claim.get("data", {}).get("lieu", "—"),
            round(claim.get("confidence_score", 0) * 100),
            claim.get("human_edits", 0),
        ]
        for claim in response.json()
    ]


def load_dashboard():
    response = httpx.get(f"{API}/dashboard", headers=api_headers(), timeout=30)
    response.raise_for_status()
    data = response.json()
    return (
        data["appels"],
        data["declarations"],
        data["validees"],
        data["en_attente"],
        data.get("temps_moyen_secondes") or 0,
        json.dumps(data.get("motifs", {}), indent=2, ensure_ascii=False),
        "\n".join(data.get("alertes", [])) or "Aucune alerte",
    )


with gr.Blocks(
    title="E-Constat IA",
    theme=gr.themes.Soft(primary_hue="orange", neutral_hue="slate"),
    css=CSS_PATH.read_text(encoding="utf-8"),
) as demo:
    with gr.Row(elem_id="asaci-header"):
        gr.Image(
            value=str(LOGO_PATH),
            show_label=False,
            interactive=False,
            container=False,
            height=90,
            elem_id="asaci-logo",
            scale=1,
        )
        gr.Markdown(
            "# E-Constat IA\n" "Transcription, analyse et constitution du constat pendant l'appel.",
            elem_id="hero-copy",
        )
        gr.Markdown("🔴 **TRAITEMENT EN DIRECT**", elem_id="live-badge")
    transcript_state = gr.State("")
    live_session = gr.State(new_live_session())
    claim_id = gr.State("")
    call_id = gr.State("")

    with gr.Tab("1 — Appel en direct"):
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Écoute et enregistrement")
                audio = gr.Audio(
                    label="Microphone de l'appel",
                    sources=["microphone"],
                    type="filepath",
                    streaming=True,
                )
                transcript = gr.Textbox(
                    value="",
                    label="Transcription instantanée",
                    lines=10,
                    placeholder="Les paroles apparaissent ici pendant l'appel…",
                )
            with gr.Column(scale=1):
                gr.Markdown("### Informations détectées à l'instant")
                live_fields = gr.Dataframe(
                    headers=["Champ", "Valeur détectée", "Confiance"],
                    datatype=["str", "str", "number"],
                    interactive=False,
                    elem_id="live-table",
                )
                live_questions = gr.Markdown("Les questions utiles apparaîtront ici.")
                live_json = gr.Code(label="Données en cours", language="json", visible=False)
        transcription_status = gr.Markdown("🎙️ Micro prêt : commencez à parler.")
        with gr.Row():
            clear_btn = gr.Button("🧹 Nouvelle session")
            process_btn = gr.Button("Créer le dossier avec l'analyse complète", variant="primary")

    with gr.Tab("2 — Extraction et contrôle humain"):
        processing_status = gr.Markdown("Aucune déclaration traitée")
        fields = gr.Dataframe(
            headers=["Champ", "Valeur détectée", "Confiance"],
            datatype=["str", "str", "number"],
            label="Informations reconnues",
            interactive=False,
        )
        questions = gr.Markdown("Les questions suggérées apparaîtront ici.")
        editable_json = gr.Code(label="Données modifiables par l'agent", language="json")
        with gr.Row():
            save_btn = gr.Button("💾 Enregistrer mes corrections")
            validate_btn = gr.Button("✅ Valider humainement", variant="primary")
        action_status = gr.Markdown()
        process_btn.click(
            process_declaration,
            transcript,
            [claim_id, call_id, fields, questions, processing_status, editable_json],
        )
        save_btn.click(update_claim, [claim_id, editable_json], action_status)
        validate_btn.click(validate_claim, claim_id, action_status)

    with gr.Tab("3 — PDF et envoi E-consta"):
        gr.Markdown("Ces actions restent bloquées avant la validation humaine.")
        with gr.Row():
            pdf_btn = gr.Button("📄 Générer le PDF")
            send_btn = gr.Button("📤 Envoyer au mock E-consta", variant="primary")
        pdf_file = gr.File(label="Constat PDF")
        output_status = gr.Markdown()
        pdf_btn.click(generate_pdf, claim_id, [pdf_file, output_status])
        send_btn.click(send_claim, claim_id, output_status)

    with gr.Tab("4 — Historique"):
        refresh_history = gr.Button("Actualiser l'historique")
        history = gr.Dataframe(
            headers=["Déclaration", "Statut", "Assuré", "Lieu", "Confiance %", "Corrections"],
            interactive=False,
        )
        refresh_history.click(load_history, None, history)

    with gr.Tab("5 — Dashboard responsable"):
        dashboard_btn = gr.Button("Actualiser le dashboard")
        with gr.Row():
            calls_kpi = gr.Number(label="Appels")
            claims_kpi = gr.Number(label="Déclarations")
            validated_kpi = gr.Number(label="Validées")
            pending_kpi = gr.Number(label="En attente")
            time_kpi = gr.Number(label="Temps moyen (s)")
        motives = gr.Code(label="Répartition des motifs", language="json")
        alerts = gr.Textbox(label="Alertes")
        dashboard_btn.click(
            load_dashboard,
            None,
            [calls_kpi, claims_kpi, validated_kpi, pending_kpi, time_kpi, motives, alerts],
        )

    audio.stream(
        live_transcribe,
        [audio, transcript_state, live_session],
        [
            transcript_state,
            transcript,
            live_fields,
            live_questions,
            live_json,
            live_session,
            transcription_status,
        ],
        show_progress="hidden",
    )
    clear_btn.click(
        clear_session,
        None,
        [
            transcript_state,
            transcript,
            audio,
            live_fields,
            live_questions,
            live_json,
            live_session,
            transcription_status,
        ],
    )

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=4, max_size=32).launch(
        server_name="127.0.0.1",
        server_port=UI_PORT,
        allowed_paths=[str(LOGO_PATH), str(RECORDINGS_DIR.resolve())],
    )
