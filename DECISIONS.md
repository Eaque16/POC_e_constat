# Décisions d’architecture

## ADR-001 — CPU comme cible obligatoire

**Contexte** : aucun GPU NVIDIA n’est garanti.  
**Options** : CUDA obligatoire ; accélération spécifique ; CPU portable.  
**Choix** : CPU, Faster-Whisper `int8`, profils configurables.  
**Pourquoi** : fonctionne sur le matériel réellement disponible.  
**Conséquences** : traitement différé, benchmark obligatoire.  
**Réversibilité** : device et compute type restent configurables.

## ADR-002 — Monolithe modulaire

**Contexte** : POC mono-poste, petite équipe, domaine unique.  
**Options** : microservices ; monolithe non structuré ; monolithe modulaire.  
**Choix** : package `econstat` organisé par responsabilités.  
**Pourquoi** : frontières claires sans exploitation distribuée.  
**Conséquences** : un dépôt et une version applicative.  
**Réversibilité** : les adaptateurs pourront devenir distants.

## ADR-003 — Worker séparé et file SQL

**Contexte** : les calculs CPU ne doivent pas occuper les requêtes HTTP.  
**Options** : synchrone ; Redis/Celery ; table SQL et worker Python.  
**Choix** : `processing_jobs` et worker indépendant.  
**Pourquoi** : progression et reprise sans service supplémentaire.  
**Conséquences** : verrouillage et jobs stale à gérer.  
**Réversibilité** : l’API dépendra d’un service de jobs abstrait.

## ADR-004 — SQLite local, PostgreSQL futur

**Contexte** : fonctionnement sans administrateur ni Docker.  
**Options** : PostgreSQL obligatoire ; JSON ; SQLite.  
**Choix** : SQLite par défaut, PostgreSQL comme cible.  
**Pourquoi** : installation nulle et transactions suffisantes pour un worker.  
**Conséquences** : concurrence PostgreSQL à valider séparément.  
**Réversibilité** : SQLAlchemy et Alembic limitent le couplage.

## ADR-005 — IA optionnelle avec règles prioritaires

**Contexte** : Ollama et pyannote peuvent être absents.  
**Options** : panne globale ; sorties fictives ; fallbacks explicites.  
**Choix** : règles d’abord, Ollama facultatif, diarisation `INCONNU`.  
**Pourquoi** : parcours utilisable sans masquer les capacités absentes.  
**Conséquences** : qualité variable, correction humaine indispensable.  
**Réversibilité** : chaque service IA reste remplaçable.

## ADR-006 — Aucun téléchargement silencieux

**Contexte** : modèles lourds, licences et réseau non fiable.  
**Options** : automatique ; modèles dans Git ; script explicite.  
**Choix** : `ALLOW_MODEL_DOWNLOADS=false` et script dédié.  
**Pourquoi** : reproductibilité et respect des licences.  
**Conséquences** : installation IA explicite.  
**Réversibilité** : un déploiement administré pourra précharger les modèles.

## ADR-007 — Double validation humaine

**Contexte** : aucune déclaration ne doit partir sur la seule décision de l’IA.  
**Options** : UI ; API ; API et client externe.  
**Choix** : garde-fou API et `EConstaClient`.  
**Pourquoi** : défense en profondeur.  
**Conséquences** : redondance volontaire à tester.  
**Réversibilité** : décision métier non destinée à être retirée.

## ADR-008 — Registre ML simple

**Contexte** : traçabilité nécessaire sans plateforme MLOps.  
**Options** : aucune trace ; MLflow ; JSON/CSV append-only.  
**Choix** : registre simple dans `experiments/`.  
**Pourquoi** : suffisant pour commits, modèles, données, paramètres et métriques.  
**Conséquences** : schéma et discipline d’écriture nécessaires.  
**Réversibilité** : import possible dans un outil futur.

## ADR-009 — Autorisation par propriété relue en base

**Contexte** : connaître l’UUID d’une déclaration ne doit pas permettre d’agir dessus.

**Options** : confiance dans le rôle JWT ; contrôles dispersés ; helpers centralisés avec rôle DB.

**Choix** : helpers de propriété communs et rôle relu depuis `User`.

**Pourquoi** : évite les oublis de route et rend un rôle JWT falsifié sans effet.

**Conséquences** : les routes sensibles nécessitent une session et l’utilisateur courant.

**Réversibilité** : une future politique ABAC pourra remplacer les helpers derrière le même contrat.

## ADR-010 — Validation audio avant persistance métier

**Contexte** : extension et MIME déclarés ne prouvent ni le conteneur réel ni la présence d’audio.

**Options** : faire confiance au navigateur ; valider dans le worker ; valider avant de créer l’appel.

**Choix** : flux borné vers un fichier temporaire, inspection `ffprobe`, hash, puis renommage UUID.

**Pourquoi** : aucun `Call` ne référence un média invalide et les noms clients ne deviennent pas des chemins.

**Conséquences** : FFmpeg/ffprobe est un prérequis explicite de l’ingestion et son absence renvoie 503.

**Réversibilité** : l’inspecteur peut être remplacé derrière `audio_validation` sans changer le contrat API.

## ADR-011 — Checkpoint porté par la prochaine étape à exécuter

**Contexte** : un arrêt peut survenir entre transcription, diarisation et extraction.

**Options** : recommencer tout le pipeline ; colonnes par étape ; `current_step` transactionnel.

**Choix** : résultat d’une étape et passage à la suivante sont commités ensemble ; `current_step`
désigne toujours la prochaine étape à exécuter.

**Pourquoi** : reprise simple et vérifiable avec le schéma existant, sans infrastructure supplémentaire.

**Conséquences** : chaque étape doit rester idempotente et utiliser la même session transactionnelle.

**Réversibilité** : des checkpoints plus détaillés pourront être ajoutés si les mesures le justifient.

## ADR-012 — Confiance Whisper comme indicateur non calibré

**Contexte** : Faster-Whisper expose un log-score, pas une probabilité métier fiable.

**Options** : masquer le score ; l’afficher comme probabilité ; publier une transformation expliquée.

**Choix** : `exp(avg_logprob)` borné entre 0 et 1, conservé avec le score brut et sa méthode.

**Pourquoi** : permet une lecture comparative sans présenter le score comme une certitude.

**Conséquences** : l’interface et la documentation doivent toujours afficher cette limite.

**Réversibilité** : une calibration sur corpus annoté pourra remplacer la transformation après mesure.

## ADR-013 — Diarisation non bloquante et rôles heuristiques

**Contexte** : pyannote est gated et ses sorties identifient des locuteurs, pas leurs rôles métier.

**Options** : rendre pyannote obligatoire ; masquer l’échec ; fallback explicite et correction humaine.

**Choix** : résultat structuré, fallback `INCONNU`, heuristique d’accueil tracée et correction par segment.

**Pourquoi** : le dossier reste traitable sans transformer une hypothèse en identité certaine.

**Conséquences** : la qualité de séparation reste partielle tant qu’elle n’est pas mesurée sur corpus.

**Réversibilité** : le moteur et l’heuristique peuvent évoluer derrière leurs contrats actuels.
