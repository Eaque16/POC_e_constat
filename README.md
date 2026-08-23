# E-Constat IA

POC local Windows d’assistance à la déclaration de sinistre automobile. La cible est un PC CPU,
sans dépendance obligatoire à CUDA, Docker, WSL2, Kafka, Redis ou Celery.

> Principe non négociable : l’IA propose. L’agent vérifie, corrige et valide. Aucun PDF officiel
> ni envoi E-consta n’est autorisé avant une validation humaine explicite.

## État de la reprise

La branche `rebuild/cpu-first` reconstruit progressivement l’ancien POC sans le supprimer avant
remplacement vérifié. Les phases 0 et 1 couvrent le cadrage, la reproductibilité Windows et le
diagnostic. Les fonctions métier historiques ne sont considérées livrées dans la nouvelle
architecture qu’après leur phase dédiée.

- cœur Python local et 11 tests historiques opérationnels ;
- CPU obligatoire, aucun GPU NVIDIA détecté sur la machine de construction ;
- FFmpeg, ffprobe, Ollama et `qwen3:4b` disponibles localement ;
- pyannote reste conditionné par une licence acceptée et un `HF_TOKEN` ;
- Docker est hors du chemin critique ;
- aucun benchmark métier n’a encore été exécuté ;
- aucune performance et aucun résultat IA ne sont revendiqués sans mesure.

## Architecture cible

```text
Gradio -> FastAPI -> SQLite/PostgreSQL <- Worker Python
                         |
             Call + ProcessingJob + Claim + AuditLog
```

Le worker séparé réalisera le traitement différé. La table SQL `processing_jobs` remplacera une
infrastructure Redis/Celery inutile au stade POC. Voir `ARCHITECTURE.md`.

## Prérequis Windows

- Windows 10 ou 11 x64 ;
- Python 3.11.x ;
- PowerShell ;
- FFmpeg et ffprobe pour l’ingestion audio ;
- Ollama facultatif pour le complément LLM ;
- compte Hugging Face et licence pyannote facultatifs pour la diarisation de qualité.

WSL2 et Docker ne sont pas requis.

## Installation

```powershell
.\setup.ps1
```

Le script crée ou réutilise `.venv`, installe le cœur et les outils de développement, puis demande
explicitement si la pile IA doit être installée. Aucun modèle lourd n’est téléchargé silencieusement.

Toutes les commandes utilisent l’interpréteur du projet :

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts\diagnose.py
```

## Configuration

Copier `.env.example` vers `.env`, puis remplacer au minimum `JWT_SECRET` par une valeur locale
robuste. `.env` est ignoré par Git et les téléchargements de modèles sont désactivés par défaut.

```powershell
Copy-Item .env.example .env
```

Ne jamais versionner de secret, token, audio client, base locale, modèle lourd ou PDF client.

## Démarrage prévu

```powershell
.\run-local.ps1
.\run-worker.ps1
```

`run-local.ps1` initialise SQLite et lance le mock E-consta, l’API et l’interface. Le worker est
séparé pour que l’interface reste disponible pendant les calculs CPU. Tant que la phase Jobs n’est
pas livrée, `run-worker.ps1` signale clairement ce prérequis au lieu de simuler un fonctionnement.

## Parcours produit cible

1. Connexion de l’agent.
2. Upload audio validé et stocké sous un nom UUID.
3. Création d’un appel et d’un job SQL.
4. Traitement différé par le worker.
5. Transcription horodatée CPU.
6. Diarisation pyannote ou fallback explicite `INCONNU`.
7. Extraction déterministe, puis complément LLM facultatif avec preuve littérale.
8. Revue, correction et validation humaine explicite.
9. PDF et envoi vers le mock E-consta.
10. Audit et dashboard responsable.

## Documentation de pilotage

- `ARCHITECTURE.md` : composants, flux et trajectoire d’industrialisation ;
- `DECISIONS.md` : décisions réversibles au format mini-ADR ;
- `RISKS.md` : registre des risques ;
- `BENCHMARK.md` : protocole et résultats mesurés uniquement ;
- `CHANGELOG.md` : historique fonctionnel.

## Limites actuelles

Le dépôt est un POC, pas un produit de production. Il ne dispose pas encore d’un corpus représentatif
annoté, d’une vraie API E-consta, d’une téléphonie réelle, d’une revue RGPD, d’un audit de sécurité,
de tests de charge ou de mesures de précision sur les accents ivoiriens. Le succès des tests unitaires
ne prouve pas une aptitude à la production.
