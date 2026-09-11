# Phase 1 — Installer et configurer

[Sommaire](README.md) · [Phase suivante](02_SOURCES_ET_UML.md)

## Objectif, entrée et résultat

Préparer un poste capable d'exécuter l'application et les pipelines. Entrées : le dépôt, Python, Neo4j et les paramètres d'accès. Résultat : un environnement Python fonctionnel et une configuration locale. Cette étape n'alimente pas le graphe.

## Vérifier le package

Le dossier actif et les imports utilisent désormais le même nom : `arianes`. Depuis la racine, vérifier :

```powershell
Test-Path .\arianes
Select-String -Path api.py -Pattern 'from arianes'
python -B -c "import arianes; print('Package arianes importable')"
```

Les deux premières commandes doivent renvoyer `True` puis une ligne d’import dans `api.py`. La dernière doit afficher `Package arianes importable`. Tous les exemples suivants utilisent ce package cohérent.

## Installer dans un environnement séparé

Depuis la racine du dépôt :

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` inclut les dépendances applicatives et pytest. Pour un poste sans tests, utiliser `requirements.txt`. Les versions ne sont pas verrouillées : la reproductibilité complète reste à établir. L'appel direct au Python de `.venv` évite de modifier la politique d'exécution PowerShell.

Dans les autres guides, `python` désigne cet interpréteur ; le remplacer par `.\.venv\Scripts\python.exe` si nécessaire.

## Configurer les services

Créer `.env` à partir de `.env.example` uniquement si `.env` n'existe pas. Renseigner les paramètres dans un éditeur local :

- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` : accès à la base attendue.
- Au moins une clé parmi `MISTRAL_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY` pour le démarrage de l'agent.
- Le nom du modèle du fournisseur choisi, réellement accessible avec cette clé.
- `DATABASE_URL` si le stockage applicatif diffère du SQLite local par défaut.

L'extraction métier et les embeddings du builder utilisent Mistral. Une clé Gemini seule peut permettre le démarrage du chatbot, mais ne remplace pas ces usages Mistral. Les variables Ollama présentes dans le code ne créent pas une option Ollama dans le sélecteur de l'interface actuelle.

Ne pas publier `.env`. Un `.gitignore` n'enlève pas un secret déjà présent dans l'historique Git. Le proxy, si nécessaire, doit correspondre à la configuration fournie par l'équipe informatique ; l'ancien fichier Commandes.txt contenait une adresse liée à un poste, non une configuration universelle.

## Démarrer et vérifier

Démarrer Neo4j puis :

```powershell
python -m uvicorn api:app --reload
```

Ouvrir `http://127.0.0.1:8000/`. Le contrôle `http://127.0.0.1:8000/health` teste la connexion Neo4j ; il ne valide ni le corpus, ni les index, ni les quotas LLM.

Si le port est indisponible, utiliser `--port 8001` et ouvrir l'adresse correspondante. Arrêter le serveur avec Ctrl+C. Redémarrer après changement de `.env`.

Une installation quotidienne ne nécessite pas de relancer les builders. Les imports sont des opérations de préparation, avec écritures en base et parfois appels API.
