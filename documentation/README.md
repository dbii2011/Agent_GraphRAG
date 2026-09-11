# Documentation du projet Arianes

Révision du 11 septembre 2026, établie par lecture du code et des huit anciens documents techniques. Cette révision ne lance ni import Neo4j, ni extraction LLM, ni campagne de tests.

## Commencer ici

- [Guide d’utilisation](GUIDE_UTILISATION.md) : utilisation du chatbot, conservé sans modification.
- [Rapport de stage PDF](Rapport_Stage_GraphRAG.pdf) : rapport conservé sans modification ; photographie du travail à sa date de rédaction.
- [Installation et configuration](01_INSTALLATION_CONFIGURATION.md).
- [Sources et conversion UML](02_SOURCES_ET_UML.md).
- [Documents, chunks et recherche](03_DOCUMENTS_ET_INDEXATION.md).
- [Extraction des concepts et relations métier](04_EXTRACTION_METIER.md).
- [Contrôle, sélection et pilotes](05_VALIDATION_ET_PILOTES.md).
- [Import Neo4j et provenance](06_IMPORT_ET_PROVENANCE.md).
- [Retrieval, agent et application](07_RETRIEVAL_ET_APPLICATION.md).
- [Tests, exploitation et prototype ML](08_TESTS_EXPLOITATION_ML.md).
- [Inventaire des scripts](BILAN_SCRIPTS_PYTHON.md).
- [Trame de présentation et démonstration](09_PRESENTATION_ET_DEMONSTRATION.md).
- [Changements de documentation et limites](MISE_A_JOUR_DOCUMENTATION.md).

## Cohérence du package Python

Le code actif se trouve dans `arianes/`, conformément aux imports de `api.py`, des pipelines, des builders et des tests. Les commandes `python -m arianes...` des guides peuvent donc être exécutées depuis la racine du dépôt, après installation des dépendances et configuration des services.

## Deux chaînes à distinguer

La préparation produit les connaissances : XMI → JSON UML → Neo4j ; fiches → chunks et embeddings → Neo4j ; fiches et catalogue UML → propositions métier → recontrôle → pilotes → import.

L'utilisation consulte ces connaissances : navigateur → API → agent → retrieval → Neo4j → réponse, éventuellement rédigée par le fournisseur choisi. SQLite conserve les comptes et conversations.

Les noms `corrections_v2` et `corrections_v3` désignent des résultats historiques. Le contrôleur actuel déclare `VERSION_VALIDATION = 4`. Un dossier ancien n'est pas mis à jour automatiquement par un changement du code.

Les guides décrivent les traitements, pas un inventaire certifié de la base active. Une sortie JSON sur disque ne prouve pas son import. Un test réussi ne certifie pas une règle ferroviaire.

## Historique

Les huit anciens textes sont conservés dans [archives/2026-09-11](archives/2026-09-11/README.md). Leurs commandes et chiffres ne doivent plus servir de référence courante. Ils restent disponibles pour retrouver le déroulement du stage et les anciens discours.
