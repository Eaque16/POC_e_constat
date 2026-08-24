import json
import os
from datetime import UTC, datetime
from pathlib import Path

import gradio as gr

from econstat.ui.api_client import APIError, EConstatAPI

API_URL = os.getenv("ECONSTAT_API_URL", "http://127.0.0.1:8000/api")
UI_PORT = int(os.getenv("ECONSTAT_UI_PORT", "7860"))
JOB_POLL_SECONDS = float(os.getenv("JOB_POLL_SECONDS", "2"))
UI_DIR = Path(__file__).resolve().parent
api = EConstatAPI(API_URL)


def require_token(session: dict | None) -> str:
    if not session or not session.get("token"):
        raise gr.Error("Connectez-vous avant d’utiliser cette fonction.")
    return session["token"]


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
    return refresh_jobs(session) if session and session.get("token") else []


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
        f"**Champs manquants :** {missing}\n\n"
        f"**Questions suggérées :**\n{questions or '—'}",
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
    return json.dumps(data, ensure_ascii=False, indent=2)


def build_app() -> gr.Blocks:
    css = (UI_DIR / "style.css").read_text(encoding="utf-8")
    with gr.Blocks(
        title="E-Constat IA",
        theme=gr.themes.Soft(primary_hue="orange", neutral_hue="slate"),
        css=css,
    ) as demo:
        session = gr.State({})
        call_id = gr.State("")
        gr.Markdown(
            "# E-Constat IA\nTraitement différé sur CPU — "
            "**l’IA propose, l’humain corrige et valide.**",
            elem_id="asaci-header",
        )
        identity = gr.Markdown("Non connecté", elem_id="identity")
        with gr.Tab("Connexion"):
            username = gr.Textbox(label="Utilisateur", value="agent.demo")
            password = gr.Textbox(label="Mot de passe", type="password")
            with gr.Row():
                login_btn = gr.Button("Se connecter", variant="primary")
                logout_btn = gr.Button("Se déconnecter")
            login_btn.click(login, [username, password], [session, identity])
            logout_btn.click(logout, None, [session, identity])
        with gr.Tab("Nouveau dossier"):
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
                    "Job", "Appel", "Profil", "Statut", "Étape", "Progression %",
                    "Erreur", "Durée écoulée (s)", "Mise à jour",
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
                    "Champ", "Proposition IA", "Preuve", "Confiance %",
                    "Valeur courante", "Valeur validée",
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
            refresh_claims_btn.click(
                refresh_claims, session, [claim_selector, hidden_history]
            )
            load_btn.click(
                load_review,
                [session, claim_selector],
                [call_id, review_status, transcript, segments, fields, editable, missing],
            )
            save_speakers_btn.click(
                save_speakers, [session, call_id, segments], action_status
            )
            save_btn.click(
                save_corrections, [session, claim_selector, editable], action_status
            )
            validate_btn.click(validate_claim, [session, claim_selector], action_status)
        with gr.Tab("Export JSON et envoi mock"):
            claim_action_id = gr.Textbox(label="Identifiant de la déclaration validée")
            with gr.Row():
                json_btn = gr.Button("Générer le JSON")
                send_btn = gr.Button("Envoyer au mock E-consta", variant="primary")
            json_file = gr.File(label="Export JSON")
            external_status = gr.Markdown()
            json_btn.click(
                generate_json, [session, claim_action_id], [json_file, external_status]
            )
            send_btn.click(send_claim, [session, claim_action_id], external_status)
        with gr.Tab("Historique"):
            history_btn = gr.Button("Actualiser")
            history = gr.Dataframe(
                headers=[
                    "Déclaration", "Statut", "Assuré", "Lieu", "Confiance %",
                    "Corrections", "Mise à jour",
                ],
                interactive=False,
            )
            history_selector = gr.Dropdown(visible=False)
            history_btn.click(refresh_claims, session, [history_selector, history])
        with gr.Tab("Dashboard responsable"):
            dashboard_btn = gr.Button("Actualiser")
            dashboard_json = gr.Code(language="json", label="Indicateurs")
            dashboard_btn.click(load_dashboard, session, dashboard_json)
    return demo


demo = build_app()


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=4, max_size=32).launch(
        server_name="127.0.0.1", server_port=UI_PORT
    )
