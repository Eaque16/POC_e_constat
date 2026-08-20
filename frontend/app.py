"""Microphone-based demonstration interface for E-Constat IA."""

import os
from pathlib import Path
from typing import Any

import gradio as gr
import httpx

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
TRANSCRIPTION_TIMEOUT_SECONDS = 600.0
EXTRACTION_TIMEOUT_SECONDS = 15.0

APP_CSS = """
.gradio-container {
    max-width: 1180px !important;
    margin: 0 auto !important;
    background: linear-gradient(145deg, #f8fafc 0%, #eef6ff 100%);
}
.hero {
    padding: 28px 32px;
    border-radius: 24px;
    color: white;
    background: linear-gradient(120deg, #075985 0%, #0f766e 100%);
    box-shadow: 0 18px 45px rgba(15, 118, 110, 0.18);
    margin-bottom: 18px;
}
.hero h1, .hero h2, .hero p { color: white !important; margin: 0.25rem 0; }
.step-card {
    border: 1px solid #dbeafe !important;
    border-radius: 18px !important;
    background: rgba(255, 255, 255, 0.92) !important;
    padding: 8px !important;
    box-shadow: 0 8px 28px rgba(15, 23, 42, 0.06);
}
.primary-action { min-height: 48px !important; font-weight: 700 !important; }
.status-box textarea { font-weight: 650 !important; color: #0f766e !important; }
footer { display: none !important; }
"""


def get_transcription_url() -> str:
    """Build the backend URL from local configuration."""

    backend_url = os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")
    return f"{backend_url}/audio/transcribe"


def get_extraction_url() -> str:
    backend_url = os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")
    return f"{backend_url}/claims/extract"


def transcribe_from_frontend(
    audio_path: str | None,
) -> tuple[str, dict[str, Any], str]:
    """Send a recorded clip to FastAPI and prepare values for the UI."""

    if not audio_path:
        return "", {}, "Enregistrez ou importez d'abord un audio."

    path = Path(audio_path)
    try:
        with path.open("rb") as audio_file:
            response = httpx.post(
                get_transcription_url(),
                files={"audio": (path.name, audio_file, "application/octet-stream")},
                timeout=TRANSCRIPTION_TIMEOUT_SECONDS,
            )
        response.raise_for_status()
        payload = response.json()
    except FileNotFoundError:
        return "", {}, "Le fichier audio selectionne est introuvable."
    except httpx.HTTPStatusError as error:
        try:
            detail = error.response.json().get("detail", "Erreur du backend")
        except ValueError:
            detail = "Erreur du backend"
        return "", {}, f"Transcription refusee : {detail}"
    except httpx.RequestError:
        return (
            "",
            {},
            "Backend indisponible. Demarrez FastAPI sur le port 8000.",
        )
    except (KeyError, TypeError, ValueError):
        return "", {}, "Le backend a retourne une reponse invalide."

    metadata = {
        "language": payload["language"],
        "language_probability": payload["language_probability"],
        "duration_seconds": payload["duration"],
        "segments": payload.get("segments", []),
    }
    return payload["text"], metadata, "Transcription terminee."


def extract_from_frontend(
    transcription: str | None,
    use_llm: bool = False,
) -> tuple[str, dict[str, Any], str, list[dict[str, Any]], str]:
    """Request structured extraction and render the important fields."""

    if not transcription or not transcription.strip():
        return "", {}, "", [], "Aucune transcription à analyser."

    try:
        response = httpx.post(
            get_extraction_url(),
            json={"transcription": transcription, "use_llm": use_llm},
            timeout=EXTRACTION_TIMEOUT_SECONDS if not use_llm else 140.0,
        )
        response.raise_for_status()
        payload = response.json()
        claim = payload["claim"]
    except httpx.HTTPStatusError as error:
        try:
            detail = error.response.json().get("detail", "Erreur du backend")
        except ValueError:
            detail = "Erreur du backend"
        return "", {}, "", [], f"Extraction refusée : {detail}"
    except httpx.RequestError:
        return "", {}, "", [], "Backend indisponible. Démarrez FastAPI sur le port 8000."
    except (KeyError, TypeError, ValueError):
        return "", {}, "", [], "Le backend a retourné une extraction invalide."

    insured = claim["assure"]
    vehicle = claim["vehicule"]
    incident = claim["sinistre"]

    def shown(value: Any) -> str:
        return str(value) if value not in (None, "", []) else "Non renseigné"

    damages = ", ".join(incident["degats"]) if incident["degats"] else None
    summary = (
        "### Informations importantes détectées\n\n"
        "| Information | Valeur |\n|---|---|\n"
        f"| Assuré | {shown(' '.join(filter(None, [insured['prenom'], insured['nom']])))} |\n"
        f"| Téléphone | {shown(insured['telephone'])} |\n"
        f"| Contrat | {shown(insured['numero_contrat'])} |\n"
        f"| Immatriculation | {shown(vehicle['immatriculation'])} |\n"
        f"| Date / heure | {shown(incident['date_sinistre'])} / {shown(incident['heure_sinistre'])} |\n"
        f"| Lieu | {shown(incident['lieu'])} |\n"
        f"| Type | {shown(incident['type_sinistre'])} |\n"
        f"| Dégâts | {shown(damages)} |"
    )
    questions = payload.get("questions", [])
    question_text = "### Questions prioritaires\n\n" + "\n".join(
        f"{index}. {question}" for index, question in enumerate(questions, start=1)
    ) if questions else "### Dossier complet\n\nAucune question critique restante."
    suggestions = payload.get("correction_suggestions", [])
    elapsed = payload.get("processing_time_ms", 0)
    return (
        summary,
        claim,
        question_text,
        suggestions,
        f"Extraction terminée ({payload['extraction_method']}, {elapsed} ms).",
    )


def build_demo() -> gr.Blocks:
    """Create the local call-simulation interface."""

    with gr.Blocks(title="E-Constat IA") as demo:
        gr.Markdown(
            "# E-Constat IA\n"
            "## Votre déclaration automobile, simplement par la voix\n"
            "Enregistrez le récit, contrôlez la transcription, puis transformez-le "
            "en informations structurées.",
            elem_classes=["hero"],
        )

        with gr.Row():
            with gr.Column(elem_classes=["step-card"]):
                gr.Markdown("### 1 · Récit audio")
                audio = gr.Audio(
                    sources=["microphone", "upload"],
                    type="filepath",
                    format="wav",
                    label="Microphone ou fichier audio",
                )
                transcribe_button = gr.Button(
                    "Transcrire l'appel",
                    variant="primary",
                    elem_classes=["primary-action"],
                )
                status = gr.Textbox(
                    label="État du traitement",
                    interactive=False,
                    elem_classes=["status-box"],
                )

            with gr.Column(elem_classes=["step-card"]):
                gr.Markdown("### 2 · Transcription contrôlable")
                transcription = gr.Textbox(
                    label="Récit transcrit",
                    lines=10,
                    interactive=True,
                    placeholder="La transcription apparaîtra ici. Vous pouvez la corriger.",
                )
                metadata = gr.JSON(label="Segments et métadonnées audio")

        with gr.Column(elem_classes=["step-card"]):
            gr.Markdown("### 3 · Transformation en constat structuré")
            extract_button = gr.Button(
                "Extraire les informations importantes",
                variant="primary",
                elem_classes=["primary-action"],
            )
            use_llm = gr.Checkbox(
                value=False,
                label="Analyse approfondie avec Qwen (optionnelle et plus lente)",
            )
            extraction_status = gr.Textbox(
                label="État de l'extraction",
                interactive=False,
                elem_classes=["status-box"],
            )
            with gr.Row():
                claim_summary = gr.Markdown("Les informations détectées apparaîtront ici.")
                structured_claim = gr.JSON(label="E-Constat JSON")
            with gr.Row():
                follow_up_questions = gr.Markdown("Les questions manquantes apparaîtront ici.")
                correction_suggestions = gr.JSON(label="Corrections à confirmer")

        transcribe_button.click(
            fn=transcribe_from_frontend,
            inputs=audio,
            outputs=[transcription, metadata, status],
        )
        extract_button.click(
            fn=extract_from_frontend,
            inputs=[transcription, use_llm],
            outputs=[
                claim_summary,
                structured_claim,
                follow_up_questions,
                correction_suggestions,
                extraction_status,
            ],
        )

    return demo


demo = build_demo()


if __name__ == "__main__":
    demo.launch(
        server_name=os.getenv("GRADIO_SERVER_NAME", "127.0.0.1"),
        server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
        theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate"),
        css=APP_CSS,
    )
