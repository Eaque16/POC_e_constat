# Benchmark POC

## Protocole

Jeu cible : 20 appels synthétiques ou consentis, anonymisés, dont 5 avec bruit, 5 avec accents
ivoiriens marqués, 3 avec hésitations/reformulations, 4 avec champs absents et 3 mono-locuteur.
Une transcription et une fiche de vérité terrain doivent être relues par deux annotateurs.

- STT : WER par `jiwer`, global et par sous-groupe.
- Extraction : précision, rappel et F1 exacts par champ ; tolérance documentée pour date/heure/plaque.
- Diarisation : DER et exactitude du rôle AGENT/ASSURÉ.
- Reproductibilité : seed 42, température 0, versions et révisions consignées avec chaque run.

## Résultats

| Variante | WER global | WER accent CI | F1 extraction | DER | Date |
|---|---:|---:|---:|---:|---|
| large-v3-french | À mesurer sur le PC cible | À mesurer | À mesurer | À mesurer | — |
| distil-dec16 | À mesurer sur le PC cible | À mesurer | À mesurer | À mesurer | — |

Le dépôt ne contient pas d'audios réels et aucune mesure n'a été inventée. Compléter ce tableau
après exécution sur le GPU cible constitue le critère d'acceptation de la phase d'évaluation.
Seuils POC proposés : WER ≤ 20 %, F1 champs critiques ≥ 0,85, aucun fait halluciné accepté.
