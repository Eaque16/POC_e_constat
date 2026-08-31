# Benchmark POC

## Protocole

Jeu cible : 20 appels synthétiques ou consentis, anonymisés, dont 5 avec bruit, 5 avec accents
ivoiriens marqués, 3 avec hésitations/reformulations, 4 avec champs absents et 3 mono-locuteur.
Une transcription et une fiche de vérité terrain doivent être relues par deux annotateurs.

- STT : WER par `jiwer`, global et par sous-groupe.
- Extraction : précision, rappel et F1 exacts par champ ; tolérance documentée pour date/heure/plaque.
- Diarisation : DER et exactitude du rôle AGENT/ASSURÉ.
- Reproductibilité : seed 42, température 0, versions et révisions consignées avec chaque run.

## Mesures exploratoires locales — 2026-08-24

Machine : Intel Core i5-10210U, 7,8 Go de RAM, Windows, CPU/int8. Chaque commande a utilisé un
processus neuf : les temps incluent donc le chargement du modèle. Ces essais vérifient l’exécution,
pas la précision métier.

| Profil | Audio synthétique | Durée audio | Temps | Facteur temps réel | Résultat |
|---|---|---:|---:|---:|---|
| fast, beam 1 | silence | 1,00 s | 25,934 s | 25,934 | aucun segment inventé |
| quality, beam 5 | silence | 1,00 s | 145,589 s | 145,589 | aucun segment inventé |
| fast, beam 1 | voix FFmpeg flite | 3,08 s | 29,743 s | 9,657 | 1 segment, confiance 0,3177 |

La voix `flite` disponible est anglophone et prononce mal le français ; sa transcription erronée ne
permet pas d’estimer le WER français. Elle confirme seulement segments, horodatage et score. Les
mesures montrent que `quality` doit rester différé sur cette machine.

### Extraction Ollama exploratoire

Sur le transcript synthétique « assureur SUNU, accident au Plateau, aucun blessé », les règles ont
extrait quatre champs avec preuves. `qwen3:4b` a d’abord atteint le timeout de 120 s avec le schéma
complet, puis a répondu avec un contenu non JSON après compactage du prompt. Les deux sorties LLM
ont été rejetées et les résultats déterministes conservés. Aucun chiffre de qualité LLM n’en est déduit.

## Résultats métier à mesurer

| Variante | WER global | WER accent CI | F1 extraction | DER | Date |
|---|---:|---:|---:|---:|---|
| large-v3-french | À mesurer sur le PC cible | À mesurer | À mesurer | À mesurer | — |
| distil-dec16 | À mesurer sur le PC cible | À mesurer | À mesurer | À mesurer | — |

Le dépôt ne contient pas d'audios réels et aucune mesure n'a été inventée. Compléter ce tableau
après exécution sur le CPU cible constitue le critère d'acceptation de la phase d'évaluation.
Seuils POC proposés : WER ≤ 20 %, F1 champs critiques ≥ 0,85, aucun fait halluciné accepté.

## Commande reproductible

Baseline des règles, hors réseau et sans modèle :

```powershell
.\.venv\Scripts\python.exe scripts\benchmark.py `
  --manifest data\demo\benchmark_manifest.json `
  --profile fast
```

L’option `--run-asr` n’est autorisée que si chaque cas possède `audio_path` et
`reference_transcript`, et si le modèle configuré est déjà présent localement. Le script ne change
pas `ALLOW_MODEL_DOWNLOADS`. Chaque résultat enregistre le commit, l’état propre ou sale de Git,
les hashes du lock et du manifeste, Python, la machine, le profil, la seed et les paramètres.

Le manifeste versionné `synthetic-text-v1` mesure uniquement la baseline d’extraction sur cinq
transcriptions synthétiques. Il ne permet pas de calculer le WER ou le DER : ces valeurs restent
explicitement `null`, avec un statut expliquant l’annotation absente.

## Baseline extraction déterministe — mesure du 2026-08-24

Expérience `598cb546-e436-465e-b9a7-b4fbadc30eac`, commit propre `eb38f11`, Python 3.11.9,
Windows CPU, cinq transcriptions synthétiques, LLM désactivé et aucun ASR exécuté.

| Mesure | Résultat |
|---|---:|
| Précision micro | 1,000000 |
| Rappel micro | 0,937500 |
| F1 micro | 0,967742 |
| F1 macro | 0,909091 |
| Taux de prédictions sans vérité terrain | 0,000000 |
| Cas nécessitant une correction | 0,200000 |
| Temps total extraction, 5 cas | 0,082957 s |
| Pic mémoire Python mesuré par `tracemalloc` | 0,138 Mo |

Échec observé : le numéro `0708091011` dicté entièrement en lettres n’est pas extrait. Le corpus est
minuscule et construit pour tester les règles ; ces scores ne permettent aucune conclusion sur des
appels réels, le bruit ou les accents. WER, facteur temps réel ASR et DER restent non mesurables faute
d'audio français annoté et de tours de parole de référence. Le détail traçable est conservé dans
`experiments/baseline-rules-synthetic-v1.json`.

## Benchmark ASR interactif même processus — 2026-08-30

Commande : `python scripts/benchmark_realtime_asr.py test-micro.wav --runs 5 --cpu-threads N`.
Machine : Intel Core i5-10210U, 8 processeurs logiques, CPU/int8, un worker. Audio synthétique de
11,818 s. Chaque variante charge une seule fois le modèle fast, effectue un warm-up, puis cinq tours.

| Threads | ASR médian | Tour médian | p95 tour | RTF médian |
|---:|---:|---:|---:|---:|
| défaut CTranslate2 (avant) | 2,589 s | 3,182 s | 3,851 s | 0,269 |
| 1 | 4,813 s | 5,651 s | 6,372 s | 0,478 |
| 2 | 2,708 s | 3,292 s | 3,697 s | 0,279 |
| 4 | 2,111 s | 2,860 s | 2,889 s | 0,242 |
| 8 (retenu sur cette machine) | 1,958 s | 2,510 s | 2,983 s | 0,212 |

Le cold start de référence était 26,121 s, dominé par 19,105 s d'imports et le premier warm-up.
Le préchauffage déplace ce coût avant le premier tour. Huit threads réduisent le tour warm médian
de 0,672 s (21,1 %) sur cette mesure, sans augmenter `num_workers`. Ce choix reste configurable et
doit être remesuré sur une autre machine. Les résultats ne mesurent pas la précision métier.

Le benchmark sépare import, modèle, décodage, VAD, ASR, parser, commit SQLite et total ; il n'appelle
ni réseau, ni Ollama, ni Pyannote.

Mesure finale après intégration du routeur et de la persistance instrumentée, même configuration
8 threads : cold start 18,313 s ; ASR warm médian 1,798 s ; commit SQLite médian 0,003 s ; tour warm
médian 2,173 s ; p95 2,299 s ; RTF médian 0,184. Les variations de cold start entre processus sont
importantes sur Windows ; la comparaison de latence interactive pertinente reste la série warm.

### Comparaison des modèles interactifs locaux

Le 2026-08-30, le même audio de 11,818 s a été rejoué cinq fois avec le modèle Small téléchargé
localement (`models/whisper-small`), CPU/int8, beam 1 et un seul processus. Cold start : 27,130 s ;
ASR warm médian : 8,707 s ; tour warm médian : 9,385 s ; p95 : 10,388 s ; RTF médian : 0,794.

| Mode UI | Modèle | Cold start | ASR warm médian | Tour warm médian | RTF médian |
|---|---|---:|---:|---:|---:|
| Rapide (défaut) | whisper-tiny | 18,313 s | 1,798 s | 2,173 s | 0,184 |
| Précision | whisper-small | 27,130 s | 8,707 s | 9,385 s | 0,794 |

Small a mieux restitué certains mots de l’échantillon, notamment « Cocody », mais cet unique audio
ne constitue pas une mesure de précision. Il est donc proposé à la demande pour une reprise
difficile ; Tiny demeure le défaut afin de préserver la fluidité conversationnelle.
