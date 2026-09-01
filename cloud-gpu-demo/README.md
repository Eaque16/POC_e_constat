# E-Constat IA — laboratoire GPU cloud

Ce dossier est indépendant du POC CPU situé à la racine. Il permet de comparer une
transcription GPU plus lourde sans modifier le parcours stable.

## Option recommandée : Hugging Face ZeroGPU

Le dossier `huggingface-space/` contient une application Gradio prête à être copiée dans
une Space. Elle utilise `openai/whisper-large-v3-turbo` sur GPU et affiche séparément :

- la transcription ;
- le champ métier attendu et la valeur extraite ;
- un signal conversationnel prudent, jamais présenté comme un diagnostic émotionnel ;
- les temps de chargement et d'inférence GPU.

### Publication

1. Créer un compte Hugging Face et vérifier l'adresse e-mail.
2. Le compte gratuit doit être en règle et âgé de plus de 30 jours pour héberger ZeroGPU.
3. Créer une Space **Gradio** publique.
4. Copier le contenu de `huggingface-space/` dans le dépôt de la Space.
5. Dans `Settings > Hardware`, choisir **ZeroGPU**.
6. Attendre la construction puis ouvrir l'URL `https://<compte>-<space>.hf.space`.

ZeroGPU est soumis à une file d'attente et à un quota quotidien. Il convient à une courte
démonstration, pas à un service permanent.

## Option benchmark : Kaggle

Importer `kaggle_gpu_benchmark.ipynb` dans Kaggle, puis activer
`Settings > Accelerator > GPU`. Le notebook mesure la VRAM, charge Faster-Whisper en CUDA
et compare les profils `large-v3-turbo`, `small` et `tiny` sur un fichier audio.

Kaggle convient mieux aux essais de plusieurs heures, mais pas à l'hébergement durable de
l'interface React.

## Données et confidentialité

N'utiliser que des audios synthétiques ou explicitement autorisés. Une Space publique rend
son code visible et le fichier audio transite sur une infrastructure tierce. Aucun audio
client réel, token, secret ou dossier nominatif ne doit être utilisé dans cette expérience.

