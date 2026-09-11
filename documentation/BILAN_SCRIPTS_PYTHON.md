# Inventaire des scripts 

## Application et retrieval

- `api.py` : expose les routes FastAPI de connexion, conversations, messages, questions et visualisation. Contrôle les données reçues et l’appartenance des conversations à l’utilisateur. SQLite conserve les comptes et échanges. Un succès HTTP ne garantit pas la justesse du contenu généré.
- `arianes/agent.py` : orchestre une question, obtient le contexte du retriever et prépare la réponse. Il gère les fournisseurs, contraintes de génération et erreurs. Certaines réponses UML sont formatées directement ; ne pas présenter chaque réponse comme une génération libre du LLM. Les anciennes fonctions de secours présentes dans le fichier ne prouvent pas qu’un fallback est actif dans le parcours courant.
- `arianes/retrieval.py` : classe la demande, résout les noms d’entités, interroge UML, documents ou relations métier, puis assemble les preuves. Il contient aussi la recherche de chemins et le classement des passages. Les chemins UML peuvent être parcourus dans les deux sens, sans changer l’orientation stockée des relations.
- `arianes/paths.py` : centralise les chemins de données à partir de la racine du projet. Il ne déplace ni ne transforme les données.
- `arianes/evaluation.py` : exécute des scénarios et produit un rapport de retrieval ; la génération est optionnelle. Même sans génération, une recherche vectorielle peut appeler l’API d’embeddings.
- Les fichiers `__init__.py` déclarent les packages ; ce ne sont pas des étapes d’import Neo4j.

Le parcours de l’utilisateur et les responsabilités sont détaillés dans le [guide 07](07_RETRIEVAL_ET_APPLICATION.md).

## Préparation UML et documentaire

### `arianes/pipelines/xmi_to_json.py`

Lit les exports XMI, construit une correspondance entre identifiants et noms, puis extrait classes, attributs, types et relations vers les JSON UML. Cette conversion est locale. Elle ne crée pas les nœuds Neo4j et ne produit pas le graphe métier issu du texte. Les propriétés absentes du XMI ne sont pas reconstituées par magie. Voir le [guide 02](02_SOURCES_ET_UML.md).

### `arianes/graph/uml_builder.py`

Lit les JSON UML et crée les objets et relations correspondants dans Neo4j. Il traite aussi les fiches documentaires : documents, passages découpés, embeddings et index. Ce script combine donc deux responsabilités et peut appeler Mistral même si son nom évoque seulement UML. `MERGE` limite certains doublons, mais ne garantit pas une synchronisation complète après suppression ou modification d’une source. Voir les [guides 02](02_SOURCES_ET_UML.md) et [03](03_DOCUMENTS_ET_INDEXATION.md).

## Extraction métier

### `arianes/pipelines/extraction_metier.py`

Charge le catalogue des classes UML, découpe une fiche et sélectionne des classes candidates par rapprochement lexical. Envoie passage et catalogue réduit au LLM pour obtenir un JSON de concepts et relations accompagnés de preuves. Contrôle et consolide la sortie. Ses sous-commandes de validation et d’import ont des effets distincts : une extraction n’est pas un import. L’import de ce parcours filtre les relations validées, contrairement au builder général qui accepte aussi les probables.

### `arianes/pipelines/extraction_globale.py`

Orchestre l’extraction de plusieurs fiches en appelant le module précédent. Gère les sorties par document, signatures de reprise, échecs et agrégation des extractions réussies. La reprise se fait au niveau du document ; elle ne signifie pas que chaque morceau d’un document interrompu est conservé séparément. Voir le [guide 04](04_EXTRACTION_METIER.md).

## Contrôle et sélection

### `arianes/pipelines/validation_metier.py`

Contient les règles locales de normalisation et de contrôle : concepts existants, types autorisés, auto-relations, preuve textuelle, compatibilité du prédicat, direction, catégories et conditions. Le contrôleur déclare la version 4. Il attribue un niveau documentaire ; il ne remplace pas une expertise métier. Certaines corrections sont spécifiques, et la confirmation automatique du sens reste limitée.

### `arianes/pipelines/recontrole_metier.py`

Reprend les propositions existantes avec leurs véritables passages sources et applique les règles actuelles sans nouvel appel d’extraction au LLM. Produit de nouvelles propositions, une agrégation et un rapport de contrôle. Exige un répertoire de sortie nouveau : ne pas le faire pointer sur un ancien résultat à écraser.

### `arianes/pipelines/generer_pilotes.py`

Produit un pilote documentaire par fiche à partir des propositions recontrôlées. Conserve les niveaux utiles, rattache les métadonnées documentaires et produit un bilan. Il n’importe rien dans Neo4j. Un pilote sur disque ne prouve ni une relecture humaine ni sa présence en base.

### `arianes/pipelines/selection_prudente.py`

Construit une sélection documentaire globale à partir du JSON agrégé. Conserve les éléments admissibles et leur niveau de validation. Ce script n’est pas un modèle ML entraîné ni un arbitre de vérité ferroviaire. Les chemins par défaut et certaines chaînes de métadonnées portent encore des noms historiques V3 : utiliser des entrées et sorties explicites.

Voir le [guide 05](05_VALIDATION_ET_PILOTES.md) pour les critères, limites et commandes enchaînées.

## Import et maintenance métier

### `arianes/graph/metier_builder.py`

Importe une définition métier dans Neo4j : concepts, relations et raccordements aux classes, documents et chunks disponibles. Accepte les niveaux `VALIDE` et `PROBABLE`, en conservant leur distinction. Contrôle la structure, mais ne refait pas une expertise complète de chaque preuve. Une correspondance documentaire absente peut laisser un raccordement incomplet.

### `arianes/pipelines/import_pilote.py`

Parcours spécialisé pour le fichier pilote Post fixé par le code. Effectue un précontrôle de correspondances en base et n’importe qu’avec l’option prévue. Ce n’est pas le lanceur générique pour toutes les fiches.

### `arianes/pipelines/normalisation_metier.py`

Recherche les doublons de concepts selon ses règles. Le mode de diagnostic permet de voir les regroupements envisagés ; le mode d’application fusionne des éléments et supprime les doublons. La sauvegarde produite n’est pas une sauvegarde complète de Neo4j ni une restauration testée. Contrôler le plan avant application.

Voir le [guide 06](06_IMPORT_ET_PROVENANCE.md).

## Prototype ML optionnel

- `ml/reranker.py` : calcule les caractéristiques et scores d’un reranker léger, avec chargement de paramètres. Ce n’est ni le LLM ni le moteur d’embeddings.
- `ml/build_dataset_from_evaluation.py` : transforme un rapport d’évaluation en exemples d’apprentissage ; les labels dérivés des documents attendus restent faibles.
- `ml/train_reranker.py` : apprend des poids sur les exemples et écrit un modèle JSON.
- `ml/evaluate_reranker.py` : mesure le classement sur un jeu d’exemples. Une mesure sur les données d’apprentissage ne démontre pas une généralisation.

Le [guide 08](08_TESTS_EXPLOITATION_ML.md) précise les commandes et les limites de ce prototype.

## Tests

Les onze fichiers de tests actuels sont :

- `test_agent_security.py` : garde-fous et traitement des erreurs de l’agent.
- `test_api_validation.py` : validation des requêtes API.
- `test_audit_regressions.py` : régressions ciblées relevées lors des audits.
- `test_auth_and_ownership.py` : authentification et isolation des conversations.
- `test_corrections_metier.py` : corrections et contrôles métier.
- `test_graphe_metier_builder.py` : comportement du builder métier.
- `test_graphrag_retriever.py` : routage, résolution, retrieval et chemins.
- `test_ml_reranker.py` : prototype de classement.
- `test_pilote_metier.py` : règles et contrôles du pilote.
- `test_pipeline_graphe_metier.py` : extraction et structure des propositions.
- `test_selection_prudente.py` : sélection documentaire.


## Ce qui n’est pas un script Python courant

`index.html` contient l’interface ; `.env` contient la configuration sensible ; les JSON de données sont des entrées ou sorties ; `legacy/` conserve des prototypes historiques. Ne pas lancer ces derniers pour remplacer les commandes documentées sans analyse de leurs effets.
