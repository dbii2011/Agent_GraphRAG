# Prototype de reranking ML

Le prototype apprend à estimer la pertinence d'un chunk à partir des signaux déjà
produits par le GraphRAG. Il ne remplace ni Neo4j, ni les embeddings, ni Mistral.

Caractéristiques utilisées : scores sémantique, lexical et de fusion, recouvrement
de mots avec le texte et le titre, présence de la classe, rang initial et longueur
du passage.

## Construire le dataset prototype

```powershell
python ml\build_dataset_from_evaluation.py
```

Les labels sont faiblement supervisés : un chunk est positif lorsque son fichier
correspond à la source attendue dans `evaluation_graphrag.json`. Ces labels doivent
être remplacés progressivement par des annotations humaines.

## Entraîner

```powershell
python ml\train_reranker.py ml\datasets\reranker_prototype.jsonl `
  --output ml\models\reranker_prototype.json
```

## Évaluer par question

```powershell
python ml\evaluate_reranker.py ml\datasets\reranker_prototype.jsonl
```

## Activer dans l'application

Ajouter dans `.env` :

```text
RERANKER_MODEL_PATH=ml/models/reranker_prototype.json
```

Puis redémarrer l'API. Si le fichier manque ou est incompatible, le retriever
revient automatiquement au classement par fusion.

Ce modèle est un prototype de faisabilité. Un déploiement fiable nécessite plus
de questions, des chunks annotés manuellement et une évaluation sur un jeu jamais
utilisé pendant l'entraînement.
