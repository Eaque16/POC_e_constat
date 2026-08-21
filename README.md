# E-Constat IA

POC monolithique destiné à ASA-CI Technologie : transcription et diarisation d'un appel,
extraction structurée assistée par Qwen3, validation humaine, PDF, envoi vers une API E-consta
simulée et indicateurs de pilotage.

## État de validation sur la machine de construction

Au 21 août 2026, Python 3.11.9, Git 2.55, FFmpeg 9.0, Ollama 0.32.15, Qwen3 4B et la pile IA
native CPU sont installés. PyTorch 2.4.1, torchaudio, faster-whisper, pyannote.audio et CTranslate2
s'importent correctement. Les 11 tests passent, `pip check` ne trouve aucune dépendance cassée,
l'API répond sur `/health` et l'interface Gradio se charge.

La machine ne possède qu'un GPU Intel UHD : CUDA est donc indisponible et le repli CPU est actif.
WSL2 reste désactivé car l'activation des fonctionnalités Windows exige une élévation UAC qui a été
annulée. Docker Desktop est installé mais son moteur Linux dépend de cette activation. Les gros
fichiers LFS Hugging Face restent bloqués par le CDN sur le réseau courant ; les fragments incomplets
ont été supprimés. Enfin, pyannote Community-1 demeure gated et requiert un `HF_TOKEN` après
acceptation manuelle de sa licence. Ne pas considérer le benchmark STT/diarisation comme validé
avant résolution de ces deux prérequis externes.

> Principe de sécurité : l'IA propose. L'agent vérifie, modifie et valide. L'API et le client
> externe bloquent tous deux un envoi non précédé d'une validation humaine explicite.

## Architecture

- `econstat/api` : FastAPI, JWT et contrôle des rôles `agent` / `responsable`.
- `econstat/services` : Whisper, pyannote, règles, Qwen3/Ollama, score, PDF et client externe.
- `econstat/schemas` : contrat Pydantic et JSON Schema de la déclaration.
- PostgreSQL 16 + Alembic : appels, déclarations, utilisateurs et journal d'audit.
- Gradio : interface de démonstration et rejeu progressif (fenêtres simulées).
- `econstat.mock_server` : contrat mock `POST /sinistres`, `GET /sinistres/{id}`.

Les modèles lourds sont chargés à la demande. Les tests du domaine fonctionnent donc sans GPU.
Le streaming est volontairement un rejeu progressif convaincant, et non une chaîne téléphonique
temps réel de production.

## Installation from scratch — WSL2 Ubuntu 24.04 (recommandé)

- [ ] Dans PowerShell administrateur : `wsl --install -d Ubuntu-24.04`, puis redémarrer.
- [ ] Installer le pilote NVIDIA Windows récent. Ne pas installer de pilote NVIDIA Linux dans WSL.
- [ ] Dans Ubuntu, vérifier `nvidia-smi`. La carte et sa VRAM doivent apparaître.
- [ ] Installer Python 3.11, `python3.11-venv`, Git et les bibliothèques système audio (`ffmpeg`).
- [ ] Installer Docker Desktop Windows, activer *Use the WSL 2 based engine* et l'intégration Ubuntu.
- [ ] Installer Ollama nativement sous Windows et vérifier depuis WSL l'URL configurée.
- [ ] Créer un compte Hugging Face, accepter les conditions de
  `pyannote/speaker-diarization-community-1`, créer un token en lecture et renseigner `HF_TOKEN`.
- [ ] Copier `.env.example` vers `.env`, remplacer `JWT_SECRET`, vérifier les révisions de modèles.
- [ ] Lancer `INSTALL_AI=1 ./setup.sh`. Sans `INSTALL_AI=1`, seuls le POC léger et ses tests sont installés.
- [ ] Lancer `uvicorn econstat.main:app --reload` puis `python -m econstat.ui.app`.
- [ ] Ouvrir `http://localhost:8000/docs` et `http://localhost:7860`.

Comptes démo : `agent.demo / DemoAgent2026!` et
`responsable.demo / DemoResp2026!`. Changez-les hors démonstration locale.

## Alternative Windows natif

Installer Python 3.11.9 x64, FFmpeg, CUDA compatible avec PyTorch 2.4.1 et Docker Desktop,
puis exécuter `$env:INSTALL_AI=1; .\setup.ps1`. Si `pyannote.audio` échoue à cause d'une DLL
audio, installer FFmpeg via `winget install Gyan.FFmpeg`, rouvrir le terminal et vérifier
`ffmpeg -version`. Si les wheels CUDA ne correspondent pas, installer les wheels PyTorch 2.4.1
depuis l'index CUDA officiel correspondant, puis relancer sans réinstaller Python système.
WSL2 reste le chemin validé par défaut, car CTranslate2, pyannote et les pilotes audio y sont plus
prévisibles.

### Mode sans droits administrateur

Lorsque WSL2, Hyper-V et le moteur Linux Docker ne peuvent pas être activés, lancer
`run-local.ps1`. Ce profil remplace PostgreSQL par `econstat-local.db` (SQLite), démarre le mock
E-consta, l'API et Gradio comme processus utilisateur, et conserve Ollama en CPU. Il couvre le
parcours de démonstration et les garde-fous humains, mais ne constitue pas une validation de la
persistance PostgreSQL cible. Les URLs sont `http://127.0.0.1:7861`, `/docs` sur le port 8080 et
le mock sur le port 8081.

## Modèles, GPU et reproductibilité

Les seuils sont dans `.env`, jamais dans le code métier : moins de 8 Gio ou aucun GPU →
`qwen3:4b` CPU/dégradé ; 8–15,99 Gio → `qwen3:8b` ; 16–19,99 Gio → `qwen3:14b` ;
20 Gio et plus → `qwen3.6:27b`. `nvidia-smi` est interrogé au lancement de l'extraction.

Le modèle Whisper et sa révision HF sont épinglés dans `.env.example`. Le modèle pyannote est gated ;
sa révision doit être remplacée par le SHA visible au moment où l'accès est accordé avant une
évaluation officielle. Les tags Ollama, la température `0.0` et la seed `42` sont centralisés.
Chaque extraction conserve modèle, device, VRAM, température et seed dans `claims.model_trace`.
`requirements.lock` fige l'environnement léger ; `pyproject.toml` fige aussi le profil IA.

Télécharger les tags Ollama avant la démo selon la VRAM : `ollama pull qwen3:8b` par exemple.
Le téléchargement automatique de modèles est désactivé par défaut (`ALLOW_MODEL_DOWNLOADS=false`).

## Parcours de démonstration

1. Obtenir un JWT via `/api/auth/token`, charger un audio avec `POST /api/calls`.
2. Transcrire/diariser (service GPU) ou utiliser un transcript de démonstration.
3. Appeler `/api/calls/{id}/extract`, examiner les preuves, confiances et questions manquantes.
4. Corriger avec `PUT /api/claims/{id}`, puis valider via `/validate`.
5. Générer le PDF et appeler `/send`. Un `/send` prématuré retourne HTTP 409.
6. Consulter `/api/dashboard` avec le rôle responsable.

Le score par champ combine 45 % confiance extracteur, 35 % confiance Whisper normalisée et
20 % complétude. Ce choix transparent est adapté au POC, pas calibré pour une décision automatisée.

## Limites et suite

Ce dépôt n'intègre ni téléphonie réelle, ni vraie API E-consta, ni sécurité enterprise. La
labellisation agent/assuré suppose que le locuteur prononçant la formule d'accueil est l'agent.
Un audio mono-locuteur reste `AGENT` ou `INCONNU` et doit être vérifié. Avant production : étude
RGPD/localisation, chiffrement, rétention, tests de charge, calibration des confiances et revue
de sécurité. Si les mesures locales montrent un écart lié aux accents ivoiriens ou au vocabulaire,
un LoRA Whisper sur corpus local annoté pourra être étudié ; aucun entraînement n'est inclus ici.
