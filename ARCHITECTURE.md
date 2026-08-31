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

1. L’API limite le flux, inspecte le média avec ffprobe, calcule son SHA-256, puis crée `Call`.
   La création atomique du `ProcessingJob(queued)` sera ajoutée en phase 5.
2. Le worker verrouille un job déjà validé et reprend à partir des checkpoints persistés.
3. Il transcrit, persiste immédiatement le transcript et met à jour la progression.
4. Il tente la diarisation. Un échec attendu produit le fallback `INCONNU` et une trace visible.
5. Il applique règles et lexique, puis sollicite facultativement Ollama. Une valeur LLM sans preuve
   littérale vérifiable est rejetée.
6. Le job passe à `ready_for_review`. L’agent corrige et valide.
7. L’API, le service d’export JSON et `EConstaClient` imposent la validation humaine.
8. `EConstaClient` utilise une clé d’idempotence stable par déclaration et un identifiant de
   corrélation par tentative ; le mock refuse une même clé associée à un contenu différent.
9. Le dashboard effectue des agrégations portables en Python pour le volume limité du POC. Une
   agrégation SQL dédiée restera une optimisation réversible si le volume augmente.

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
- Réservation par `UPDATE ... WHERE status=queued` : un seul worker gagne le job.
- Verrou et timestamps persistés ; polling simple réglé par `JOB_POLL_SECONDS`.
- Jobs actifs trop anciens détectés via `JOB_STALE_MINUTES`.
- Résultats intermédiaires sauvegardés après chaque étape.
- Résultat d’étape et transition suivante validés dans le même commit SQL.
- Une reprise conserve `current_step` et ne rejoue pas les étapes déjà validées.
- Transitions et erreurs auditées sans secrets ni contenu audio dans les logs.

Le worker se lance avec `python -m econstat.worker`; `--once` traite au plus un job pour le
diagnostic. Les uploads créent `Call` et `ProcessingJob` dans la même transaction. Les anciens
endpoints de calcul direct ne lancent plus de charge IA depuis une requête HTTP.

## Transcription

`Transcriber` sélectionne le chemin local et le beam depuis le profil du job. Son cache par processus
est indexé par chemin résolu, device et compute type. Il vérifie les fichiers CTranslate2 essentiels
avant import/chargement et ne transforme jamais un chemin manquant en téléchargement implicite.
Les segments et la trace opérationnelle sont persistés avant le checkpoint `diarizing`.

## Diarisation et attribution des rôles

`Diarizer` encapsule pyannote et retourne toujours un résultat structuré. Un token absent, un modèle
local incomplet, une licence inaccessible ou une erreur runtime produit un fallback audité plutôt
qu’une exception globale. Le cache du pipeline est séparé du cache Whisper.

`role_assignment` transforme les identifiants anonymes de locuteurs en rôles métier par une
heuristique explicitement tracée. Un segment sans chevauchement reste `INCONNU`. L’API de correction
humaine modifie les segments et reconstruit le transcript, avec contrôle propriétaire et audit.

## Extraction hybride

`extraction_rules` produit valeur, confiance initiale, preuve littérale et identifiant de règle.
`lexicon` fournit les lieux, assureurs et formulations ivoiriennes. `extraction_llm` ne complète que
via un contrat JSON strict et filtre les preuves avant la fusion. `extraction` valide chaque valeur
avec `ClaimData`, conserve la priorité des règles, calcule complétude/confiance et génère les questions.

Le worker persiste séparément données, confiances, preuves, manques, questions et trace du modèle.
Une indisponibilité Ollama ne modifie pas le statut du job et ne supprime aucun résultat déterministe.

## Conversation temps réel orientée slot

La boucle interactive utilise exclusivement le modèle `fast` CPU/int8, partagé dans le processus
Gradio et préchauffé optionnellement. À chaque tour, le moteur connaît `expected_slot` et route le
transcript vers un parser déterministe spécialisé. Ni Pyannote, ni le profil `quality`, ni Ollama ne
participent au chemin critique.

Les champs sensibles suivent `audio conservé -> transcript Whisper -> normalisation -> confiance
composite -> confirmation -> persistance`. Les enregistrements enrichis restent dans
`Claim.model_trace_json.field_records`, tandis que `Claim.data_json` conserve le contrat métier
historique. Cette stratégie évite une migration destructive.

Le géocodeur est un adaptateur facultatif avec timeout, restriction `ci` et cache. Un résultat du
gazetteer vérifie uniquement qu'un lieu est référencé ; il ne prouve jamais que l'accident s'y est
produit. Le GPS navigateur est la position actuelle, pas nécessairement celle du sinistre.

## Modèle persistant

- `User` porte l’identité et le rôle.
- `Call` appartient à un utilisateur et conserve chemin, hash, durée, transcription et segments.
- `ProcessingJob` porte profil, état, progression, verrou, tentatives, erreur et checkpoints temporels.
- `Claim` conserve données, confiances, preuves, manques, questions et validation humaine.
- `AuditLog` conserve les actions pertinentes avec des détails JSON minimaux.

La migration `0002` renomme les colonnes historiques vers ce vocabulaire canonique et maintient des
alias ORM temporaires pour l’ancien code. Le bootstrap refuse d’adopter une base non versionnée dont
le schéma n’est pas reconnu.

## Sécurité et données

- Contrôle de propriété centralisé pour appels et déclarations.
- Le rôle effectif est toujours relu en base ; une revendication de rôle JWT falsifiée est ignorée.
- Les accès croisés répondent 404 afin de ne pas révéler l’existence d’un dossier tiers.
- Le dashboard impose le rôle `responsable`.
- Noms serveur générés par UUID.
- Limites de taille, MIME, conteneur, durée et hash avant traitement.
- Écriture temporaire puis renommage atomique ; nettoyage sur rejet ou échec de transaction SQL.
- Audit minimal des acceptations et rejets, sans nom de fichier fourni par le client.
- Aucun secret, audio réel, modèle lourd, base locale ou export client dans Git.
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
