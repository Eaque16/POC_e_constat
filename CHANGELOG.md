# Changelog

## Phase 11 — Dashboard responsable

- Contrat typé couvrant appels, dossiers, états, erreurs, latence et corrections.
- Distinction explicite entre dossiers à valider, validés et envoyés.
- Temps moyen basé uniquement sur les traitements arrivés à la revue humaine.
- Distribution des types d’accident et des codes d’erreur sans données individuelles.
- Interface Gradio avec KPI, distributions et alertes réservées au responsable.
- Tests des métriques nominales, de la base vide et du contrôle de rôle.

## Phase 10 — Export JSON et mock E-consta

- Export JSON versionné avec double garde-fou de validation humaine.
- Client E-consta avec timeout configurable, corrélation et erreurs explicites.
- Envoi idempotent et refus des collisions de clé avec un contenu différent.
- Audit des tentatives, réussites, répétitions et échecs sans données métier complètes.
- Tests d’intégration du parcours validation, export, envoi et répétition.

## Ajustement produit — export JSON

- Remplacement du document PDF par un export JSON UTF-8 versionné.
- Double garde-fou de validation humaine dans l’API et le service d’export.
- Ajout de la référence dossier, de la date, du validateur et d’un avertissement explicite.
- Suppression de ReportLab et des routes, composants et tests dédiés au PDF.

## Phase 9 — Interface agent et revue humaine

- Authentification JWT dans Gradio sans mode de contournement local.
- Upload fichier/microphone, profils de traitement et suivi explicite des jobs.
- Revue avec transcription, locuteurs, preuves, confiances et champs manquants.
- Distinction entre proposition IA, correction courante et valeur validée.
- Historique agent, dashboard responsable et actions export JSON/envoi protégées.

## 0.2.0 — reprise CPU-first en cours

- Phase 0 : cadrage de l’architecture Windows CPU-first, décisions et registre des risques.
- Phase 1 : environnement `.venv` obligatoire, configuration locale, installation sans Docker,
  diagnostic Windows et script worker préparatoire.
- Validation : 13 tests, Ruff et `pip check` réussis sur Python 3.11.9.
- Limite explicite : l’IA reste partielle sans accès pyannote ; le worker SQL arrive en phase 5.
- Phase 2 : schéma canonique `User`, `Call`, `Claim`, `ProcessingJob`, `AuditLog`, migration Alembic
  `0002`, adoption prudente des bases historiques et seed idempotent.
- Validation phase 2 : migration aller/retour, copie réelle avec conservation des données, CRUD,
  contraintes de progression, Alembic check, 17 tests, Ruff et `pip check`.
- Phase 3 : endpoint d’authentification isolé, audit de connexion, rôle relu en base, helpers de
  propriété centralisés et protection de toutes les routes appel/déclaration.
- Validation phase 3 : connexion, jetons invalides, accès croisés, rôle JWT falsifié, périmètre
  responsable, garde-fous export/envoi, 30 tests, Ruff et `pip check`.
- Phase 4 : ingestion audio bornée, contrôle extension/MIME, inspection réelle avec `ffprobe`, durée,
  stockage UUID, SHA-256, nettoyage transactionnel et audit minimal des acceptations/rejets.
- Validation phase 4 : fichiers WAV valides, faux conteneurs, incohérence extension/conteneur,
  fichier vide, limites de taille/durée et absence de `ffprobe`, 39 tests, Ruff et `pip check`.
- Phase 5 : création atomique `Call` + `ProcessingJob`, réservation SQL conditionnelle, progression,
  checkpoints, échec, retry borné, reprise stale, API de suivi propriétaire et worker indépendant.
- Validation phase 5 : réservation exclusive, transitions monotones, reprise au checkpoint, erreur
  persistée, fallback diarisation et accès croisé ; 45 tests, pipeline IA simulé sans téléchargement.
- Phase 6 : profils Faster-Whisper locaux CPU/int8, cache par processus, segments horodatés,
  confiance ASR expliquée, trace de latence, diagnostic de complétude et scripts explicites de modèles.
- Validation réelle phase 6 : `fast` et `quality` exécutés hors réseau sur audio synthétique ; temps
  exploratoires documentés dans `BENCHMARK.md`, 52 tests, sans revendication de précision métier.
- Phase 7 : pyannote optionnel avec cache et API 3.3 compatible, fallback structuré `INCONNU`,
  attribution heuristique tracée et correction humaine des rôles avec contrôle propriétaire.
- Limite phase 7 : vraie diarisation non exécutée, car `HF_TOKEN` et configuration locale chargeable
  sont absents ; fallback local validé sans panne globale, avec 57 tests réussis.
- Phase 8 : règles avec preuves, lexique CI enrichi, schéma métier étendu, client Ollama JSON strict,
  validation littérale, fusion prioritaire, confiances, manques, questions et persistance des preuves.
- Limite phase 8 : Ollama réel a expiré puis produit une sortie non JSON ; les deux essais ont été
  rejetés sans perte des résultats déterministes ; 62 tests réussissent.

> Les entrées correspondent aux phases livrées sur la branche `rebuild/cpu-first` avec un commit
> logique par phase.

## 0.1.0 — 2026-08-20

- Chantier 1 : monolithe modulaire, configuration typée, PostgreSQL, Alembic, JWT et rôles.
- Chantier 2 : sélection VRAM, Whisper, pyannote, alignement, règles + Qwen3, preuves anti-hallucination,
  lexique ivoirien, questions manquantes, scores et traçabilité.
- Chantier 3 : API agent, historique et interface Gradio avec rejeu progressif.
- Chantier 4 : export validé, client E-consta à double garde-fou, serveur mock et dashboard responsable.
- Qualité : tests unitaires des cas nominaux et limites, scripts WSL2/Windows et protocole benchmark.
