# Bilan détaillé des scripts Python du projet AGENT_SNCF

## 1. Vue d'ensemble

Le dépôt contient **34 fichiers Python** représentant environ **5 800 lignes**. Ils se répartissent en cinq ensembles :

1. l'application actuellement utilisée : API, authentification, agent et retrieval GraphRAG ;
2. la construction du métamodèle, des documents et du graphe métier ;
3. l'évaluation et le prototype de reranking par machine learning ;
4. les anciennes versions conservées dans `Bin/` ;
5. les tests automatiques.

Le chemin d'exécution principal est actuellement :

```text
Navigateur / index.html
        ↓ HTTP
api.py
        ↓
Agent_LG.py
        ↓
graphrag_retriever.py
        ↓
Neo4j : métamodèle + documents + graphe métier
        ↓
Mistral : génération de la réponse finale
```

L'historique des utilisateurs et des conversations suit un chemin distinct :

```text
api.py → SQLModel → ariane_coeur.db (SQLite)
```

La construction des données suit ce second pipeline :

```text
XMI/*.txt ──XmiToJson.py──> Data/*.json
Data/*.json + Docs/*.txt ──GrapheBuilder_v3.py──> Neo4j
Docs/*.txt ──pipeline métier──> DataMetier/*.json ──validation/import──> Neo4j
```

## 2. Statut général des fichiers

### Code actif de production

- `api.py`
- `Agent_LG.py`
- `graphrag_retriever.py`
- `GrapheBuilder_v3.py`
- `XmiToJson.py`
- `pipeline_graphe_metier.py`
- `validation_metier.py`
- `extraire_tout_graphe_metier.py`
- `recontroler_graphe_metier.py`
- `selectionner_graphe_metier_prudent.py`
- `graphe_metier_builder.py`
- `importer_pilote_metier.py`

### Outils d'évaluation ou prototypes optionnels

- `evaluate_graphrag.py`
- les quatre scripts du dossier `ml/`

### Code historique ou obsolète

- `app.py`
- tous les scripts du dossier `Bin/`

### Tests

- tous les scripts du dossier `tests/`

---

## 3. Application et agent GraphRAG

### `api.py` — serveur principal de l'application

**Statut : actif, point d'entrée principal.**

Ce fichier crée l'application FastAPI servie par Uvicorn. La commande normale de lancement est :

```powershell
python -m uvicorn api:app --reload
```

#### Responsabilités

- initialise `AgentLG` au démarrage ;
- initialise les tables SQLite avec SQLModel ;
- sert la page `index.html` ;
- expose les routes d'authentification ;
- stocke et recharge les conversations ;
- transmet les questions à l'agent ;
- expose un aperçu en lecture seule du graphe Neo4j pour le frontend ;
- fournit les contrôles de santé de Neo4j.

#### Modèles SQL

- `Utilisateur` : nom, sel et hash de mot de passe ;
- `SessionAuthentification` : session utilisateur avec jeton hashé et expiration ;
- `Conversation` : identifiant, titre et date ;
- `Message` : contenu, rôle, position et conversation ;
- `ProprietaireConversation` : lie une conversation à son utilisateur.

#### Sécurité

Les mots de passe sont dérivés avec un sel aléatoire. Les jetons de session sont également hashés avant stockage. Chaque accès à une conversation passe par `_verifier_proprietaire`, ce qui empêche un utilisateur de lire ou supprimer les conversations d'un autre compte.

#### Routes principales

- `POST /auth/register` : création de compte ;
- `POST /auth/login` : connexion ;
- `POST /auth/logout` : révocation de session ;
- `GET /auth/me` : utilisateur courant ;
- `POST /ask` : question au chatbot avec mémoire de conversation ;
- `GET /conversations` : historique de l'utilisateur ;
- `GET /conversations/{id}/messages` : messages d'une conversation ;
- `DELETE /conversations/{id}` : suppression ;
- `GET /graph?vue=metier` : concepts et relations métier validés ;
- `GET /graph?vue=metamodele` : classes et relations UML ;
- `GET /schema` : aperçu du schéma Neo4j ;
- `GET /health` : état de connexion ;
- `GET /` : interface web.

#### Entrées et sorties

Entrée : requêtes HTTP JSON et cookie de session. Sortie : JSON ou `index.html`. Effets persistants : écrit dans SQLite et, via l'agent, lit Neo4j et appelle Mistral. L'endpoint `/graph` reste en lecture seule.

---

### `Agent_LG.py` — orchestration de l'agent

**Statut : actif.**

`AgentLG` relie Neo4j, le retriever GraphRAG et Mistral.

#### Initialisation

Le constructeur charge :

- `MISTRAL_API_KEY` ;
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` ;
- le modèle de conversation Mistral ;
- le modèle d'embedding `mistral-embed` ;
- une instance de `GraphRAGRetriever`.

Le script refuse de démarrer si les secrets obligatoires ne sont pas présents.

#### Méthode `ask`

1. reçoit la question et les derniers messages de la conversation ;
2. appelle `retriever.retrieve` ;
3. sérialise le résultat contrôlé en contexte JSON ;
4. construit le prompt système ;
5. demande une réponse à Mistral ;
6. masque les références techniques visibles avec `_retirer_sources_visibles` ;
7. transforme les erreurs réseau ou HTTP en messages compréhensibles.

Le prompt impose une réponse directe et courte, interdit les faits absents du contexte et sépare le graphe métier du métamodèle UML.

#### Autres fonctions

- `get_schema_context` : inventaire borné des labels, relations, classes, attributs et documents ;
- `_valider_et_executer` : exécute uniquement des requêtes Cypher en lecture ;
- `close` : ferme le driver Neo4j ;
- `main` : ancien mode terminal interactif, encore utilisable pour tester l'agent sans navigateur.

#### Point d'attention

La génération finale dépend toujours de Mistral. Neo4j peut fonctionner alors que la réponse échoue si le réseau, le proxy ou l'API Mistral est indisponible.

---

### `graphrag_retriever.py` — cœur du retrieval GraphRAG

**Statut : actif, composant central.**

Ce fichier ne génère pas la réponse. Il décide quelles informations de Neo4j doivent être données au LLM.

#### Résolution des entités

- `normaliser` retire accents, casse et sépare le CamelCase ;
- `tokens` extrait les mots significatifs ;
- `_charger_catalogue` met en cache les classes et attributs ;
- `resoudre_classes` compare la question aux noms, descriptions et attributs ;
- `_selectionner_concepts` sélectionne les concepts métier par nom, alias, classe correspondante et tolérance aux petites fautes comme `post`/`poste`.

#### Choix du mode

`determiner_mode` classe la question en :

- `STRUCTURE` : classes, attributs et relations UML ;
- `DOCUMENTAIRE` : procédures et passages textuels ;
- `HYBRIDE` : combinaison des deux.

#### Construction du contexte

- `_construire_sous_graphe` récupère les classes voisines, attributs et relations structurelles ;
- `_construire_graphe_metier` récupère uniquement les `ConceptMetier` et `RELATION_METIER` marqués `valide: true` ;
- `_chercher_preuves_metier` retrouve les chunks documentaires attachés aux relations métier ;
- `_chercher_chunks` combine similarité vectorielle, liens aux classes et éventuellement reranking ML ;
- `retrieve` orchestre l'ensemble, ajoute l'historique récent et retourne un objet contrôlé ;
- `contexte_pour_llm` transforme cet objet en JSON lisible par Mistral.

#### Propriété importante

Le système constitue un GraphRAG parce que la récupération combine le graphe structurel, le graphe métier et les passages documentaires avant la génération. Le LLM n'interroge pas librement toute la base et ne doit pas inventer les relations manquantes.

---

### `app.py` — ancienne API minimale

**Statut : obsolète, ne pas utiliser pour lancer l'application actuelle.**

Ce fichier créait une API FastAPI très simple autour de `GraphAgent` : génération d'une requête Cypher par le LLM, exécution, puis reformulation du résultat.

Il n'offre ni comptes utilisateurs, ni conversations persistantes, ni mémoire, ni retrieval GraphRAG contrôlé. De plus, il importe `mini_agent_neo4j_mistral` depuis la racine alors que ce fichier se trouve maintenant dans `Bin/`. Le point d'entrée actuel est `api.py`.

---

## 4. Construction du métamodèle et des documents

### `XmiToJson.py` — conversion XMI vers JSON

**Statut : actif comme outil de préparation des données.**

Ce script lit les fichiers XMI exportés sous forme de fichiers `.txt` dans `XMI/` et produit un JSON par modèle dans `Data/`.

#### Étapes

1. lecture XML avec `ElementTree` ;
2. extraction des classes, énumérations, attributs et associations ;
3. lecture de la documentation et des multiplicités ;
4. déduplication ;
5. écriture d'une structure JSON stable.

Fonctions importantes : `parse_xmi`, `get_documentation`, `get_multiplicity`, `deduplique` et `read_xmi_file`.

Il ne contacte ni Neo4j ni Mistral. Sa sortie sert d'entrée à `GrapheBuilder_v3.py`.

---

### `GrapheBuilder_v3.py` — import du métamodèle et des documents

**Statut : actif pour construire ou reconstruire la base technique.**

Le builder importe deux familles de données dans Neo4j.

#### Métamodèle

À partir de `Data/*.json`, il crée ou fusionne :

- `Classe` ;
- `Attribut` ;
- `Type` et énumérations ;
- relations `HERITE_DE`, `COMPOSE_DE`, `ASSOCIE_A`, `AGREGE`.

Les méthodes `merge_classe`, `merge_attribut`, `merge_enum` et `add_relation` effectuent des `MERGE` afin de rendre les imports rejouables.

#### Documents

À partir de `Docs/*.txt`, il :

1. crée un nœud `Document` ;
2. découpe le texte en chunks de 800 caractères avec recouvrement de 100 ;
3. calcule un embedding Mistral par chunk ;
4. crée les nœuds `Chunk` ;
5. relie les documents/chunks aux classes détectées.

#### Effets

Le script écrit massivement dans Neo4j et appelle l'API d'embeddings Mistral. Il doit donc être utilisé pour une reconstruction maîtrisée, pas à chaque démarrage de l'application.

---

## 5. Pipeline du graphe métier

### `pipeline_graphe_metier.py` — extraction, validation et import

**Statut : actif, pipeline métier principal.**

Ce fichier propose trois commandes :

```powershell
python pipeline_graphe_metier.py extraire Docs\Post.txt
python pipeline_graphe_metier.py valider fichier.json --confirmer-relecture
python pipeline_graphe_metier.py importer fichier.json
```

#### Extraction

- `charger_catalogue` lit les classes Arianes présentes dans Neo4j ;
- `classes_candidates` repère les classes susceptibles d'apparaître dans un passage ;
- `decouper_document` conserve les numéros de lignes ;
- `prompt_extraction` demande au LLM des concepts, relations, preuves, conditions et classes correspondantes ;
- `extraire_json_message` sécurise la récupération du JSON produit par Mistral ;
- `valider_extraction` applique les contrôles locaux ;
- `consolider` fusionne les morceaux sans perdre les preuves distinctes.

#### Philosophie

Une extraction reçoit le statut `A_REVOIR`. Le LLM propose des relations, mais il ne les déclare jamais automatiquement vraies. Les relations rejetées restent conservées avec leurs motifs.

#### Import

`filtrer_valides` ne transmet au builder que les concepts et relations explicitement `VALIDE`. Cette séparation empêche une proposition brute d'entrer accidentellement dans le contexte utilisé par l'agent.

---

### `validation_metier.py` — règles locales de contrôle

**Statut : actif, garde-fou partagé.**

Ce module ne fait aucun appel LLM. Il contient les règles déterministes utilisées par le pipeline, le recontrôle et l'import.

#### Fonctions

- `categorie_concept` estime une catégorie contrôlée : équipement, localisation, document, acteur, caractéristique, etc. ;
- `normaliser_commande` traite certains cas de voix passive ;
- `corriger_relation` applique uniquement les corrections sémantiques explicitement codées ;
- `controler_relation` vérifie les concepts, le prédicat, la direction, la citation, la négation et les incompatibilités ;
- `verifier_import` refuse tout import contenant des statuts non validés, des motifs de rejet ou des auto-relations.

#### Rôle architectural

Ce fichier garantit que les mêmes règles sont appliquées quelle que soit la commande utilisée. Il évite de dupliquer des contrôles contradictoires dans plusieurs scripts.

---

### `extraire_tout_graphe_metier.py` — extraction des 29 fiches

**Statut : actif comme traitement par lot.**

Il découvre tous les fichiers `Docs/*.txt`, appelle `extraire_document` pour chacun et écrit un checkpoint JSON par fiche. Il peut reprendre une extraction interrompue sans retraiter les fichiers déjà présents.

Entrées : dossier `Docs`, catalogue des classes et clé Mistral. Sorties : `DataMetier/propositions/*.metier.json` et une proposition consolidée. Il n'importe rien dans Neo4j.

Le délai entre appels réduit les risques de surcharge ou de limitation de l'API.

---

### `recontroler_graphe_metier.py` — recontrôle hors ligne

**Statut : actif.**

Ce script relit les checkpoints existants sans appeler Mistral et sans modifier Neo4j.

#### Contrôles

- vérifie que la citation existe réellement dans les lignes annoncées ;
- refuse les chemins sortant du corpus `Docs/` ;
- recalcule les catégories ;
- applique les corrections déterministes de `validation_metier.py` ;
- sépare relations conservées et relations rejetées ;
- produit un rapport avec compteurs et empreintes SHA-256.

Les originaux restent intacts. Les sorties corrigées sont écrites dans un nouveau dossier, par exemple `DataMetier/corrections_v2/`.

---

### `selectionner_graphe_metier_prudent.py` — sélection automatique conservatrice

**Statut : actif, ajouté faute de validation métier experte disponible.**

Le script lit la proposition consolidée corrigée et retient seulement les relations qui :

- ne sont pas rejetées ;
- n'ont aucun motif de rejet ;
- n'ont pas d'avertissement sémantique sur le prédicat, la négation ou la composition ;
- peuvent conserver uniquement l'avertissement indiquant que la catégorie d'un concept reste à préciser.

Il marque cette sélection `VALIDE` avec la méthode `AUTO_PRUDENTE_PREUVE_DOCUMENTAIRE`, limite les concepts à ceux réellement utilisés et écrit `DataMetier/selection_auto_prudente.json`.

Ce mécanisme a permis d'importer 114 relations candidates prudentes, mais il ne remplace pas une expertise ferroviaire. Les relations exclues ne sont pas supprimées.

---

### `graphe_metier_builder.py` — écriture contrôlée dans Neo4j

**Statut : actif.**

Ce builder reçoit une définition JSON déjà validée. Avant toute écriture, `charger_definition` contrôle les identifiants et `verifier_import` contrôle les statuts.

#### Nœuds et relations créés

- `ConceptMetier` avec nom, alias, description, domaine, catégorie et `valide: true` ;
- `REPRESENTE_PAR` vers une `Classe` Arianes ;
- `DOCUMENTE_PAR` vers un `Document` ;
- `RELATION_METIER` avec type, preuve, document, lignes, chunks, condition et méthode de validation ;
- `ETAYE_PAR` vers les chunks de preuve.

Les relations utilisent un `MERGE` incluant leur preuve. Deux preuves différentes du même triplet peuvent donc être conservées sans écrasement.

Ce script écrit dans Neo4j. Il ne fait ni extraction LLM ni validation sémantique.

---

### `importer_pilote_metier.py` — pilote Poste d'aiguillage

**Statut : actif mais spécifique au premier pilote.**

Il prépare `poste_aiguillage.json`, vérifie les citations dans `Post.txt`, attache les identifiants des chunks correspondants et contrôle les relations et conditions avant import.

Ce script a servi à importer le premier sous-graphe métier fiable : poste, signaux, appareils de voie, ligne, PK, PAI et PRCI. Pour les imports globaux, `selectionner_graphe_metier_prudent.py` et `pipeline_graphe_metier.py importer` sont désormais plus généraux.

---

## 6. Évaluation du GraphRAG

### `evaluate_graphrag.py` — campagne de tests fonctionnels

**Statut : actif comme outil d'évaluation, pas utilisé par l'application en direct.**

Il charge des questions d'évaluation, exécute le retrieval et compare les résultats à des attentes : classes racines, relations, sources ou chunks attendus.

Avec `--with-llm`, il appelle également `AgentLG` pour enregistrer la réponse finale de Mistral. Sans cette option, il évalue seulement le retrieval, ce qui coûte moins cher et isole mieux les erreurs.

La sortie `evaluation_graphrag.json` contient la date, le nombre de réussites, le taux de réussite, les temps et le détail de chaque cas. Le code de sortie vaut zéro seulement si tous les cas réussissent, ce qui permet une future utilisation en intégration continue.

---

## 7. Prototype de machine learning

### `ml/__init__.py`

**Statut : actif comme marqueur de package.**

Il permet d'importer les modules avec `ml.reranker`, `ml.train_reranker`, etc. Il ne contient aucune logique métier.

### `ml/reranker.py`

**Statut : prototype fonctionnel et optionnel.**

Il définit `LinearReranker`, un modèle linéaire léger qui réordonne les chunks après le retrieval initial.

`extraire_features` calcule notamment des signaux de similarité, de recouvrement lexical et de provenance. Le modèle calcule une probabilité, puis `rerank` trie les passages. Il peut être sauvegardé et rechargé en JSON.

`GraphRAGRetriever` ne le charge que si `RERANKER_MODEL_PATH` est défini. Sans cette variable, le classement standard reste utilisé.

### `ml/build_dataset_from_evaluation.py`

**Statut : outil de préparation de données.**

Il transforme `evaluation_graphrag.json` en exemples JSONL. Les passages correspondant aux sources attendues deviennent des exemples positifs ; les autres deviennent négatifs. Il s'agit de faible supervision, pas d'annotations expertes.

### `ml/train_reranker.py`

**Statut : outil d'entraînement expérimental.**

Il charge le JSONL, standardise les variables, entraîne une régression logistique avec NumPy, calcule des métriques élémentaires et sauvegarde le modèle.

### `ml/evaluate_reranker.py`

**Statut : outil d'évaluation expérimentale.**

Il effectue une validation croisée groupée par question et compare le reranker au score de fusion initial. Les métriques portent sur le classement des bons chunks. Ce script sert à déterminer si le modèle apporte réellement quelque chose avant activation.

#### Limite commune du dossier ML

Le dataset actuel est petit et dérivé de règles. Le prototype démontre la mécanique, mais ses résultats ne suffisent pas encore pour affirmer une amélioration généralisable.

---

## 8. Anciennes versions dans `Bin/`

Le dossier `Bin/` sert d'archive de développement. Aucun de ces fichiers n'est importé par l'application actuelle.

### `Bin/Agent_v3.py`

Ancien agent Text-to-Cypher. Le LLM génère une requête, le script la nettoie, la valide, l'exécute puis reformule les résultats. Il sérialise les objets Neo4j `Node`, `Relationship` et `Path`. Il ne possède pas le retrieval hybride actuel et laisse davantage de responsabilité au LLM.

### `Bin/mini_agent_neo4j_mistral.py`

Version très proche de `Agent_v3.py`, conçue comme agent minimal Neo4j + Mistral. Elle est utilisée conceptuellement par l'ancien `app.py`, mais son emplacement rend cet import ancien invalide depuis la racine.

### `Bin/AgentGraphRag.py`

Premier prototype RAG vectoriel avec `Neo4jVector` et LangChain. Il construit une chaîne `retriever → prompt → Mistral`. Il s'appuie surtout sur la recherche vectorielle de documents et ne maîtrise pas les relations du graphe métier comme le retriever actuel.

### `Bin/build_ariane_graph.py`

Ancien builder UML codé manuellement. La classe `UMLGraphBuilder` crée gammes, classes, énumérations, attributs et relations. Les données sont inscrites directement dans le code, ce qui rend les évolutions difficiles.

### `Bin/GrapheBuilder_V1.py`

Extension volumineuse du premier builder manuel. Elle contient davantage de classes et relations Arianes codées en dur. Elle a servi de squelette initial avant la conversion XMI/JSON.

### `Bin/GrapheBuilder_v2.py`

Version manuelle la plus complète, couvrant plusieurs gammes du modèle Arianes. Elle constitue une référence historique utile, mais ses 1 141 lignes de données codées en dur sont remplacées par `XmiToJson.py` et `GrapheBuilder_v3.py`.

### `Bin/SNCFGraphBuilder.py`

Builder d'un autre graphe orienté données ouvertes SNCF : lignes, gares, quais, chantiers et circuits. Il lit des fichiers JSON et écrit ces objets dans Neo4j. Ce graphe de données réelles n'est pas le métamodèle Arianes ni le graphe métier documentaire actuel.

### `Bin/sncf_client.py`

Client HTTP pour l'API Open Data SNCF. Il fournit une méthode par dataset : ponts, quais, gares, passages à niveau, vitesses, cantonnement, KVB, radio, etc. Il appelle `ressources.data.sncf.com` avec `requests` et un timeout. Il n'est relié à aucun pipeline actif.

### `Bin/test_neo4j.py`

Petit script manuel qui charge `.env`, ouvre le driver Neo4j, appelle `verify_connectivity`, affiche « Connexion Neo4j OK » puis ferme le driver. Il reste pratique pour un diagnostic rapide, mais ne constitue pas un test pytest.

### `Bin/testatr.py`

Fragment de test PySpark créant un DataFrame avec Alice, Bob et Charlie. La variable `spark` n'est pas initialisée dans le fichier. Ce script est sans rapport avec l'application et peut être considéré comme un brouillon.

---

## 9. Tests automatisés

La commande de validation globale est :

```powershell
python -m pytest -q -p no:cacheprovider
```

### `tests/test_agent_security.py`

Teste le refus des requêtes Cypher en écriture, les débuts de requêtes interdits, `LOAD CSV`, la transmission de l'historique, le prompt de réponse directe et le masquage des sources.

### `tests/test_api_validation.py`

Teste la conversion des UUID, le rejet des UUID invalides et la réponse de santé lorsque Neo4j est indisponible.

### `tests/test_auth_and_ownership.py`

Crée une base SQLite en mémoire et vérifie l'inscription, le cookie de session, l'isolation des conversations entre Alice et Bob et la révocation à la déconnexion.

### `tests/test_graphrag_retriever.py`

Teste la normalisation, le CamelCase, la résolution des classes courtes, les modes de retrieval et la sélection du concept `poste_aiguillage`, y compris la faute `post`.

### `tests/test_pipeline_graphe_metier.py`

Teste le découpage avec conservation des lignes, les classes candidates, le rejet d'une preuve absente, les statuts `A_REVOIR`, la voix passive, le filtrage avant import et la découverte des fiches `.txt`.

### `tests/test_corrections_metier.py`

Teste les corrections sémantiques contrôlées, la non-inversion sans preuve, la négation, les auto-relations, la sécurité des chemins, la conservation de preuves multiples et le refus d'import avant validation.

### `tests/test_graphe_metier_builder.py`

Contrôle la cohérence structurelle de la définition du pilote Poste d'aiguillage.

### `tests/test_pilote_metier.py`

Vérifie les preuves et conditions du pilote, la récupération des chunks de preuve et le fonctionnement sans embedding pour une question structurelle.

### `tests/test_selection_prudente.py`

Teste les règles de la sélection automatique conservatrice et vérifie que seuls les concepts utilisés par les relations retenues sont exportés.

### `tests/test_ml_reranker.py`

Teste la dimension des features, l'apprentissage sur un petit signal séparable, le réordonnancement et la construction du dataset par faible supervision.

---

## 10. Scripts à utiliser selon le besoin

### Lancer l'application

```powershell
python -m uvicorn api:app --reload
```

### Reconstruire le métamodèle depuis les XMI

```powershell
python XmiToJson.py
python GrapheBuilder_v3.py
```

La deuxième commande importe aussi les documents et appelle Mistral pour les embeddings.

### Extraire toutes les fiches métier

```powershell
python extraire_tout_graphe_metier.py
```

### Recontrôler les propositions sans appel externe

```powershell
python recontroler_graphe_metier.py --output-dir DataMetier/corrections_nouvelle_version
```

### Produire puis importer la sélection prudente

```powershell
python selectionner_graphe_metier_prudent.py
python pipeline_graphe_metier.py importer DataMetier/selection_auto_prudente.json
```

### Évaluer le retrieval

```powershell
python evaluate_graphrag.py
```

Ajouter `--with-llm` uniquement si l'on souhaite aussi tester les réponses Mistral.

---

## 11. Recommandations de nettoyage

1. Conserver `Bin/` comme archive, mais ajouter un fichier `Bin/README.md` indiquant explicitement que ces scripts ne sont plus exécutés.
2. Déplacer ou supprimer `app.py` pour éviter de lancer le mauvais serveur.
3. Supprimer `Bin/testatr.py`, qui est un fragment PySpark sans rapport avec le projet.
4. Ajouter un fichier de dépendances versionnées (`requirements.txt` ou `pyproject.toml`).
5. Séparer à terme `api.py` en modules `auth`, `conversations`, `graph` et `schemas` si le projet continue à grandir.
6. Ajouter des tests dédiés à `/graph` et au format des réponses envoyées au frontend.
7. Conserver dans Neo4j et dans les JSON la méthode de validation de chaque relation pour distinguer relecture humaine, pilote et validation automatique prudente.

## 12. Conclusion

Le projet n'est plus un simple agent Text-to-Cypher. Il possède désormais :

- un métamodèle UML importé depuis XMI ;
- un corpus documentaire découpé et indexé ;
- une couche de concepts et relations métier sourcés ;
- un retrieval GraphRAG déterministe ;
- une génération finale par Mistral ;
- une API avec comptes et mémoire de conversation ;
- une visualisation Neo4j dans le navigateur ;
- une suite de tests ;
- un prototype de reranking ML optionnel.

La principale dette technique vient des nombreuses versions historiques et de la concentration de plusieurs responsabilités dans `api.py` et `index.html`. Le cœur actif est néanmoins identifiable et couvert par des tests.
