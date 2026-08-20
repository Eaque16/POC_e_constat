# E-Constat IA

POC local et open source de declaration vocale d'un sinistre automobile.

## Fonctionnalites actuelles

- API FastAPI avec controle de sante ;
- upload audio securise et limite a 25 Mio ;
- transcription locale en francais avec Faster-Whisper ;
- interface Gradio avec microphone ou import de fichier ;
- affichage de la transcription, de la langue, de la confiance et de la duree.
- extraction conservative des informations importantes vers le JSON E-Constat.

L'interface actuelle simule un appel par un enregistrement termine. Le streaming
audio continu, l'extraction par LLM et la diarisation des locuteurs viendront
plus tard. Le premier extracteur est deterministe : une valeur absente reste
`null`.

## Installation

Depuis la racine du projet :

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Le modele Faster-Whisper est telecharge au premier usage s'il n'est pas deja
present dans le cache local.

## Lancement de la demonstration

Si Ollama est installe dans `.tools/ollama`, le demarrer dans un terminal :

```bash
cd /home/komelan01/econstat-ai
./scripts/start_ollama.sh
```

Puis telecharger une fois le modele, dans un autre terminal :

```bash
cd /home/komelan01/econstat-ai
OLLAMA_HOST=127.0.0.1:11434 .tools/ollama/bin/ollama pull qwen2.5:1.5b
```

Par defaut, l'API utilise l'extracteur deterministe rapide afin de poser les
questions manquantes sans attendre Qwen. La case « analyse approfondie » de
l'interface active Ollama/Qwen. Si le service est indisponible, l'API revient
automatiquement a l'extracteur rapide.

Les lexiques versionnes dans `data/reference/` aident Faster-Whisper a decoder
les noms et lieux ivoiriens. Une orthographe proche est seulement proposee a
la confirmation : un nom ou un lieu critique n'est jamais remplace en silence.
Le lexique est transmis comme `hotwords`, sans le dupliquer dans le prompt
initial, et la generation est plafonnee a 128 nouveaux tokens par segment afin
de rester sous la limite de 448 positions du decodeur Whisper. Cette valeur est
ajustable avec `WHISPER_MAX_NEW_TOKENS`.

Dans un premier terminal :

```bash
cd /home/komelan01/econstat-ai
source .venv/bin/activate
uvicorn backend.app.main:app --reload
```

Dans un second terminal :

```bash
cd /home/komelan01/econstat-ai
source .venv/bin/activate
python -m frontend.app
```

Ouvrir ensuite <http://127.0.0.1:7860>, autoriser le microphone, enregistrer le
recit du sinistre, arreter l'enregistrement puis cliquer sur **Transcrire
l'appel**.

La documentation de l'API est disponible sur <http://127.0.0.1:8000/docs>.

## Demonstration Docker en une commande

Docker Compose lance trois services isoles : FastAPI, Gradio et Ollama. Les
modeles Whisper et Ollama sont conserves dans des volumes entre les lancements.
Aucun fichier `.env` n'est obligatoire : des valeurs locales adaptees a la
demonstration sont deja definies dans `compose.yaml`.

Demarrer Docker Desktop, puis executer :

```bash
cd /home/komelan01/econstat-ai
./scripts/start_demo_docker.sh
```

Le script choisit automatiquement un contexte Docker actif, construit l'image,
demarre les conteneurs et affiche les adresses. Au premier lancement seulement,
Compose telecharge automatiquement Qwen et Whisper est telecharge lors de la
premiere transcription. Ces modeles restent ensuite dans des volumes Docker.

Arreter la demonstration sans supprimer les modeles :

```bash
./scripts/stop_demo_docker.sh
```

Commandes de diagnostic facultatives :

```bash
docker compose logs -f
docker compose ps
```

Les volumes `whisper-cache` et `ollama-data` ne sont volontairement pas
supprimes par le script d'arret.

### Bouton du Bureau

Le lanceur `E-Constat IA - Demarrer Arreter` place sur le Bureau execute
`scripts/toggle_demo_docker.sh`. Un double-clic demarre la demonstration si elle
est arretee, ou l'arrete si des conteneurs du projet sont actifs. Docker Desktop
doit etre demarre au prealable.

## Tests

```bash
cd /home/komelan01/econstat-ai
source .venv/bin/activate
python -m unittest discover -s tests -v
```

## Configuration

Les valeurs configurables sont documentees dans `.env.example`, notamment le
modele Whisper, le mode CPU/int8, la limite d'upload et l'adresse du backend.
