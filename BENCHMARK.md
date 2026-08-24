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

## Résultats métier à mesurer

| Variante | WER global | WER accent CI | F1 extraction | DER | Date |
|---|---:|---:|---:|---:|---|
| large-v3-french | À mesurer sur le PC cible | À mesurer | À mesurer | À mesurer | — |
| distil-dec16 | À mesurer sur le PC cible | À mesurer | À mesurer | À mesurer | — |

Le dépôt ne contient pas d'audios réels et aucune mesure n'a été inventée. Compléter ce tableau
après exécution sur le CPU cible constitue le critère d'acceptation de la phase d'évaluation.
Seuils POC proposés : WER ≤ 20 %, F1 champs critiques ≥ 0,85, aucun fait halluciné accepté.
