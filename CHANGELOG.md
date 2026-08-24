# Changelog

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
  responsable, garde-fous PDF/envoi, 30 tests, Ruff et `pip check`.
- Phase 4 : ingestion audio bornée, contrôle extension/MIME, inspection réelle avec `ffprobe`, durée,
  stockage UUID, SHA-256, nettoyage transactionnel et audit minimal des acceptations/rejets.
- Validation phase 4 : fichiers WAV valides, faux conteneurs, incohérence extension/conteneur,
  fichier vide, limites de taille/durée et absence de `ffprobe`, 39 tests, Ruff et `pip check`.

> Les entrées correspondent aux phases livrées sur la branche `rebuild/cpu-first` avec un commit
> logique par phase.

## 0.1.0 — 2026-08-20

- Chantier 1 : monolithe modulaire, configuration typée, PostgreSQL, Alembic, JWT et rôles.
- Chantier 2 : sélection VRAM, Whisper, pyannote, alignement, règles + Qwen3, preuves anti-hallucination,
  lexique ivoirien, questions manquantes, scores et traçabilité.
- Chantier 3 : API agent, historique et interface Gradio avec rejeu progressif.
- Chantier 4 : PDF validé, client E-consta à double garde-fou, serveur mock et dashboard responsable.
- Qualité : tests unitaires des cas nominaux et limites, scripts WSL2/Windows et protocole benchmark.
