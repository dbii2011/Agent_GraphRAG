# Agent GraphRAG Arianes

Application de question-réponse combinant le métamodèle UML Arianes, les fiches
documentaires et un graphe métier validé dans Neo4j.

## Démarrage

Depuis la racine du dépôt :

```powershell
python -m uvicorn api:app --reload
```

L'application est ensuite accessible sur <http://127.0.0.1:8000>.

## Organisation

```text
api.py                       API FastAPI et point d'entrée
index.html                   interface du chatbot
arianes/
  agent.py                   orchestration du retrieval et des LLM
  retrieval.py               routage et retrieval GraphRAG
  paths.py                   chemins centralisés du projet
  graph/
    uml_builder.py           construction du graphe UML/documentaire
    metier_builder.py        import du graphe métier validé
  pipelines/
    extraction_metier.py     extraction contrôlée d'une ou plusieurs fiches
    extraction_globale.py    extraction de toutes les fiches
    validation_metier.py     règles de validation locales
    recontrole_metier.py     second contrôle des propositions
    selection_prudente.py    sélection automatique conservatrice
    generer_pilotes.py       un pilote gradué pour chaque fiche
    normalisation_metier.py  fusion des concepts métier en doublon
    import_pilote.py         import du pilote métier
    xmi_to_json.py           conversion des exports XMI en JSON
project_data/
  uml/                       métamodèle converti en JSON
  procedures/                fiches documentaires texte
  metier/                    propositions et sélections métier
  xmi/                       exports XMI sources
tests/                       tests automatisés
ml/                          prototype de reranking
documentation/               guides et documentation détaillée
reports/                     rapports LaTeX et Overleaf
presentations/               diaporamas et ressources de présentation
legacy/                      anciens prototypes conservés
```

## Commandes principales

```powershell
# Construire le graphe UML et documentaire
python -m arianes.graph.uml_builder

# Extraire le graphe métier de toutes les fiches
python -m arianes.pipelines.extraction_globale

# Recontrôler et classifier les relations des 29 fiches
python -m arianes.pipelines.recontrole_metier `
  --output-dir project_data/metier/corrections_v3

# Générer les pilotes documentaires individuels
python -m arianes.pipelines.generer_pilotes

# Générer la sélection documentaire globale
python -m arianes.pipelines.selection_prudente

# Importer une définition métier validée
python -m arianes.graph.metier_builder `
  project_data/metier/pilote_global_documentaire.json

# Évaluer le retrieval
python -m arianes.evaluation

# Exécuter les tests
python -m unittest discover -s tests -v
```

Les chemins de données sont définis dans `arianes/paths.py`. Les secrets restent
uniquement dans `.env`.
