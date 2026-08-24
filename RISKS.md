# Registre des risques

| ID | Risque | Probabilité | Impact | Mitigation | Owner | Statut |
|---|---|---:|---:|---|---|---|
| R01 | Traitement CPU lent | Élevée | Élevé | int8, profils, worker, benchmark, aucune promesse temps réel | Lead IA | Ouvert |
| R02 | pyannote indisponible | Élevée | Moyen | fallback INCONNU, erreur visible, correction humaine | Lead IA | Ouvert |
| R03 | Téléchargement modèle impossible | Moyenne | Élevé | modèles locaux, téléchargement explicite, hash | Tech Lead | Ouvert |
| R04 | Hallucination du LLM | Moyenne | Élevé | règles, preuve littérale, score, validation humaine | Lead IA | Ouvert |
| R05 | Exposition de données sensibles | Moyenne | Critique | Git ignore, stockage local, rétention, données synthétiques | Manager | Ouvert |
| R06 | Contrôle d’accès insuffisant | Moyenne | Critique | propriété centralisée et tests inter-utilisateurs | Tech Lead | Maîtrisé phase 3 |
| R07 | Dépendances Python incompatibles | Moyenne | Élevé | Python 3.11, `.venv`, versions figées, pip check | Tech Lead | Maîtrisé phase 1 |
| R08 | API E-consta réelle absente | Élevée | Moyen | client encapsulé, mock, contrat documenté | Manager | Ouvert |
| R09 | SQLite limité en concurrence | Faible au POC | Moyen | worker unique, transactions courtes, PostgreSQL futur | Architecte | Accepté POC |
| R10 | Audio invalide ou malveillant | Moyenne | Élevé | taille, MIME, ffprobe, durée, UUID, SHA-256 | Tech Lead | Maîtrisé phase 4 |
| R11 | Job bloqué après incident | Moyenne | Élevé | checkpoints, timestamps, stale, reprise idempotente | Tech Lead | Maîtrisé phase 5 |
| R12 | Qualité insuffisante sur accents/bruit | Élevée | Élevé | corpus consenti, baseline, métriques par sous-groupe | Manager/IA | Non mesuré |
| R13 | Confusion Python système/projet | Moyenne | Moyen | commandes `.venv`, diagnostic, scripts stricts | Tech Lead | Maîtrisé phase 1 |
| R14 | Secret de développement hors local | Moyenne | Critique | variable obligatoire, `.env` ignoré, diagnostic sans valeur | Tech Lead | Ouvert |
| R15 | Migration d’une base historique inconnue | Faible | Critique | détection stricte, refus par défaut, sauvegarde, test sur copie | Tech Lead | Maîtrisé phase 2 |
| R16 | Bypass local conservé pour l’ancienne UI | Moyenne | Élevé | bind localhost, statut explicite, suppression prévue en phase 9 | Tech Lead | Accepté temporairement |
| R17 | Score ASR interprété comme certitude métier | Moyenne | Élevé | score brut, méthode affichée, libellé non calibré, validation humaine | Lead IA | Maîtrisé phase 6 |

## Règle de maintenance

Le registre est revu à chaque fin de phase. Un risque n’est fermé que si une preuve vérifiable existe.
Un fallback réduit l’impact mais ne rend pas automatiquement une capacité validée.
