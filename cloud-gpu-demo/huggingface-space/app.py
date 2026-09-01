"""Démonstrateur GPU public : aucune donnée client réelle ne doit être utilisée."""

from __future__ import annotations

import re
import time
from pathlib import Path

import gradio as gr
import librosa
import spaces
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

MODEL_ID = "openai/whisper-large-v3-turbo"

LOAD_STARTED = time.perf_counter()
model = AutoModelForSpeechSeq2Seq.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.float16,
    low_cpu_mem_usage=True,
    use_safetensors=True,
)
model.to("cuda")
processor = AutoProcessor.from_pretrained(MODEL_ID)
asr = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    torch_dtype=torch.float16,
    device=0,
)
LOAD_SECONDS = round(time.perf_counter() - LOAD_STARTED, 3)

EXPECTED_FIELDS = {
    "Nom": "nom_assure",
    "Téléphone": "telephone_assure",
    "Assureur": "assureur",
    "Lieu": "lieu",
    "Nombre de véhicules": "nombre_vehicules",
    "Circonstances": "circonstances",
    "Dommages": "dommages",
}


def extract_expected(field: str, transcript: str):
    """Extraction volontairement explicable pour comparer l'ASR, pas un verdict IA."""
    text = " ".join(transcript.split()).strip(" .")
    if field == "telephone_assure":
        digits = re.sub(r"\D", "", text)
        return digits if 8 <= len(digits) <= 13 else None
    if field == "nombre_vehicules":
        words = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5}
        match = re.search(r"\b(\d{1,2}|un|une|deux|trois|quatre|cinq)\b", text.lower())
        return int(match.group(1)) if match and match.group(1).isdigit() else words.get(match.group(1)) if match else None
    prefixes = {
        "nom_assure": r"^(?:je m'appelle|mon nom est|moi c'est)\s+",
        "assureur": r"^(?:je suis assur(?:é|ée) chez|mon assureur est)\s+",
        "lieu": r"^(?:l'accident a eu lieu|ça s'est passé)\s+(?:à|au)?\s*",
        "dommages": r"^(?:il y a|je constate|les dommages sont)\s+",
    }
    return re.sub(prefixes.get(field, r"a^"), "", text, flags=re.I).strip() or None


def conversation_signal(text: str):
    """Signal textuel non clinique ; aucune émotion n'est affirmée comme un fait."""
    lowered = text.lower()
    urgent = ("blessé", "danger", "saigne", "urgence", "bloqué")
    stressed = ("paniqué", "peur", "stressé", "angoissé", "je tremble")
    confused = ("je ne comprends", "je ne sais pas", "répétez", "perdu")
    if any(word in lowered for word in urgent):
        return {"signal": "urgence_explicite", "confiance": "élevée", "action": "vérifier immédiatement la sécurité"}
    if any(word in lowered for word in stressed):
        return {"signal": "stress_déclaré", "confiance": "moyenne", "action": "ralentir et reformuler"}
    if any(word in lowered for word in confused):
        return {"signal": "confusion_possible", "confiance": "moyenne", "action": "poser une question courte"}
    return {"signal": "aucun_signal_explicite", "confiance": "faible", "action": "continuer normalement"}


@spaces.GPU(duration=45)
def transcribe(audio_path: str | None, field_label: str):
    if not audio_path:
        raise gr.Error("Enregistrez ou importez un audio de démonstration.")
    started = time.perf_counter()
    audio, _ = librosa.load(Path(audio_path), sr=16_000, mono=True)
    result = asr(
        audio,
        generate_kwargs={"language": "fr", "task": "transcribe"},
        return_timestamps=True,
    )
    elapsed = time.perf_counter() - started
    transcript = result["text"].strip()
    duration = len(audio) / 16_000
    expected = EXPECTED_FIELDS[field_label]
    metrics = {
        "model": MODEL_ID,
        "device": torch.cuda.get_device_name(0),
        "vram_allouée_go": round(torch.cuda.memory_allocated() / 1024**3, 2),
        "chargement_secondes": LOAD_SECONDS,
        "audio_secondes": round(duration, 2),
        "inférence_secondes": round(elapsed, 3),
        "facteur_temps_réel": round(elapsed / max(duration, 0.01), 3),
    }
    extraction = {
        "champ_attendu": expected,
        "valeur": extract_expected(expected, transcript),
        "preuve": transcript,
    }
    return transcript, extraction, conversation_signal(transcript), metrics


with gr.Blocks(title="E-Constat IA — GPU Lab", theme=gr.themes.Soft()) as demo:
    gr.Markdown(
        "# E-Constat IA — laboratoire GPU\n"
        "Testez uniquement un audio synthétique ou autorisé. "
        "Le signal conversationnel n'est pas un diagnostic émotionnel."
    )
    with gr.Row():
        with gr.Column(scale=1):
            audio = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Réponse client")
            field = gr.Dropdown(list(EXPECTED_FIELDS), value="Lieu", label="Question/Champ attendu")
            run = gr.Button("Transcrire sur GPU", variant="primary")
        with gr.Column(scale=2):
            transcript = gr.Textbox(label="Transcription Whisper Large v3 Turbo", lines=4)
            extraction = gr.JSON(label="Extraction ciblée")
            signal = gr.JSON(label="Signal conversationnel prudent")
            metrics = gr.JSON(label="Mesures GPU")
    run.click(transcribe, [audio, field], [transcript, extraction, signal, metrics])

demo.queue(default_concurrency_limit=1).launch()

