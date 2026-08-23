# Architecture

## Objectif

Fournir un POC Windows CPU-first démontrable et reprenable, avec traitement différé, état persistant,
fallbacks explicites et validation humaine obligatoire.

## Vue des composants

```text
Utilisateur
    |
    v
Gradio UI ---- polling HTTP ----> FastAPI
                                   |
                                   v
                           SQLite / PostgreSQL
                         /    |       |       \
                     Call   Job     Claim   AuditLog
                              ^
                              |
                       Worker Python unique
                              |
          +-------------------+-------------------+
          |          |             |             |
       ffprobe   Faster-Whisper  pyannote     Ollama/Qwen
       validation    CPU/int8     optionnel      optionnel
```

## Responsabilités

- **Gradio** : connexion, soumission, polling, revue, correction, validation et pilotage.
- **FastAPI** : contrats HTTP, authentification, contrôle de propriété et garde-fous métier.
- **Base SQL** : source de vérité des utilisateurs, appels, jobs, déclarations et audits.
- **Worker** : prend un job à la fois, sauvegarde chaque checkpoint et rend les erreurs visibles.
- **Services IA** : chargement paresseux, CPU par défaut, modèles configurés localement.
- **Intégrations** : FFmpeg/ffprobe, Ollama, Hugging Face et E-consta derrière des adaptateurs.

## Flux de traitement

1. L’API stocke l’audio de façon sûre et crée `Call` et `ProcessingJob(queued)` en transaction.
2. Le worker verrouille un job, inspecte le média avec ffprobe et calcule son SHA-256.
3. Il transcrit, persiste immédiatement le transcript et met à jour la progression.
4. Il tente la diarisation. Un échec attendu produit le fallback `INCONNU` et une trace visible.
5. Il applique règles et lexique, puis sollicite facultativement Ollama. Une valeur LLM sans preuve
   littérale vérifiable est rejetée.
6. Le job passe à `ready_for_review`. L’agent corrige et valide.
7. L’API et `EConstaClient` interdisent indépendamment PDF/envoi avant validation.

## Décisions structurantes

### CPU-first

Le poste cible ne garantit aucun GPU NVIDIA. `device=cpu` et `compute_type=int8` sont des contraintes
d’architecture. Les profils `fast` et `quality` permettront de mesurer le compromis précision/latence.

### Worker SQL

Le traitement audio ne doit pas bloquer une requête HTTP. Une table de jobs et un processus Python
séparé suffisent pour un poste et offrent progression, audit, reprise et persistance.

### Pas de Kafka, Redis ou Celery

Ils augmenteraient installation et exploitation sans valeur mesurée pour ce POC mono-poste. Le
service de jobs pourra changer d’implémentation si volume ou distribution le justifient.

### Pas de microservices

Les composants partagent un domaine, une base et un cycle de livraison. Le paquet `econstat` garde
des frontières testables avec moins de déploiements et de défaillances réseau.

## Cohérence et reprise

- Un seul job traité simultanément par défaut.
- Verrou et timestamps persistés.
- Jobs actifs trop anciens détectés via `JOB_STALE_MINUTES`.
- Résultats intermédiaires sauvegardés après chaque étape.
- Une reprise vérifie le checkpoint avant de recalculer.
- Transitions et erreurs auditées sans secrets ni contenu audio dans les logs.

## Sécurité et données

- Contrôle de propriété centralisé pour appels et déclarations.
- Noms serveur générés par UUID.
- Limites de taille, MIME, conteneur, durée et hash avant traitement.
- Aucun secret, audio réel, modèle lourd, base locale ou PDF client dans Git.
- Données de test synthétiques ou anonymisées.

## Trajectoire de montée en charge

1. Mesurer latence, mémoire, taux d’erreur et volume réel.
2. Optimiser modèles et checkpoints CPU.
3. Passer à PostgreSQL si la concurrence réelle le demande.
4. Autoriser plusieurs workers avec verrouillage SQL atomique.
5. Introduire une file dédiée uniquement après mesure des limites SQL.
6. Séparer un service uniquement si son exploitation indépendante apporte une valeur démontrée.

## Statut

Ce document décrit la cible. Une capacité n’est disponible qu’après sa phase, ses tests et ses
commandes de reproduction. Des tests unitaires réussis ne valent pas validation production.
