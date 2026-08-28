# Agent Arianes GraphRAG — documentation complète du projet

## 1. Objectif du projet

Ce projet construit un assistant conversationnel spécialisé dans le métamodèle
Arianes et dans les fiches métier ferroviaires.

L'assistant doit pouvoir répondre à deux familles de questions :

- questions structurelles : classes, attributs, types, héritages, associations,
  compositions, agrégations et cardinalités du métamodèle ;
- questions documentaires : définitions, procédures et règles présentes dans les
  fiches de référence.

Le système combine :

- les exports XMI du métamodèle Arianes ;
- leur conversion en JSON ;
- un graphe Neo4j ;
- des documents découpés en chunks et vectorisés ;
- une récupération GraphRAG contrôlée ;
- Mistral pour les embeddings et la rédaction de la réponse ;
- une API FastAPI ;
- une interface web ;
- une base SQLite pour les comptes et les conversations ;
- une nouvelle couche de concepts métier, encore soumise à validation avant
  import dans Neo4j.

## 2. Architecture générale

```text
Exports XMI
    │
    ▼
XmiToJson.py
    │
    ▼
Data/*.json ─────────────┐
                        │
Docs/*.txt ──────────────┤
                        ▼
                GrapheBuilder_v3.py
                        │
                        ▼
                    Neo4j
         ┌──────────────┼────────────────┐
         │              │                │
    Métamodèle       Documents        Chunks
         │              │                │
         └──────────────┴────────────────┘
                        │
                        ▼
              graphrag_retriever.py
                        │
                        ▼
                   Agent_LG.py
                        │
                        ▼
                      api.py
                  ┌─────┴─────┐
                  ▼           ▼
              index.html    SQLite
```

La couche métier suit un chemin séparé :

```text
Data/*.json + Docs/*.txt
          │
          ▼
pipeline_graphe_metier.py
          │
          ▼
Propositions A_REVOIR
          │
          ▼ validation humaine
graphe_metier_builder.py
          │
          ▼
(:ConceptMetier) dans Neo4j
```

## 3. Modèle de données Neo4j

### 3.1 Métamodèle technique

Les principaux labels sont :

- `Classe` : classe du métamodèle Arianes ;
- `Attribut` : propriété appartenant à une classe ;
- `Type` : type primitif ou type de l'attribut ;
- `Enum` : énumération ;
- `ValeurEnum` : valeur d'une énumération.

Relations principales :

```text
Classe ──A_ATTRIBUT──> Attribut
Attribut ──EST_DE_TYPE──> Type ou Enum
Enum ──A_VALEUR──> ValeurEnum
Classe ──HERITE_DE──> Classe
Classe ──COMPOSE_DE──> Classe
Classe ──AGREGE──> Classe
Classe ──ASSOCIE_A──> Classe
```

### 3.2 Couche documentaire

Les labels documentaires sont :

- `Document` : fiche de référence complète ;
- `Chunk` : passage d'une fiche ;
- `Chunk.embedding` : vecteur Mistral de dimension 1024.

Relations :

```text
Chunk ──APPARTIENT_A──> Document
Document ──DECRIT──> Classe
```

Indexes utilisés :

- `chunk_embeddings` : index vectoriel cosine sur `Chunk.embedding` ;
- `chunk_fulltext` : index plein texte sur `Chunk.texte`.

### 3.3 Couche métier

La couche métier est ajoutée sans modifier le métamodèle existant :

```text
ConceptMetier ──RELATION_METIER──> ConceptMetier
ConceptMetier ──REPRESENTE_PAR──> Classe
ConceptMetier ──DOCUMENTE_PAR──> Document
```

Une relation métier conserve notamment :

- son type métier ;
- sa citation ;
- son document source ;
- les lignes concernées ;
- son état de validation.

Les propositions automatiques ne sont pas importées directement. Elles sont
d'abord enregistrées avec le statut `A_REVOIR`.

## 4. Parcours complet des données

### Étape 1 — conversion XMI vers JSON

`XmiToJson.py` lit les exports XMI et produit des fichiers structurés dans
`Data/`.

Il extrait :

- les classes UML ;
- les descriptions ;
- le caractère abstrait ;
- les attributs et leurs types ;
- les énumérations et leurs valeurs ;
- les généralisations ;
- les associations, rôles et cardinalités.

Le JSON produit suit principalement cette forme :

```json
{
  "enums": [],
  "classes": [],
  "generalizations": [],
  "relations": []
}
```

### Étape 2 — construction de Neo4j

`GrapheBuilder_v3.py` lit les JSON de `Data/` et les fiches de `Docs/`.

Pour le métamodèle, il crée ou fusionne les classes, attributs, types,
énumérations et relations.

Pour les documents, il :

1. crée un nœud `Document` ;
2. découpe le texte en chunks ;
3. calcule un embedding Mistral pour chaque chunk ;
4. crée les nœuds `Chunk` ;
5. rattache les chunks à leur document ;
6. tente de relier le document à une classe de même nom.

L'import utilise `MERGE` afin d'être relançable sans dupliquer volontairement
les mêmes identifiants.

### Étape 3 — récupération GraphRAG

`graphrag_retriever.py` ne laisse pas le LLM inventer librement des requêtes
Cypher. Il construit le contexte de manière déterministe.

Le parcours est :

```text
Question
  → contextualisation avec le dernier message utilisateur
  → résolution lexicale des classes
  → choix du mode de recherche
  → extraction du sous-graphe technique
  → extraction éventuelle du sous-graphe métier
  → recherche documentaire vectorielle et plein texte
  → fusion et classement des passages
  → contexte JSON transmis à Mistral
```

Les trois modes sont :

- `STRUCTURE` : métamodèle uniquement, sans chunks ;
- `DOCUMENTAIRE` : priorité aux passages de référence ;
- `HYBRIDE` : structure, métier et documentation.

La recherche documentaire combine :

- similarité cosine des embeddings ;
- recherche plein texte ;
- fusion réciproque des rangs ;
- seuils destinés à rejeter les questions sans ancrage documentaire.

### Étape 4 — génération de la réponse

`Agent_LG.py` reçoit le contexte contrôlé du retriever et l'envoie à Mistral.

Le modèle doit :

- répondre uniquement avec les informations du contexte ;
- distinguer les faits structurels des passages documentaires ;
- ne pas inventer de classe, relation ou procédure ;
- signaler les informations manquantes ;
- citer les sources documentaires.

L'ancien agent capable de choisir librement des outils et de générer ses propres
requêtes n'est plus le chemin actif.

### Étape 5 — API et conversations

`api.py` expose l'agent avec FastAPI.

Les comptes, sessions, conversations et messages sont stockés dans SQLite.
Neo4j contient la connaissance Arianes ; SQLite contient l'état de l'application.

### Étape 6 — interface web

`index.html` appelle l'API pour :

- créer un compte ;
- se connecter et se déconnecter ;
- créer une conversation ;
- ouvrir une ancienne conversation ;
- supprimer une conversation ;
- envoyer une question ;
- afficher l'historique et la réponse.

## 5. Description des fichiers actifs

### `XmiToJson.py`

Convertisseur XMI vers JSON.

Fonctions importantes :

- `get_documentation` : récupère la documentation UML ;
- `est_une_enumeration` : reconnaît une énumération ;
- `get_multiplicity` : extrait une cardinalité ;
- `parse_xmi` : analyse les classes, attributs, enums et relations ;
- `deduplique` : supprime les classes dupliquées dans un export ;
- `read_xmi_file` : lit un fichier XMI ;
- `main` : traite les fichiers sources.

### `GrapheBuilder_v3.py`

Builder principal du graphe technique et documentaire.

Méthodes principales de `ArianeGraphBuilder` :

- `create_constraints` : crée contraintes et indexes Neo4j ;
- `merge_classe` : crée ou met à jour une classe ;
- `merge_attribut` : crée un attribut et son type ;
- `merge_enum` : crée une énumération et ses valeurs ;
- `add_relation` : ajoute une relation UML autorisée ;
- `merge_document` : crée un document ;
- `merge_chunk` : crée un passage vectorisé ;
- `lier_document_a_classe` : rattache une fiche à une classe.

Fonctions extérieures :

- `importer_modele_depuis_json` : importe un JSON Arianes ;
- `parser_nom_fichier` : transforme le nom d'une fiche en classe candidate ;
- `importer_document` : découpe et vectorise une fiche ;
- `main` : orchestre l'import complet.

### `graphrag_retriever.py`

Cœur du GraphRAG contrôlé.

Fonctions et méthodes :

- `normaliser` : retire accents et variations de casse, découpe le CamelCase ;
- `tokens` : produit les mots utiles d'une expression ;
- `_charger_catalogue` : met en cache la liste des classes ;
- `resoudre_classes` : classe les entités candidates avec scores explicables ;
- `determiner_mode` : choisit structure, documentaire ou hybride ;
- `_construire_sous_graphe` : récupère racines, voisins, attributs et relations ;
- `_selectionner_concepts` : détecte les concepts métier pertinents ;
- `_construire_graphe_metier` : récupère leur voisinage métier ;
- `_chercher_chunks` : recherche vectorielle et lexicale ;
- `retrieve` : exécute le pipeline complet ;
- `contexte_pour_llm` : sérialise le résultat en JSON pour l'agent.

### `Agent_LG.py`

Agent de réponse actif.

Responsabilités :

- initialiser Neo4j, Mistral et les embeddings ;
- appeler le retriever ;
- transmettre l'historique récent ;
- construire le prompt système anti-hallucination ;
- appeler Mistral ;
- ajouter les citations ;
- convertir les erreurs réseau Mistral en messages compréhensibles ;
- fermer proprement le driver Neo4j.

`get_schema_context` fournit un aperçu borné du graphe.
`_valider_et_executer` conserve un exécuteur Cypher strictement en lecture seule,
principalement pour la compatibilité et les tests de sécurité.

### `api.py`

API principale de l'application.

Modèles SQLite :

- `Utilisateur` : compte utilisateur ;
- `SessionAuthentification` : session connectée ;
- `Conversation` : titre et date de conversation ;
- `ProprietaireConversation` : rattachement d'une conversation à son utilisateur ;
- `Message` : message ordonné dans une conversation.

Sécurité :

- mots de passe PBKDF2-HMAC-SHA256 avec sel ;
- comparaison constante des empreintes ;
- jetons de session aléatoires ;
- stockage de l'empreinte du jeton ;
- cookie HttpOnly avec politique SameSite stricte ;
- contrôle du propriétaire pour chaque conversation ;
- validation UUID ;
- longueur maximale des questions.

Routes :

- `POST /auth/register` : inscription ;
- `POST /auth/login` : connexion ;
- `POST /auth/logout` : déconnexion ;
- `GET /auth/me` : utilisateur courant ;
- `POST /ask` : question à l'agent ;
- `GET /conversations` : conversations de l'utilisateur ;
- `GET /conversations/{id}/messages` : historique ;
- `DELETE /conversations/{id}` : suppression ;
- `GET /schema` : aperçu du graphe ;
- `GET /health` : état API/Neo4j ;
- `GET /` : interface web.

### `index.html`

Frontend autonome HTML/CSS/JavaScript.

Fonctions JavaScript principales :

- `api` : wrapper autour de `fetch` avec gestion des erreurs ;
- `verifierSession` : vérifie si un utilisateur est connecté ;
- `chargerConversations` : charge la liste de l'utilisateur ;
- `ouvrirConversation` : affiche les messages d'une conversation ;
- `nouvelleConversation` : remet l'interface en état de nouvelle discussion ;
- `envoyerQuestion` : envoie la question à `/ask` ;
- `ajouterMessage` : affiche un message dans le fil.

### `pipeline_graphe_metier.py`

Pipeline d'extraction contrôlée de la couche métier.

Il possède trois commandes :

```text
extraire → valider → importer
```

Fonctions principales :

- `charger_catalogue` : catalogue les classes des JSON ;
- `classes_candidates` : trouve les classes proches d'un passage ;
- `decouper_document` : découpe une fiche avec numéros de lignes ;
- `prompt_extraction` : impose à Mistral un JSON et des types autorisés ;
- `extraire_json_message` : récupère l'objet JSON de la réponse ;
- `valider_extraction` : contrôle concepts, citations et relations ;
- `consolider` : fusionne les concepts identiques et déduplique les relations ;
- `extraire_document` : traite une fiche complète ;
- `marquer_valide` : passe une proposition relue en `VALIDE` ;
- `filtrer_valides` : empêche l'import des éléments non validés.

Le filtre est volontairement tolérant sur la sémantique : un prédicat non confirmé
produit un avertissement au lieu de supprimer automatiquement la relation.

Les erreurs certaines restent bloquantes :

- auto-relation ;
- concept source ou cible absent ;
- citation absente du passage ;
- type de relation inconnu.

Pour une phrase passive comme « le canton est commandé par un signal », la
relation est conservée sous la forme :

```text
Canton ──EST_COMMANDE_PAR──> Signal
```

### `extraire_tout_graphe_metier.py`

Exécute l'extraction sur toutes les fiches `Docs/*.txt`.

Caractéristiques :

- inventaire automatique des fiches ;
- traitement document par document ;
- sauvegarde intermédiaire après chaque fiche ;
- reprise après interruption ;
- option `--force` pour recalculer ;
- option `--limite` pour tester ;
- consolidation dans `DataMetier/proposition_globale.json` ;
- aucun import Neo4j automatique.

### `graphe_metier_builder.py`

Importeur Neo4j de la couche métier validée.

Il :

- crée la contrainte unique `ConceptMetier.id` ;
- fusionne les concepts ;
- crée `REPRESENTE_PAR` vers les classes existantes ;
- crée `DOCUMENTE_PAR` vers les documents existants ;
- crée les `RELATION_METIER` ;
- conserve citation, fichier et lignes ;
- utilise `MERGE` pour être idempotent.

Le `MATCH` sur une classe ou un document est exact ou fondé sur la fin du nom.
Si la cible n'existe pas, le lien n'est pas créé. Une future amélioration devra
produire un rapport explicite des rattachements manquants et des liens directs
`JUSTIFIE_PAR` vers les chunks.

### `evaluate_graphrag.py`

Évalue le retrieval sur les questions de référence.

Il vérifie :

- le mode attendu ;
- les classes racines ;
- les sources documentaires ;
- le rejet d'une question hors domaine.

Avec `--with-llm`, il appelle également Mistral et conserve la réponse finale.

### `app.py`

Ancienne API FastAPI minimale. Elle expose seulement `/ask` et `/health` sans le
système complet de comptes et conversations. Le serveur actif recommandé utilise
`api.py`, pas `app.py`.

### `.env.example`

Modèle des variables nécessaires, sans secret réel :

```text
MISTRAL_API_KEY
MISTRAL_MODEL
NEO4J_URI
NEO4J_USER
NEO4J_PASSWORD
```

Le fichier réel `.env` est ignoré par Git.

### `.gitignore`

Exclut notamment :

- `.env` et secrets locaux ;
- environnements Python ;
- caches ;
- bases SQLite ;
- logs et fichiers temporaires ;
- réglages d'IDE.

## 6. Répertoires de données

### `XMI/`

Exports bruts du métamodèle. Ils constituent la source structurelle initiale et
ne doivent pas être interrogés directement par l'agent en production.

### `Data/`

JSON normalisés produits depuis les XMI. Ils alimentent le builder Neo4j et le
catalogue de classes du pipeline métier.

### `Docs/`

Fiches métier et procédures au format texte. Elles sont chunkées et indexées dans
Neo4j et servent aussi à extraire les concepts métier.

### `DataMetier/`

Contient :

- `poste_aiguillage.json` : premier sous-graphe métier validé manuellement ;
- `proposition_poste_auto.json` : extraction automatique de `Post.txt` ;
- `propositions/*.metier.json` : checkpoints par fiche ;
- `proposition_globale.json` : consolidation de toutes les fiches traitées.

Les fichiers automatiques restent `A_REVOIR` tant qu'ils ne sont pas approuvés.

## 7. Tests

### `tests/test_agent_security.py`

Vérifie la validation Cypher en lecture seule, l'appel du retriever et la gestion
de l'indisponibilité réseau.

### `tests/test_api_validation.py`

Vérifie les entrées API : UUID, longueur des questions et erreurs contrôlées.

### `tests/test_auth_and_ownership.py`

Vérifie l'inscription, la connexion, les cookies, l'isolation des conversations
et la mémoire transmise dans une conversation.

### `tests/test_graphrag_retriever.py`

Vérifie la normalisation, la résolution de classes, les modes de retrieval et la
sélection des concepts métier.

### `tests/test_graphe_metier_builder.py`

Vérifie la cohérence structurelle des définitions métier.

### `tests/test_pipeline_graphe_metier.py`

Vérifie le découpage, les classes candidates, les citations, les statuts, les
relations passives, l'extraction globale et l'absence d'écriture Neo4j pendant la
phase de proposition.

### `tests/evaluation_questions.json`

Jeu de questions structurelles, documentaires, hybrides, contextuelles et hors
domaine.

### `evaluation_graphrag.json`

Dernier rapport produit par `evaluate_graphrag.py`. C'est un artefact de test,
pas une source de connaissance.

## 8. Prototypes historiques dans `Bin/`

Le dossier `Bin/` contient les anciennes expérimentations. Elles sont conservées
pour référence mais ne constituent pas le chemin de production.

- `Agent_v3.py` : ancien agent Mistral générant/interprétant des requêtes graphe ;
- `mini_agent_neo4j_mistral.py` : prototype minimal Neo4j + Mistral ;
- `AgentGraphRag.py` : tentative initiale de vector store GraphRAG, incomplète ;
- `GrapheBuilder_V1.py` : premier builder UML ;
- `GrapheBuilder_v2.py` : builder enrichi de plusieurs gammes Arianes ;
- `build_ariane_graph.py` : ancienne variante du builder ;
- `SNCFGraphBuilder.py` : prototype de graphe construit depuis des données SNCF
  ouvertes, différent du métamodèle actuel ;
- `sncf_client.py` : client de l'API open data SNCF ;
- `test_neo4j.py` : vérification simple de connexion ;
- `testatr.py` : expérimentation Spark indépendante ;
- `data.json` : donnée d'exemple historique.

Ne pas lancer ces scripts pour reconstruire le graphe actif sans audit préalable.

## 9. Installation et configuration

Prérequis :

- Python ;
- Git ;
- Neo4j ;
- une clé Mistral valide ;
- les dépendances Python déjà utilisées par le projet : FastAPI, Uvicorn,
  SQLModel, Neo4j, LangChain Mistral, python-dotenv et httpx.

Créer le fichier `.env` à partir de `.env.example`, puis renseigner les valeurs
locales. Ne jamais committer `.env`.

Vérifier Neo4j :

```powershell
python Bin\test_neo4j.py
```

## 10. Commandes courantes

### Construire le graphe technique et documentaire

Neo4j doit être démarré :

```powershell
python GrapheBuilder_v3.py
```

Cette commande peut effectuer de nombreux appels d'embeddings Mistral.

### Démarrer l'application

```powershell
python -m uvicorn api:app --reload
```

Puis ouvrir :

```text
http://127.0.0.1:8000/
```

Une seule instance doit utiliser le port 8000.

### Lancer les tests

Pour éviter les problèmes de cache avec OneDrive :

```powershell
python -m pytest tests -q -p no:cacheprovider
```

### Évaluer le GraphRAG sans réponse finale

```powershell
python evaluate_graphrag.py
```

### Évaluer Neo4j + retrieval + Mistral

```powershell
python evaluate_graphrag.py --with-llm
```

### Tester l'extraction métier sur deux fiches

```powershell
python extraire_tout_graphe_metier.py --limite 2
```

### Extraire toutes les fiches

```powershell
python extraire_tout_graphe_metier.py
```

La commande reprend automatiquement les checkpoints existants. Pour recalculer :

```powershell
python extraire_tout_graphe_metier.py --force
```

### Valider puis importer une proposition métier

Après relecture manuelle :

```powershell
python pipeline_graphe_metier.py valider DataMetier\proposition_globale.json
python pipeline_graphe_metier.py importer DataMetier\proposition_globale.json
```

## 11. Exemple de question et parcours interne

Question :

> Quel est le rôle d'un poste d'aiguillage et quels sont ses liens avec les
> itinéraires, signaux et aiguillages ?

Parcours attendu :

1. résolution de la classe technique `Poste` ;
2. résolution du concept `Poste d'aiguillage` si la couche métier est importée ;
3. récupération des concepts voisins ;
4. récupération des classes Arianes correspondantes ;
5. récupération de `Post.txt` et `Itineraire.txt` ;
6. classement des chunks ;
7. génération d'une réponse Mistral uniquement à partir du contexte ;
8. ajout des sources.

## 12. Sécurité et règles de confiance

### Secrets

- les secrets sont lus depuis `.env` ;
- aucune clé ne doit être codée en dur ;
- une clé anciennement exposée doit être révoquée même si le dépôt est privé.

### Neo4j

- l'agent actif utilise des requêtes déterministes ;
- l'exécuteur générique refuse les écritures ;
- les imports sont réservés aux builders explicites.

### Graphe métier

- Mistral propose, mais ne valide pas ;
- une citation exacte est obligatoire ;
- une proposition reste `A_REVOIR` ;
- l'import ne prend que les éléments `VALIDE` ;
- les avertissements sémantiques doivent être relus par un expert métier.

### Utilisateurs

- les mots de passe ne sont jamais stockés en clair ;
- les conversations sont isolées par propriétaire ;
- les cookies de session sont HttpOnly.

## 13. Limites connues et améliorations prévues

- relier chaque concept et chaque assertion directement au chunk justificatif ;
- produire un rapport des classes/documents introuvables pendant l'import métier ;
- distinguer une assertion métier d'une simple relation par un nœud
  `AssertionMetier` ;
- améliorer la consolidation des synonymes entre plusieurs fiches ;
- faire valider individuellement les concepts et relations au lieu de valider tout
  un fichier d'un coup ;
- mieux reconnaître les relations exprimées dans les tableaux et listes ;
- ajouter une interface de revue des propositions métier ;
- éliminer les doublons historiques de classes ou documents dans les données
  sources ;
- ajouter des métriques de précision, rappel et fidélité des réponses ;
- remplacer progressivement les prototypes de `Bin/` par une archive documentée.

## 13.1 Prototype de reranking machine learning

Le dossier `ml/` contient un prototype optionnel de régression logistique entraîné
avec NumPy. Il apprend à reclasser les chunks candidats après la recherche hybride
et avant la sélection des huit passages transmis à Mistral.

Le modèle est désactivé par défaut. Il est activé uniquement lorsque
`RERANKER_MODEL_PATH` désigne un modèle JSON compatible. En cas d'erreur, le score
de fusion standard reste utilisé. Les commandes et limites sont documentées dans
`ml/README.md`.

## 14. Fichiers à utiliser en priorité

Pour travailler sur l'application actuelle :

```text
XmiToJson.py
GrapheBuilder_v3.py
graphrag_retriever.py
Agent_LG.py
api.py
index.html
pipeline_graphe_metier.py
extraire_tout_graphe_metier.py
graphe_metier_builder.py
evaluate_graphrag.py
tests/
```

Les scripts dans `Bin/` sont historiques et ne doivent pas être confondus avec
les composants actifs.
