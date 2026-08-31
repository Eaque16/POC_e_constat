# Rapport technique — E-Constat IA

**Projet :** Assistant IA de pré-déclaration automobile  
**Organisation :** ASACI — Association des Sociétés d’Assurances de Côte d’Ivoire  
**Version analysée :** 0.1.0  
**Date :** 31 août 2026  
**Environnement cible :** Windows 10/11 ou WSL2, Python 3.11, fonctionnement CPU-first

---

## 1. Résumé exécutif

E-Constat IA est une preuve de concept destinée à assister la pré-déclaration d’un sinistre
automobile. L’utilisateur répond oralement aux questions de l’assistant. L’application transcrit
les réponses, extrait les informations métier, demande une confirmation pour les données sensibles,
constitue un dossier, puis soumet ce dossier au contrôle obligatoire d’un agent humain.

L’application adopte un **monolithe modulaire** : l’interface, l’API, le worker et les services IA
sont séparés logiquement mais restent dans un seul dépôt. Ce choix réduit la complexité de
déploiement d’un POC tout en conservant des frontières permettant une évolution future.

Les principes structurants sont :

- exécution locale et prioritairement sur CPU ;
- aucune décision métier définitive prise uniquement par l’IA ;
- validation humaine avant export ou transmission ;
- fonctionnement dégradé explicite quand une IA optionnelle est indisponible ;
- traçabilité des propositions, corrections et validations ;
- absence de téléchargement silencieux de modèles lourds.

---

## 2. Besoin fonctionnel couvert

Le parcours principal permet de :

1. démarrer une pré-déclaration guidée ;
2. enregistrer les réponses au microphone ;
3. transcrire automatiquement les réponses en français ;
4. corriger manuellement une mauvaise transcription ;
5. collecter l’identité, le téléphone, l’assureur, l’immatriculation, la date, l’heure, le lieu,
   les circonstances et les dommages ;
6. confirmer les informations sensibles ;
7. conserver les données et la trace de traitement ;
8. présenter un dossier à un agent humain ;
9. valider, exporter puis transmettre la déclaration ;
10. consulter un tableau de bord responsable.

Le système ne détermine pas la responsabilité juridique et ne calcule pas d’indemnisation.

---

## 3. Architecture générale

```text
Utilisateur
    |
    v
Interface Gradio (port 7860)
    |
    | HTTP / JSON
    v
API FastAPI (port 8000)
    |
    +-------------------------> SQLite local / PostgreSQL
    |                              |
    |                              +-- User
    |                              +-- Call
    |                              +-- ProcessingJob
    |                              +-- Claim
    |                              +-- AuditLog
    |
    v
Worker Python indépendant
    |
    +-- FFmpeg / ffprobe : validation audio
    +-- Faster-Whisper : transcription
    +-- pyannote.audio : diarisation optionnelle
    +-- règles + lexique ivoirien : extraction déterministe
    +-- Ollama / Qwen : complément LLM optionnel
    +-- client E-consta : export et envoi contrôlés
```

### 3.1 Interface utilisateur

L’interface est construite avec Gradio. Elle contient le parcours conversationnel, le microphone,
le choix de qualité de reconnaissance, la correction écrite, le dossier constitué en direct et la
rubrique de tableau de bord. Gradio a été retenu car il permet de construire rapidement une
interface Python interactive intégrant audio, tableaux, formulaires et événements asynchrones.

### 3.2 API métier

FastAPI expose les contrats HTTP pour l’authentification, les appels, les jobs, les déclarations,
les corrections, la validation, l’export, l’envoi et les statistiques. L’API demeure le garde-fou
des règles métier : contourner l’interface ne doit pas permettre d’envoyer un dossier non validé.

### 3.3 Worker de traitement

Le traitement lourd est exécuté dans un processus Python distinct. Une requête HTTP ne reste donc
pas bloquée pendant la transcription, la diarisation ou l’extraction. Les étapes et checkpoints
sont persistés afin de rendre la progression visible et de faciliter la reprise après incident.

### 3.4 Persistance

SQLite est utilisé par défaut pour la démonstration locale. PostgreSQL est déjà prévu via SQLAlchemy
et le pilote Psycopg. Alembic gère les migrations du schéma. La base constitue la source de vérité
des utilisateurs, appels, tâches, dossiers et audits.

### 3.5 Services d’intelligence artificielle

La transcription repose sur Faster-Whisper avec des modèles CTranslate2 locaux. Deux modes sont
disponibles : Tiny pour la rapidité et Small pour une meilleure précision. Le mode Small est
maintenant prioritaire dans le parcours conversationnel, car les captures observées montrent que
Tiny reconnaît mal certains noms, téléphones, assureurs, plaques et lieux ivoiriens.

L’extraction combine des parseurs déterministes, un lexique local et, facultativement, un modèle
Qwen exécuté par Ollama. Les règles déterministes restent prioritaires. Une proposition du LLM sans
preuve textuelle vérifiable est rejetée.

---

## 4. Organisation des fichiers

```text
e-constat-ia/
|-- econstat/
|   |-- main.py                 Point d’entrée FastAPI
|   |-- worker.py               Worker de traitement différé
|   |-- mock_server.py          Simulation du service E-consta
|   |-- config.py               Configuration et variables d’environnement
|   |-- database.py             Connexion SQLAlchemy
|   |-- models.py               Modèles persistants
|   |-- local_bootstrap.py      Initialisation locale et migrations
|   |-- api/
|   |   |-- routes.py           Routes HTTP métier
|   |   |-- auth.py             Authentification
|   |   |-- deps.py             Dépendances et autorisations
|   |   `-- jobs.py             Opérations liées aux jobs
|   |-- schemas/
|   |   |-- auth.py             Contrats d’authentification
|   |   |-- call.py             Contrats des appels
|   |   |-- claim.py            Contrats des déclarations
|   |   |-- job.py              Contrats de traitement
|   |   `-- dashboard.py        Contrat des statistiques
|   |-- services/
|   |   |-- transcription.py    Transcription différée
|   |   |-- realtime_transcription.py Transcription conversationnelle
|   |   |-- diarization.py      Séparation des locuteurs
|   |   |-- extraction.py       Fusion des extractions
|   |   |-- extraction_rules.py Règles déterministes
|   |   |-- extraction_llm.py   Complément Ollama/Qwen
|   |   |-- conversation.py     Dialogue orienté par champs
|   |   |-- confirmation.py     Confirmation des valeurs sensibles
|   |   |-- confidence.py       Scores de confiance
|   |   |-- lexicon.py          Lexique ivoirien
|   |   |-- geolocation.py      Positionnement et lieux
|   |   |-- dashboard.py        Agrégations du tableau de bord
|   |   |-- json_export.py      Export final contrôlé
|   |   |-- econsta.py          Client du système externe
|   |   `-- parsers/            Parseurs nom, téléphone, date, plaque, etc.
|   `-- ui/
|       |-- app.py              Interface Gradio
|       |-- api_client.py       Client HTTP de l’interface
|       |-- style.css           Identité visuelle et responsive design
|       `-- assets/             Logo ASACI
|-- alembic/                    Migrations de base de données
|-- data/                       Lexique et données synthétiques
|-- models/                     Modèles IA locaux, non versionnés
|-- generated/                  Exports produits après validation
|-- scripts/                    Installation, diagnostic et benchmarks
|-- tests/                      Tests unitaires et d’intégration
|-- experiments/                Registre simple des expériences IA
|-- pyproject.toml              Dépendances et configuration Python
|-- requirements.lock           Versions verrouillées
|-- Dockerfile                  Image de l’API
|-- docker-compose.yml          PostgreSQL et mock E-consta
|-- run-local.ps1 / .sh         Démarrage local
`-- run-worker.ps1              Démarrage du worker
```

---

## 5. Bibliothèques utilisées et justification

### 5.1 Bibliothèques principales

| Bibliothèque | Version | Rôle | Pourquoi ce choix |
|---|---:|---|---|
| Python | 3.11.x | Langage principal | Écosystème IA mature, typage moderne, compatibilité stable avec les bibliothèques retenues. |
| FastAPI | 0.112.2 | API HTTP | Contrats typés, validation automatique, documentation OpenAPI et bonnes performances. |
| Uvicorn | 0.30.6 | Serveur ASGI | Serveur léger et standard pour FastAPI. |
| Gradio | 4.44.0 | Interface web | Intégration rapide du microphone, du chat, des tableaux et des événements Python. |
| Pydantic | 2.8.2 | Validation des données | Empêche l’enregistrement de structures métier invalides et documente les contrats. |
| pydantic-settings | 2.4.0 | Configuration | Centralise les variables d’environnement et leurs types. |
| SQLAlchemy | 2.0.32 | Accès aux données | Abstraction compatible SQLite/PostgreSQL et transactions explicites. |
| Alembic | 1.13.2 | Migrations SQL | Évolution contrôlée et reproductible du schéma. |
| Psycopg | 3.2.1 | Pilote PostgreSQL | Prépare la montée en charge sans imposer PostgreSQL au POC local. |
| HTTPX | 0.27.2 | Client HTTP | Appels asynchrones/synchrones testables vers l’API et E-consta. |
| PyJWT | 2.9.0 | Jetons d’accès | Authentification stateless avec validation côté serveur. |
| Passlib | 1.7.4 | Gestion des mots de passe | API éprouvée pour le hachage et la vérification. |
| bcrypt | 4.0.1 | Algorithme de hachage | Protection des mots de passe sans stockage en clair. |
| python-multipart | 0.0.9 | Formulaires et fichiers | Nécessaire aux uploads audio et au formulaire OAuth2. |
| Jinja2 | 3.1.4 | Gabarits | Génération contrôlée de contenus textuels lorsque nécessaire. |
| NumPy | 1.26.4 | Calcul et audio | Manipulation efficace des tableaux audio pour les modèles IA. |
| dateparser | 1.4.2 | Dates naturelles | Comprend des formulations françaises comme « demain matin » ou « hier soir ». |
| RapidFuzz | 3.9.6 | Correspondance approximative | Aide à rapprocher une transcription imparfaite du lexique ivoirien. |

### 5.2 Bibliothèques IA optionnelles

| Bibliothèque | Version | Rôle | Pourquoi ce choix |
|---|---:|---|---|
| faster-whisper | 1.0.3 | Reconnaissance vocale | Implémentation Whisper optimisée, compatible CPU et quantification int8. |
| CTranslate2 | 4.4.0 | Moteur d’inférence | Réduit la consommation mémoire et améliore la vitesse sur CPU. |
| Hugging Face Hub | 0.24.6 | Gestion des modèles | Téléchargement explicite et versionnable des artefacts autorisés. |
| pyannote.audio | 3.3.2 | Diarisation | Sépare les locuteurs ; son indisponibilité ne bloque pas le dossier. |
| PyTorch | 2.4.1 | Calcul IA | Dépendance de pyannote et de plusieurs modèles audio. |
| TorchAudio | 2.4.1 | Traitement audio | Fonctions audio compatibles avec PyTorch. |
| Ollama + Qwen | externe | Extraction LLM locale | Évite l’envoi automatique de données sensibles vers un service cloud. |

### 5.3 Développement et qualité

| Outil | Version | Utilité |
|---|---:|---|
| pytest | 8.3.2 | Tests unitaires et d’intégration. |
| pytest-asyncio | 0.24.0 | Tests des comportements asynchrones. |
| coverage | 7.6.1 | Mesure de la couverture des tests. |
| Ruff | 0.6.3 | Analyse statique, imports et conventions Python. |
| Hatchling | 1.25.0 | Construction du paquet Python. |

### 5.4 Outils système

- **FFmpeg / ffprobe** : vérification réelle du conteneur, de la piste audio et de la durée ;
- **SQLite** : base locale sans serveur pour la démonstration ;
- **PostgreSQL 16** : cible lorsque la concurrence ou le volume augmente ;
- **Docker** : option de déploiement reproductible, mais non obligatoire ;
- **PowerShell / Bash** : scripts de lancement Windows et WSL2.

Les versions Python sont figées afin de limiter les incompatibilités et de rendre l’installation
reproductible.

---

## 6. Flux de traitement détaillé

### 6.1 Conversation en direct

1. L’assistant pose la question correspondant au champ attendu.
2. Le navigateur enregistre la réponse.
3. Faster-Whisper transcrit l’audio en français.
4. La question courante est ajoutée au contexte de transcription.
5. Le parser spécialisé analyse uniquement le type de donnée attendu.
6. Les données sensibles sont reformulées et confirmées.
7. Si la transcription est incorrecte, l’utilisateur peut saisir la correction exacte.
8. L’état et les preuves sont sauvegardés dans le dossier.

### 6.2 Traitement différé

1. L’API borne la taille de l’upload et inspecte l’audio avec ffprobe.
2. Le fichier reçoit un nom UUID et une empreinte SHA-256.
3. Un appel et un job SQL sont créés dans une transaction.
4. Le worker réserve le job.
5. Whisper produit les segments horodatés.
6. pyannote tente la diarisation ; en cas d’échec, le rôle reste `INCONNU`.
7. Les règles et le lexique extraient les informations.
8. Ollama peut compléter les champs manquants sous contrat JSON strict.
9. Le dossier passe en attente de revue.
10. Un agent corrige et valide avant export ou envoi.

---

## 7. Choix techniques et raisons

### CPU-first et quantification int8

Le matériel cible ne garantit pas de GPU NVIDIA. L’exécution CPU/int8 permet une démonstration sur
un poste standard. La conséquence est une latence supérieure, particulièrement avec Whisper Small
et pyannote. Le traitement différé et les deux profils de transcription permettent de maîtriser ce
compromis.

### Mode Whisper Small par défaut dans la conversation

Les essais visuels ont montré des transcriptions incohérentes avec Tiny sur des données essentielles.
Small est donc devenu le choix initial. Tiny reste disponible lorsque la rapidité prime. Le faisceau
de recherche est porté à 5 en précision, la langue est forcée en français et la question courante
sert de contexte. Une correction écrite garantit que l’utilisateur ne reste pas bloqué par l’ASR.

### Monolithe modulaire plutôt que microservices

Le domaine, la base et le cycle de livraison sont communs. Des microservices ajouteraient des
déploiements, des erreurs réseau et de l’observabilité sans valeur mesurée pour ce POC. Les modules
et adaptateurs actuels pourront néanmoins être externalisés si l’usage réel le justifie.

### File SQL plutôt que Redis/Celery

Une table `ProcessingJob` suffit pour un worker local, tout en fournissant état, progression,
tentatives et reprise. Redis ou Celery ne deviendront pertinents qu’après mesure d’un volume ou
d’une concurrence dépassant cette solution.

### SQLite par défaut

SQLite ne demande aucun service à administrer et convient à une démonstration mono-poste. Sa
concurrence en écriture est limitée ; PostgreSQL est prévu pour un déploiement multi-utilisateur.

### Règles avant LLM

Les téléphones, plaques, dates et réponses oui/non se prêtent à des parseurs déterministes, plus
rapides et explicables. Le LLM ne complète que les absences et doit citer une preuve présente dans
la transcription. Ce choix limite les hallucinations et conserve le service même sans Ollama.

### Validation humaine en profondeur

Une déclaration d’assurance contient des informations sensibles et peut avoir des conséquences
contractuelles. La validation est imposée dans l’API et dans le client d’envoi, et pas seulement
dans l’interface. L’IA propose ; l’humain corrige et valide.

### Modèles locaux et téléchargements explicites

Les modèles sont lourds, le réseau peut être absent et certaines licences exigent une acceptation.
Le système refuse donc de télécharger silencieusement un modèle. Les modèles et leurs empreintes
doivent être préparés explicitement.

---

## 8. Contraintes identifiées

### Contraintes matérielles

- fonctionnement sans GPU obligatoire ;
- mémoire et temps CPU limités ;
- Whisper Small plus précis mais sensiblement plus lent que Tiny ;
- pyannote peut être très coûteux sur CPU ;
- le réglage de huit threads n’est pas optimal sur toutes les machines.

### Contraintes de qualité IA

- précision non validée sur un corpus représentatif d’accents ivoiriens ;
- bruit, distance du microphone et débit de parole dégradent la transcription ;
- noms propres, communes, assureurs, téléphones et plaques sont particulièrement difficiles ;
- le score `exp(avg_logprob)` est un indicateur comparatif, pas une probabilité métier calibrée ;
- la diarisation ne prouve pas l’identité réelle d’une personne ;
- le LLM peut produire un JSON invalide, être lent ou halluciner.

### Contraintes réseau et licences

- Nominatim et Hugging Face peuvent être indisponibles ;
- pyannote nécessite un jeton et l’acceptation d’une licence ;
- l’API E-consta réelle n’est pas disponible dans le POC ;
- le téléchargement automatique de modèles est désactivé.

### Contraintes de sécurité et confidentialité

- les audios et déclarations contiennent des données personnelles ;
- une politique de chiffrement, rétention, purge et contrôle d’accès reste nécessaire avant production ;
- les secrets doivent rester dans `.env`, hors Git ;
- les audios, bases locales, modèles et exports ne doivent pas être versionnés ;
- un audit de sécurité et une analyse réglementaire restent nécessaires.

### Contraintes de montée en charge

- SQLite est limité en concurrence d’écriture ;
- un seul worker est recommandé dans le contexte local actuel ;
- les agrégations du tableau de bord sont effectuées en Python, adaptées au petit volume du POC ;
- aucun test de charge ne permet encore d’annoncer une capacité de production.

### Contraintes métier

- validation humaine obligatoire ;
- pas de détermination automatique des responsabilités ;
- pas d’envoi avant validation ;
- le GPS indique la position présente et ne prouve pas le lieu du sinistre ;
- un lieu trouvé dans le gazetteer ne prouve pas que l’accident y a eu lieu.

---

## 9. Sécurité et traçabilité

Le système prévoit :

- authentification JWT ;
- mots de passe hachés avec bcrypt ;
- rôles `agent` et `responsable` relus depuis la base ;
- contrôle de propriété des appels et déclarations ;
- réponse 404 pour éviter de révéler une ressource appartenant à un autre utilisateur ;
- validation de la taille, du MIME, du conteneur et de la durée audio ;
- noms de fichiers générés par UUID ;
- empreinte SHA-256 des médias ;
- journaux d’audit des opérations importantes ;
- idempotence des envois E-consta ;
- absence de secrets ou de données personnelles dans Git.

Le mode local de démonstration peut désactiver l’authentification. Cette configuration ne doit pas
être utilisée telle quelle dans un environnement partagé ou exposé au réseau.

---

## 10. Tests et assurance qualité

La suite couvre notamment :

- configuration et base de données ;
- authentification et contrôle d’accès ;
- validation des fichiers audio ;
- transcription et cache des modèles ;
- diarisation et correction des locuteurs ;
- extraction des informations ;
- parseurs spécialisés ;
- conversation et confirmation ;
- géolocalisation ;
- jobs, reprise et erreurs ;
- export JSON et garde-fous ;
- API et interface utilisateur ;
- dashboard ;
- parcours de bout en bout.

Les commandes de contrôle sont :

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\diagnose.py
```

Le succès des tests confirme la cohérence logicielle, mais ne constitue pas une validation métier
de la précision de l’IA ni une homologation de production.

---

## 11. Limites actuelles

- Le projet reste un POC.
- La précision ASR n’est pas mesurée sur un corpus ivoirien annoté et consenti.
- La téléphonie réelle n’est pas intégrée.
- E-consta est simulé par un serveur mock.
- La diarisation de qualité dépend d’un modèle sous licence.
- Le complément Qwen/Ollama peut dépasser le délai ou retourner une sortie invalide.
- Les tests de charge, l’audit de sécurité et l’analyse réglementaire ne sont pas terminés.
- La gestion complète du cycle de vie des données personnelles reste à définir.

---

## 12. Recommandations avant production

1. Constituer légalement un corpus audio ivoirien représentatif et annoté.
2. Mesurer le WER global et par catégories sensibles : noms, téléphones, assureurs, plaques, lieux.
3. Comparer Whisper Small à des modèles français plus grands sur le matériel cible.
4. Calibrer les seuils de confirmation à partir de données réelles.
5. Ajouter suppression, durée de rétention et chiffrement des audios.
6. Réaliser une analyse de protection des données et un audit de sécurité.
7. Utiliser PostgreSQL et tester plusieurs utilisateurs concurrents.
8. Effectuer des tests de charge et de reprise après panne.
9. Intégrer le contrat réel d’E-consta dans un environnement de recette.
10. Mettre en place supervision, sauvegardes, alertes et procédure d’exploitation.
11. Conserver la correction manuelle et la validation humaine même après amélioration des modèles.

---

## 13. Conclusion

E-Constat IA repose sur une architecture pragmatique adaptée à une démonstration locale : Python,
FastAPI, Gradio, SQLAlchemy, Faster-Whisper et des services IA optionnels. Les choix privilégient
la portabilité CPU, l’explicabilité, la reprise, la sécurité et la validation humaine plutôt que la
complexité d’une infrastructure distribuée.

La principale faiblesse observée concerne la reconnaissance des informations sensibles avec le
petit modèle Whisper. Le passage au mode précision par défaut, le contexte fourni à l’ASR et la
correction écrite réduisent le risque sans prétendre supprimer le besoin de contrôle humain.

Le socle est approprié pour continuer les expérimentations. Une mise en production exige toutefois
des mesures sur données représentatives, une gouvernance des données personnelles, un audit de
sécurité, une infrastructure de base plus concurrente et une intégration réelle avec E-consta.

