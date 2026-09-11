# Script oral détaillé — Architecture et pipelines du GraphRAG Arianes

Ce texte est conçu comme un discours de 35 à 45 minutes, auquel on peut ajouter une démonstration de 10 à 15 minutes. Les passages entre crochets sont des indications pour la personne qui présente et ne doivent pas nécessairement être lus à voix haute.

## 1. Introduction — le problème traité

[Afficher la page de titre, puis une vue très simple : documents + UML → Neo4j → chatbot.]

Bonjour à toutes et à tous.

Je vais vous présenter le travail réalisé autour d’un assistant conversationnel spécialisé dans le référentiel Arianes. L’objectif n’est pas simplement de brancher un modèle de langage sur des documents. Le véritable problème est de permettre à l’utilisateur d’interroger plusieurs formes de connaissance qui ne se représentent pas de la même manière.

La première forme de connaissance est le métamodèle UML Arianes. Il décrit la structure du système : les classes, leurs attributs, leurs types, les héritages, les compositions, les agrégations et les associations. Par exemple, si je demande quels sont les attributs de la classe `Ligne`, ou quelles classes héritent de `NoeudDeLigne`, la réponse doit venir du modèle UML et non d’un texte libre.

La deuxième forme est documentaire. Elle correspond aux fiches de procédure et aux descriptions métier. Ces fiches expliquent comment créer un itinéraire, ce qu’est un détecteur de boîtes chaudes, quelles règles doivent être respectées, quelles conditions existent et quelles exceptions sont prévues. Ici, une structure UML ne suffit pas : il faut retrouver les bons passages du document.

La troisième forme est la connaissance métier relationnelle. Une fiche peut exprimer qu’un signal est commandé par un poste, qu’un poste est localisé sur une ligne ou qu’un objet est rattaché à un autre. Ces relations ne sont pas forcément des associations UML. Elles expriment le fonctionnement ferroviaire décrit dans les documents. Une couche métier séparée a donc été ajoutée.

Le système doit répondre à ces trois familles sans les confondre. C’est essentiel : demander les sous-classes UML de `NœudDeLigne` n’est pas la même chose que demander comment fonctionne un nœud de ligne dans une fiche. De même, un chemin UML entre deux classes et un chemin métier entre deux concepts sont deux calculs différents.

Le projet est donc un GraphRAG contrôlé : le graphe et les documents fournissent les faits, le retriever choisit les bonnes sources, et le LLM formule la réponse. Le LLM n’est pas autorisé à inventer librement le graphe ou une requête Cypher.

## 2. Vue générale de l’architecture

[Afficher le diagramme d’architecture. Suivre les flèches de gauche à droite.]

L’architecture comporte cinq blocs.

Le premier bloc contient les sources : les exports XMI du modèle UML et les 29 fiches documentaires au format texte.

Le deuxième bloc contient les pipelines de préparation. Le XMI est converti en JSON. Les documents sont découpés en chunks et vectorisés. Un autre pipeline analyse les mêmes documents pour proposer des concepts et des relations métier.

Le troisième bloc est Neo4j. C’est la base de connaissances. Elle contient côte à côte, mais sans les confondre, le graphe UML, les documents et leurs chunks, ainsi que la couche métier.

Le quatrième bloc est le moteur GraphRAG. Il analyse la question, détermine le type de recherche nécessaire, résout les entités, exécute des requêtes Neo4j déterministes et prépare un contexte borné.

Le cinquième bloc est l’application : l’agent choisit le fournisseur sélectionné par l’utilisateur, envoie le contexte au modèle lorsque c’est nécessaire, puis FastAPI et l’interface web affichent la réponse et éventuellement un schéma. SQLite conserve les utilisateurs, les sessions et les conversations. Neo4j conserve la connaissance ; SQLite conserve l’état conversationnel de l’application.

On peut résumer le flux principal ainsi :

```text
XMI ──> JSON UML ──> graphe UML ───────────────┐
                                                │
Fiches texte ──> documents + chunks + vecteurs ├──> retriever ──> agent ──> API ──> interface
                                                │
Fiches texte ──> extraction + contrôle métier ─> graphe métier
```

## 3. Organisation actuelle du dépôt

[Afficher l’arborescence du projet.]

Le dépôt a été réorganisé pour séparer le code, les données, les tests et les anciens prototypes.

À la racine, `api.py` est le point d’entrée serveur et `index.html` est l’interface du chatbot.

Le package `arianes` contient le code actif. `agent.py` orchestre la réponse et les fournisseurs de LLM. `retrieval.py` contient le cœur du GraphRAG. `paths.py` centralise les chemins afin que les commandes fonctionnent quel que soit le dossier courant.

Dans `arianes/graph`, `uml_builder.py` construit les couches UML et documentaire, tandis que `metier_builder.py` importe la couche métier contrôlée.

Dans `arianes/pipelines`, on trouve toute la chaîne hors ligne : conversion XMI, extraction métier, recontrôle, classification, génération des pilotes et import.

Le dossier `project_data` contient les données. `uml` contient actuellement 44 fichiers JSON issus du modèle. `procedures` contient 29 fiches texte. `metier` contient les propositions, les corrections V3, les pilotes par document et la sélection globale.

Le dossier `tests` contient les tests automatisés. Le dossier `ml` contient un prototype optionnel de reranking, qui n’est pas indispensable au fonctionnement courant. `legacy` contient les anciens essais ; il ne faut pas les confondre avec le chemin de production.

## 4. Pipeline structurel : du XMI au graphe UML

### 4.1 Le rôle de `xmi_to_json.py`

[Montrer un extrait XMI, puis un JSON plus lisible.]

Le XMI est un format XML d’échange de modèles. Il contient beaucoup d’identifiants techniques et de balises imbriquées. L’interroger directement serait difficile et fragile. Le premier pipeline transforme donc chaque export XMI en un JSON normalisé.

La fonction `parse_xmi` parcourt le document XML. Elle identifie les classes, leurs identifiants, leur documentation et leur caractère abstrait. Elle extrait ensuite les attributs, leur type, leur valeur par défaut et leur multiplicité. Elle repère également les énumérations et leurs valeurs.

Les généralisations deviennent des relations d’héritage. Les associations sont analysées avec leurs rôles et cardinalités. Les fonctions `get_documentation`, `est_une_enumeration` et `get_multiplicity` isolent ces traitements afin de rendre le parseur plus compréhensible.

La fonction `deduplique` traite les répétitions présentes dans certains exports. Le résultat final sépare quatre collections principales : classes, énumérations, généralisations et relations. Cette étape ne crée encore rien dans Neo4j ; elle produit une représentation intermédiaire vérifiable et rejouable.

### 4.2 Le rôle de `uml_builder.py`

Le builder lit les 44 JSON normalisés et les importe dans Neo4j.

`create_constraints` installe les contraintes d’unicité et les index utiles. C’est important pour éviter qu’une relance du pipeline ne crée volontairement les mêmes objets plusieurs fois.

`merge_classe` crée ou met à jour un nœud `Classe`. `merge_attribut` crée l’attribut, son type, puis la relation entre la classe et l’attribut. `merge_enum` construit les énumérations et leurs valeurs.

`add_relation` n’accepte que les relations structurelles prévues : héritage, composition, agrégation et association. Le rôle et la cardinalité sont conservés comme propriétés lorsque l’information existe.

Le choix de `MERGE` rend le pipeline idempotent : si les mêmes données sont réimportées, Neo4j cherche l’objet existant avant de le créer. Cela ne résout pas automatiquement les incohérences sémantiques des sources, mais évite les duplications liées à une simple relance.

Le graphe UML obtenu répond aux questions déterministes. Par exemple, pour chercher un chemin de `HabillageOriente` vers `Ligne`, le retriever parcourt uniquement les relations structurelles dans le sens enregistré. Il ne retourne pas un chemin inversé artificiellement.

## 5. Pipeline documentaire : des fiches aux chunks indexés

[Afficher une fiche texte, son découpage, puis plusieurs nœuds Chunk dans Neo4j.]

Le même `uml_builder.py` charge également les fiches contenues dans `project_data/procedures`.

`merge_document` crée un nœud `Document`. La fiche est ensuite découpée en passages plus petits. Ce découpage est indispensable : envoyer les 29 documents complets à chaque question serait trop long, coûteux et peu précis.

Pour chaque passage, un embedding est calculé. Un embedding est une représentation numérique du sens du texte. Deux textes proches sémantiquement doivent produire des vecteurs proches, même s’ils n’utilisent pas exactement les mêmes mots.

`merge_chunk` enregistre le texte, sa position et son vecteur dans un nœud `Chunk`, puis crée `APPARTIENT_A` vers son document. `lier_document_a_classe` essaie de créer un lien `DECRIT` entre la fiche et la classe UML correspondante.

Deux mécanismes de recherche sont complémentaires. L’index vectoriel retrouve des passages sémantiquement proches. L’index plein texte retrouve les mots et expressions exacts. Le retriever fusionne ensuite les classements. Cela permet, par exemple, de retrouver à la fois le terme exact `KVB` et une explication formulée avec des mots légèrement différents.

Il faut bien distinguer l’embedding et le LLM. L’embedding sert à sélectionner les passages ; le LLM sert à rédiger la réponse. Dans la configuration actuelle, les embeddings peuvent fonctionner alors que l’API de génération d’un fournisseur atteint une limite 429.

## 6. Pipeline de construction du graphe métier

[Afficher la chaîne : fiche → morceaux → candidats → extraction JSON → contrôle → pilote → import.]

Cette partie répond à une difficulté importante. Les relations UML décrivent la structure du modèle, mais elles ne suffisent pas pour représenter toutes les règles exprimées dans les fiches. Il faut donc extraire une couche de concepts métier.

Le pipeline ne considère jamais la sortie brute du LLM comme une vérité. Il sépare proposition, contrôle documentaire, sélection et import.

### 6.1 `extraction_metier.py` : extraction contrôlée d’une fiche

La fonction `charger_catalogue` lit les JSON UML et construit un catalogue des classes connues. Ce catalogue sert de repère, mais un concept métier reste distinct d’une classe UML.

`decouper_document` partage une fiche en morceaux de taille bornée et conserve les numéros de lignes. Ces numéros sont essentiels pour vérifier ensuite les preuves.

Pour chaque morceau, `classes_candidates` compare les termes du passage aux noms et descriptions des classes UML. Elle propose au LLM une liste limitée de classes plausibles. Cela réduit l’espace de recherche et évite de lui transmettre tout le métamodèle.

`prompt_extraction` construit une instruction stricte. Le LLM doit retourner un JSON avec des concepts, des relations, une citation exacte, le document et les lignes. Il doit employer des prédicats autorisés. Son rôle est celui d’un extracteur de candidats, pas celui d’un validateur.

`extraire_json_message` nettoie la réponse du modèle et récupère l’objet JSON, même si le modèle a ajouté des délimiteurs Markdown.

`valider_extraction` effectue les contrôles locaux immédiats : la source et la cible doivent exister, une auto-relation injustifiée est refusée, le type doit être autorisé et la citation doit apparaître dans le passage. Les erreurs certaines sont bloquantes ; une ambiguïté sémantique peut être conservée avec avertissement.

`consolider` fusionne les extractions de tous les morceaux d’une fiche. Il déduplique les concepts et les relations et regroupe leurs preuves.

`extraire_document` orchestre tout ce traitement pour une fiche complète. Les commandes `extraire`, `valider` et `importer` exposent les différentes phases, mais l’import ne doit intervenir qu’après contrôle.

### 6.2 `extraction_globale.py` : traitement des 29 fiches

Ce script découvre automatiquement tous les fichiers texte. Il exécute l’extraction fiche par fiche et écrit un checkpoint `.metier.json` après chaque document.

Le checkpoint est important pour deux raisons. Premièrement, une panne réseau ou une interruption ne fait pas perdre les fiches déjà traitées. Deuxièmement, chaque proposition peut être inspectée indépendamment.

Le script sait reprendre les résultats présents et propose une option de recalcul forcé. À la fin, il consolide les propositions dans un fichier global. À ce stade, rien ne doit être automatiquement écrit dans Neo4j.

### 6.3 `validation_metier.py` : règles locales de cohérence

Ce fichier contient la logique de normalisation et de classification des relations.

`categorie_concept` attribue une catégorie générale au concept. `normaliser_commande` traite notamment les formulations passives. Par exemple, « le signal est commandé par le poste » doit produire `Signal → EST_COMMANDE_PAR → Poste`, sans inverser le sens grammatical.

`corriger_relation` applique des corrections identifiées et traçables. `controler_relation` vérifie la présence des concepts, le prédicat, la citation, la compatibilité générale et les règles bloquantes. Le résultat reçoit un statut et conserve les motifs ou corrections.

Enfin, `verifier_import` exécute les contrôles minimaux avant toute écriture en base.

### 6.4 `recontrole_metier.py` : second contrôle hors ligne

Le recontrôle relit les checkpoints sans appeler le LLM et sans modifier Neo4j.

`lire_passage` ouvre uniquement un document appartenant au corpus autorisé. Le chemin est vérifié pour empêcher une référence vers un fichier extérieur. Les numéros de lignes sont contrôlés.

Chaque relation est ensuite repassée dans `controler_relation` avec le véritable passage source. Une preuve introuvable, une plage invalide ou une citation absente entraînent un rejet. Les fichiers originaux ne sont pas écrasés : un nouveau dossier de correction est créé.

Les empreintes SHA-256 des propositions originales sont enregistrées. Elles permettent de prouver quels fichiers ont été contrôlés. `corrections_v2` et `corrections_v3` sont donc des résultats successifs d’audit, et non des copies arbitraires.

La V3 distingue trois niveaux. `VALIDE` signifie que la relation est clairement confirmée par la preuve documentaire et satisfait les règles automatiques. `PROBABLE` signifie qu’une preuve réelle existe, mais qu’une ambiguïté, une condition ou une généralisation empêche d’en faire une règle certaine. `REJETE` signifie qu’une erreur bloquante a été détectée.

Il faut formuler cette limite clairement devant le public : `VALIDE` signifie « validé automatiquement par rapport au document », pas « certifié par un expert ferroviaire ».

### 6.5 `selection_prudente.py` et `generer_pilotes.py`

`selection_prudente.py` conserve les relations `VALIDE` et `PROBABLE` dépourvues de motif bloquant. Il élimine les concepts qui ne participent plus à aucune relation retenue. Il ajoute la méthode de validation et l’indicateur `validation_experte=false`.

`generer_pilotes.py` applique cette sélection à chaque fiche contrôlée. Il produit actuellement 29 fichiers `.pilote.json`, un par document, puis un rapport global.

Dans l’état actuel des données, ces pilotes totalisent 324 occurrences de concepts, 117 relations classées `VALIDE`, 224 classées `PROBABLE` et 24 rejetées. Le nombre de concepts est un total par pilote ; des synonymes ou concepts identiques peuvent encore apparaître dans plusieurs fiches.

### 6.6 `metier_builder.py` et `import_pilote.py`

`metier_builder.py` est l’importeur générique. Il crée les nœuds `ConceptMetier` et les relations `RELATION_METIER`. Il relie, lorsque la correspondance existe, un concept à une classe UML avec `REPRESENTE_PAR` et à un document avec `DOCUMENTE_PAR`. Les preuves peuvent être reliées aux chunks avec `ETAYE_PAR` et les propriétés de la relation conservent citation, lignes, condition, exception, statut et identifiants de chunks.

`import_pilote.py` ajoute un précontrôle spécifique avant l’import. Il vérifie que chaque classe et chaque document ciblé existe de manière unique dans Neo4j. Il vérifie que la citation apparaît réellement dans les lignes annoncées et dans au moins un chunk. Il refuse aussi d’écraser silencieusement un concept existant de contenu différent.

Sans l’option `--importer`, le script reste en lecture seule. Avec cette option, l’import est exécuté après tous les contrôles. Les opérations utilisent `MERGE`, ce qui permet de rejouer un import identique sans créer volontairement de doublons.

### 6.7 `normalisation_metier.py`

Après plusieurs fiches, deux identifiants peuvent désigner le même concept. Ce script cherche les doublons, choisit un concept canonique, sauvegarde l’état avant modification, redirige les relations puis fusionne les nœuds.

Cette opération est plus sensible qu’une extraction : elle modifie un graphe existant. C’est pourquoi elle prévoit une sauvegarde et sépare la détection des doublons de leur fusion.

## 7. Le cœur GraphRAG : `retrieval.py`

[Afficher le flux Question → Mode → Entités → Sources → Contexte.]

Le retriever est la pièce centrale. Il ne rédige pas la réponse ; il décide quelles connaissances doivent être fournies.

### 7.1 Normalisation et résolution des entités

`normaliser` met le texte en minuscules, retire les accents, traite les ligatures comme `œ`, découpe le CamelCase et supprime la ponctuation. Ainsi, `NœudDeLigne`, `Noeud de ligne` et d’autres variantes deviennent comparables.

`resoudre_classes` compare la question au catalogue des classes. Elle privilégie les expressions exactes, calcule un recouvrement de tokens et une similarité textuelle, puis élimine les candidats génériques inclus dans un nom plus précis. Cela évite, par exemple, de sélectionner `Ligne` lorsque l’utilisateur nomme précisément `NoeudDeLigne`.

### 7.2 Classification des intentions

`analyser_question` recherche des marqueurs généraux, sans coder une réponse pour une question particulière. Il produit actuellement six modes.

`STRUCTURE` consulte le graphe UML pour les attributs, types, héritages et relations directes.

`DOCUMENTAIRE` cherche les passages de procédure ou de définition.

`METIER` consulte les concepts et relations métier contrôlés.

`CHEMIN_UML` calcule un chemin orienté dans les relations structurelles.

`CHEMIN_METIER` calcule le plus court chemin entre deux concepts métier validés, dans une profondeur bornée.

`HYBRIDE` combine uniquement les sources réellement demandées. Il ne signifie pas que toutes les couches sont systématiquement chargées.

Cette séparation réduit le bruit. Une question sur les attributs n’a pas besoin de chunks. Une procédure n’a pas besoin de tout le voisinage UML. Une question mixte peut toutefois demander les deux.

### 7.3 Construction des sous-graphes

`_construire_sous_graphe` récupère les classes racines, leurs attributs et leur voisinage structurel.

`_selectionner_concepts` retrouve les concepts métier proches de la question et des classes résolues. `_construire_graphe_metier` charge ensuite un voisinage borné et uniquement les relations admises par les statuts configurés.

`_selectionner_extremites_chemin` identifie les deux extrémités d’une demande de chemin métier. `_construire_chemin_metier` demande ensuite à Neo4j un plus court chemin de profondeur maximale cinq.

`_construire_chemin_uml` effectue un calcul séparé, sur les seules relations `HERITE_DE`, `COMPOSE_DE`, `ASSOCIE_A` et `AGREGE`, jusqu’à huit sauts. Le sens de départ et d’arrivée suit l’ordre de la question. Le système n’inverse pas ensuite les arêtes uniquement pour fabriquer une réponse.

### 7.4 Recherche des chunks

`_chercher_chunks` combine la recherche vectorielle et la recherche plein texte. Les résultats sont fusionnés par leurs rangs. Un reranker optionnel peut reclasser les candidats, puis seuls les meilleurs passages sont conservés.

`_chercher_preuves_metier` ajoute en priorité les chunks qui justifient les relations métier présentes dans le contexte. C’est ce mécanisme qui relie la relation structurée à sa preuve textuelle.

### 7.5 Orchestration finale

`retrieve` contextualise d’abord les relances qui en ont réellement besoin, par exemple « et ses attributs ? ». Il choisit le mode, résout les classes, exécute seulement les branches nécessaires, récupère les preuves et retourne un objet JSON contrôlé.

Cet objet contient notamment la question, le mode, les entités candidates, les classes racines, le sous-graphe UML, le graphe métier, les chemins éventuels et les chunks. `contexte_pour_llm` sérialise cet objet pour la génération.

## 8. L’agent de réponse : `agent.py`

L’agent initialise Neo4j, les embeddings et les fournisseurs configurés. L’utilisateur peut choisir Mistral, Gemini ou Groq. Le fournisseur choisi est appelé explicitement ; le système courant ne change pas silencieusement de fournisseur pour une réponse ordinaire.

La distinction la plus importante est celle entre calcul et reformulation.

En mode `STRUCTURE`, la réponse est déterministe. `_formater_structure_uml` transforme directement les données Neo4j en texte. Le LLM n’est pas nécessaire pour décider des attributs ou des héritages.

En mode `CHEMIN_UML`, `_formater_chemin_uml` présente le chemin calculé par Neo4j. Là encore, la vérité du chemin ne vient pas du LLM.

En mode `CHEMIN_METIER`, Neo4j calcule le chemin. Le LLM peut seulement reformuler les arêtes en phrases naturelles, sans en ajouter ou en supprimer.

Pour les modes documentaire, métier et hybride, l’agent construit un prompt qui contient le contexte GraphRAG. Le modèle doit répondre d’abord directement, développer lorsque la question le demande, respecter les conditions et exceptions, distinguer une relation `PROBABLE` d’une relation `VALIDE` et ne pas afficher les références techniques.

`_schema_depuis_retrieval` construit les nœuds et liens envoyés à l’interface pour le schéma visuel. Ce schéma est un complément ; il ne doit pas remplacer l’explication textuelle.

Les fonctions `_invoquer_groq`, `_invoquer_gemini` et l’intégration Mistral adaptent les formats d’API. Groq reçoit un contexte compacté afin de respecter ses limites. Les erreurs réseau, 429, clés refusées ou réponses vides sont converties en messages compréhensibles.

## 9. API, authentification et mémoire

[Afficher l’interface avec la liste des conversations.]

`api.py` démarre FastAPI et instancie l’agent. La route `/ask` vérifie l’utilisateur, la conversation et la question, charge l’historique, appelle l’agent, enregistre la réponse et son graphe, puis renvoie le tout au navigateur.

SQLite contient les tables `Utilisateur`, `SessionAuthentification`, `Conversation`, `ProprietaireConversation`, `Message` et `VisualisationMessage`.

Les mots de passe sont hachés avec PBKDF2-HMAC-SHA256 et un sel. Les jetons de session sont aléatoires ; seule leur empreinte est stockée. Le cookie est `HttpOnly` et chaque accès à une conversation vérifie son propriétaire.

La mémoire conversationnelle n’est donc pas une mémoire globale du LLM. Elle est reconstruite depuis les messages enregistrés pour la conversation et transmise de manière bornée à l’agent. Les conversations de deux utilisateurs restent séparées.

Les autres routes permettent l’inscription, la connexion, la déconnexion, la liste des conversations, le chargement des messages, la suppression, la liste des fournisseurs, l’état de santé et la récupération d’un graphe visible.

`index.html` regroupe le HTML, le CSS et le JavaScript du frontend. Il gère l’écran de connexion, la barre latérale, les conversations, le choix du fournisseur, l’envoi des questions, le rendu Markdown et la visualisation interactive du graphe.

## 10. Évaluation et tests

`arianes/evaluation.py` charge un jeu de questions de référence. Pour chaque cas, il vérifie le mode attendu, les classes racines et les sources récupérées. L’option avec LLM permet d’ajouter la réponse générée, mais il faut distinguer l’évaluation du retrieval de celle de la formulation.

Les tests couvrent le retriever, les builders, les validations métier, l’API, l’authentification, l’isolation des conversations, la sécurité Cypher et le prototype de reranking.

La dernière exécution de la suite officielle donne 76 tests réussis et 15 sous-tests réussis, soit 91 contrôles. Un avertissement de compatibilité future entre Starlette et la couche de test HTTP reste à surveiller, sans échec fonctionnel actuel.

Une matrice de questions vérifie aussi les six modes. Par exemple : « Quels attributs possède Ligne ? » doit être structurel ; « Comment créer un itinéraire ? » documentaire ; « À quoi un poste est-il rattaché ? » métier ; « Quel chemin UML mène de HabillageOriente à Ligne ? » chemin UML ; et une comparaison entre UML et fonctionnement doit être hybride.

## 11. Prototype de reranking dans `ml`

Cette partie est optionnelle et n’est pas le cœur de la démonstration.

`reranker.py` extrait des caractéristiques comme les scores initiaux, le recouvrement lexical et le rang, puis applique un modèle linéaire. `train_reranker.py` entraîne une régression logistique. `build_dataset_from_evaluation.py` transforme les résultats annotés en données d’apprentissage. `evaluate_reranker.py` mesure la qualité du classement et effectue une validation croisée.

Le modèle est désactivé par défaut et le retrieval standard continue de fonctionner s’il est absent. Sa limite actuelle est la quantité et la qualité des exemples annotés. Il s’agit donc d’une piste expérimentale, pas d’un composant dont dépend la démonstration.

## 12. Démonstration proposée

[Démarrer avec Neo4j et l’application déjà ouverts. Éviter de reconstruire le graphe en direct.]

Je commencerais par une question UML simple : « Quels attributs possède la classe Ligne ? » J’expliquerais que la réponse est produite directement depuis Neo4j et non inventée par le modèle.

Ensuite : « Quelles classes héritent de NoeudDeLigne ? » Cela montre que le mot « types » ou « classes héritières » est interprété structurellement.

Puis : « Quel chemin UML mène de HabillageOriente à Ligne ? » Le résultat doit suivre un chemin orienté réel.

Pour la partie documentaire : « Comment construire un itinéraire ? » Le retriever doit sélectionner la fiche et quelques chunks pertinents, puis le fournisseur choisi rédige la procédure.

Pour la couche métier : « À quoi un poste est-il rattaché ? » puis « Quel chemin métier relie Signal à Ligne ? » Le deuxième cas doit expliquer qu’un signal est commandé par un poste d’aiguillage et que ce poste est localisé sur une ligne, si ces relations sont présentes et admises dans le graphe importé.

Enfin, je poserais une question hybride : « Explique la classe Poste, ses relations UML et ses relations métier. » Cela permet de montrer l’assemblage contrôlé des différentes couches.

Avant la démonstration, je vérifierais `/health`, la connexion Neo4j et le fournisseur sélectionné. Je garderais aussi des captures d’écran des réponses attendues. Une panne ou une limite d’API ne remet pas en cause le retrieval, mais elle peut empêcher la rédaction documentaire en direct.

## 13. Limites actuelles et positionnement honnête

Le premier risque est la qualité des relations métier extraites. Une citation présente ne garantit pas qu’une relation est universellement vraie. Les relations `PROBABLE` doivent être présentées avec prudence et une validation experte reste nécessaire avant un usage opérationnel.

Le deuxième risque est le routage linguistique. Des formulations nouvelles peuvent encore être mal classées. Les tests ont par exemple identifié qu’une formulation comme « description documentaire » doit être explicitement reconnue comme hybride lorsqu’elle est comparée à une classe UML.

Le troisième risque est la dépendance aux fournisseurs pour la rédaction. Les erreurs 429 relèvent des quotas du fournisseur. C’est la raison du choix explicite entre plusieurs fournisseurs. Les réponses UML déterministes restent moins dépendantes de cette disponibilité.

Le quatrième point est la consolidation interdocumentaire. Les 29 pilotes peuvent contenir des concepts proches ou contradictoires. La normalisation automatique aide, mais une interface de revue experte serait l’étape suivante la plus utile.

Enfin, la visualisation d’un grand graphe complet devient vite illisible. L’interface doit donc afficher des sous-graphes centrés sur la question, limiter le nombre de relations et conserver un placement stable. Une visualisation n’est pas la base elle-même : c’est une projection adaptée à la réponse.

## 14. Conclusion

Pour conclure, la contribution principale du projet est la séparation explicite des responsabilités.

Le XMI fournit la structure UML. Les fiches fournissent les procédures et les preuves. Le pipeline métier transforme certains passages en propositions relationnelles contrôlées. Neo4j stocke ces couches et leur provenance. Le retriever décide quelle couche consulter. L’agent formule la réponse sans devenir la source de vérité. FastAPI, SQLite et le frontend rendent enfin le système utilisable par plusieurs utilisateurs avec un historique séparé.

Ce projet ne prétend pas qu’un LLM connaît spontanément Arianes. Au contraire, il limite le modèle à ce qu’il sait bien faire : comprendre une demande et produire une explication lisible à partir d’un contexte sélectionné. La connaissance reste dans les données, les documents et le graphe.

La suite logique serait de faire valider progressivement les relations par des experts métier, d’améliorer le jeu d’évaluation, d’ajouter une interface de revue et de mesurer séparément la précision du retrieval, la fidélité factuelle et la qualité de formulation.

Merci. Je peux maintenant répondre aux questions ou montrer plus précisément l’un des trois pipelines : UML, documentaire ou métier.

## 15. Réponses courtes aux questions probables du public

### « Pourquoi utiliser Neo4j plutôt qu’une base relationnelle ? »

Parce que les questions portent directement sur des voisins, des héritages et des chemins. Neo4j représente ces relations naturellement. SQLite reste utilisé là où un modèle relationnel simple est adapté : comptes, sessions, conversations et messages.

### « Est-ce réellement du GraphRAG ? »

Oui, car le contexte de génération est construit à partir d’un graphe et de ses relations, complété par une recherche documentaire. Ce n’est pas seulement un RAG vectoriel. Le calcul de sous-graphes et de chemins fait partie du retrieval.

### « Le LLM peut-il modifier Neo4j ? »

Non dans le parcours normal de questions-réponses. Les requêtes sont déterministes et en lecture. Les écritures passent par des builders et des scripts d’import explicites après validation.

### « Quelle différence entre UML et métier ? »

L’UML décrit la structure officielle du modèle informatique. Le graphe métier représente des relations fonctionnelles exprimées dans les fiches. Une relation métier ne doit jamais être présentée comme une association UML.

### « Pourquoi garder les relations probables ? »

Parce qu’un filtre trop strict éliminerait une grande partie de la connaissance utile. Elles sont conservées avec leur statut, leur preuve, leurs conditions et un avertissement. Elles ne doivent pas être présentées comme certifiées.

### « Pourquoi plusieurs modèles de langage ? »

Pour laisser l’utilisateur choisir selon la disponibilité, la latence et les quotas. Le contexte GraphRAG reste le même ; seul le moteur de formulation change.

### « Que se passe-t-il si le LLM est indisponible ? »

Les réponses structurelles UML et les chemins UML peuvent rester déterministes. Les réponses documentaires nécessitent encore un modèle pour produire une formulation complète, même si le retrieval des passages peut être évalué indépendamment.

### « Pourquoi le graphe complet n’est-il pas connexe ? »

Cela peut être normal : plusieurs domaines UML, documents ou concepts n’ont pas nécessairement de relation entre eux. Un graphe non connexe n’est pas automatiquement faux. Il faut distinguer une composante réellement indépendante d’un lien manquant dû à l’extraction ou à la validation.

### « Comment prouver une réponse métier ? »

Chaque relation importée conserve le document, les lignes, la citation et les identifiants des chunks justificatifs. La réponse masque ces détails techniques dans l’interface, mais le système les conserve pour l’audit.
