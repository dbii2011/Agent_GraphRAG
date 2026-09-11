# Script oral — Présentation GraphRAG Arianes (1 heure)

Ce script accompagne la présentation `Presentation_GraphRAG_Arianes_1h_visuelle.pptx`. Il est conçu pour environ 45 minutes de présentation, 10 minutes de démonstration et 5 minutes d'échanges.

## Fil conducteur pour un public non informaticien

Pendant toute la présentation, utiliser une seule comparaison : **le système fonctionne comme un documentaliste assisté par une carte du réseau**.

- Les fiches de procédure sont les livres de la bibliothèque.
- Les chunks sont les paragraphes ou extraits de ces livres.
- Le graphe UML est le plan officiel qui décrit les catégories d'objets et leur organisation.
- Le graphe métier est une carte qui relie les notions rencontrées dans les fiches.
- Neo4j est le classeur qui conserve cette carte et permet de suivre les liens.
- Le retriever joue le rôle du documentaliste : il choisit le bon rayon et rassemble les éléments utiles.
- Le modèle de langage joue le rôle du rédacteur : il transforme les éléments retrouvés en réponse naturelle.

Répéter cette idée lorsque le public semble perdu : **le modèle de langage ne connaît pas à lui seul les règles Arianes. L'application lui fournit les bonnes informations avant de lui demander de répondre.**

## Vocabulaire à expliquer avant de l'utiliser

**Métamodèle UML** : un plan de classement formel. Il décrit les types d'objets que le système peut contenir, leurs propriétés et leurs liens. Une classe comme `Ligne` représente une catégorie, pas une ligne ferroviaire réelle.

**Instance** : un objet concret créé à partir d'une classe. La classe peut être comparée au formulaire vierge, tandis que l'instance correspond au formulaire rempli pour un objet réel.

**Graphe** : une représentation composée de points et de liens. Les points représentent les objets ou concepts. Les liens indiquent leurs relations.

**Nœud** : un élément du graphe, par exemple la classe `Ligne`, le concept `Canton` ou un passage documentaire.

**Relation** : un lien nommé et orienté entre deux nœuds, par exemple `Signal EST_COMMANDE_PAR Poste`.

**Chunk** : un morceau de document. Les fiches sont découpées afin que le moteur puisse retrouver un passage précis sans transmettre tout le document.

**Embedding** : une traduction mathématique du sens d'un texte. Deux formulations proches par leur sens obtiennent des représentations proches, même lorsqu'elles n'utilisent pas exactement les mêmes mots.

**Indexation** : la préparation des données pour accélérer leur recherche. Elle joue un rôle proche de l'index situé à la fin d'un livre.

**Retrieval** : l'étape de recherche et de sélection des informations utiles avant la rédaction de la réponse.

**RAG** : une méthode dans laquelle le système recherche d'abord des informations, puis demande au modèle de rédiger une réponse à partir de ces informations.

**GraphRAG** : un RAG qui utilise également les relations d'un graphe. Il peut donc retrouver des passages, mais aussi suivre des liens entre des objets.

**LLM ou modèle de langage** : le moteur qui comprend et produit du texte. Il formule la réponse, mais ne doit pas inventer les relations absentes des données récupérées.

**Pipeline** : une chaîne d'étapes successives. Chaque étape reçoit une entrée, effectue un traitement et fournit une sortie à l'étape suivante.

**Provenance** : l'information qui permet de retrouver l'origine d'une donnée, par exemple la fiche et le passage ayant justifié une relation métier.

## Comment commenter les schémas

Ne pas commencer par lire tous les blocs. Donner d'abord le sens général, puis suivre les flèches avec le pointeur.

Pour un schéma de pipeline, dire : « On part de cette donnée, elle passe dans ces traitements, puis elle arrive ici sous une forme exploitable. » Expliquer ensuite une étape à la fois, de gauche à droite.

Pour un graphe, dire : « Les rectangles ou cercles sont les objets. Les flèches sont les relations. Le nom écrit sur la flèche explique le sens du lien. » Lire ensuite un seul exemple complet à voix haute.

Pour une architecture, commencer par les quatre zones : sources, préparation, stockage et réponse. Le public comprendra mieux les composants techniques après avoir compris leurs responsabilités.

## Formulations simples à privilégier

- Dire « retrouver les passages les plus proches par leur sens » avant « recherche vectorielle ».
- Dire « recherche exacte par mots » avant « index plein texte ».
- Dire « point de reprise » avant « checkpoint ».
- Dire « fusionner sans créer de doublon » avant de citer `MERGE`.
- Dire « question sur l'organisation du modèle » pour le mode `STRUCTURE`.
- Dire « question sur une procédure » pour le mode `DOCUMENTAIRE`.
- Dire « question sur les liens opérationnels » pour le mode `METIER`.

## Ce qu'il faut éviter à l'oral

- Ne pas détailler une requête Cypher ligne par ligne, sauf si le public le demande.
- Ne pas présenter le LLM comme une source de vérité.
- Ne pas dire qu'une relation `VALIDE` a reçu une certification métier humaine.
- Ne pas confondre la panne d'un fournisseur avec un échec de Neo4j ou du retrieval.
- Ne pas lire tous les nombres et toutes les relations d'un schéma dense. Choisir un exemple représentatif.
- Ne pas utiliser plusieurs analogies différentes pour la même notion.

## Introduction orale alternative, très accessible

« Imaginez que nous demandions à une personne de répondre à des questions sur Arianes. Nous lui donnons d'un côté un plan officiel des objets et de leurs relations, et de l'autre plusieurs fiches expliquant les procédures. Cette personne doit d'abord comprendre si la question concerne le plan, une procédure ou une relation métier. Elle consulte ensuite les bonnes sources et rédige une réponse. Mon application automatise ce travail. Neo4j conserve la carte des relations, les index retrouvent les bons passages et le modèle de langage présente le résultat en français. »

Cette introduction peut remplacer les premières phrases des slides 1 et 2 si l'auditoire connaît peu l'intelligence artificielle.

## Avant de commencer

- Ouvrir l'application, Neo4j Browser et un terminal avant l'arrivée du public.
- Vérifier les trois démonstrations : question UML, question documentaire et question métier.
- Garder des captures d'écran prêtes si une API externe ou le réseau devient indisponible.
- Ne pas lire chaque mot. Les paragraphes donnent une formulation possible et les phrases en italique servent de transitions.

---

## Slide 1 — GraphRAG Arianes

**Durée : 1 minute**

Bonjour à toutes et à tous. Je vais vous présenter le travail réalisé autour d'un assistant conversationnel pour le métamodèle Arianes et ses fiches de procédure. Le problème de départ était simple à formuler : nous disposons de beaucoup de connaissances, mais elles sont réparties entre un modèle UML, des relations complexes et des documents textuels. Il est donc difficile de retrouver rapidement une information fiable sans connaître exactement le fichier ou la classe à consulter.

L'objectif du projet est de permettre à un utilisateur de poser une question en langage naturel. L'application identifie le type de question, recherche la bonne connaissance dans Neo4j ou dans les documents indexés, puis utilise un modèle de langage pour présenter une réponse compréhensible.

*Transition : avant l'architecture technique, je vais préciser ce que la démonstration doit prouver.*

## Slide 2 — Objectif de la présentation

**Durée : 1 minute**

La présentation suit quatre étapes. Je vais d'abord expliquer les données disponibles et pourquoi un simple moteur de recherche documentaire ne suffit pas. Ensuite, je détaillerai la construction des trois couches de connaissance : UML, documentaire et métier. Je montrerai alors comment le retriever choisit la couche adaptée à chaque question. Enfin, je terminerai par une démonstration de l'application et par les limites actuelles.

Le message important est que le modèle de langage ne constitue pas la base de connaissances. Les connaissances restent dans les sources, les index et le graphe. Le modèle sert surtout à comprendre la demande et à restituer les résultats.

## Slide 3 — Trois formes de connaissance

**Durée : 2 minutes**

Le projet manipule trois formes de connaissance complémentaires.

La première est la connaissance structurelle. Elle vient du métamodèle UML : classes, attributs, héritages, associations et compositions. Elle répond par exemple à « Quels sont les attributs de Ligne ? » ou « Existe-t-il un chemin UML entre HabillageOriente et Ligne ? ».

La deuxième est la connaissance documentaire. Elle vient de 29 fiches de procédure découpées en passages. Elle répond à des demandes comme « Comment crée-t-on un itinéraire ? » ou « Qu'est-ce que le KVB ? ».

La troisième est la connaissance métier. Elle représente des concepts et des relations exprimés dans les documents, par exemple « un signal est commandé par un poste ». Cette couche permet des questions relationnelles et des chemins métier.

Il ne faut pas mélanger ces couches. Une procédure n'est pas un héritage UML, et une association UML n'est pas forcément une règle opérationnelle.

## Slide 4 — Pourquoi un RAG vectoriel seul ne suffit pas

**Durée : 2 minutes**

Un RAG classique transforme la question en vecteur et récupère les passages les plus proches. Cette approche convient bien aux définitions et aux procédures. En revanche, elle répond moins bien aux questions qui demandent une structure exacte ou plusieurs sauts dans un graphe.

Par exemple, pour trouver un chemin entre deux classes, la similarité sémantique ne garantit ni la continuité du chemin ni le sens des relations. Pour connaître tous les descendants d'une classe, une requête de graphe est plus fiable qu'une génération libre.

Le GraphRAG combine donc deux capacités : la recherche sémantique dans les textes et la navigation explicite dans les relations. Ici, le terme GraphRAG désigne cette utilisation coordonnée du graphe UML, du graphe métier et des chunks documentaires.

*Transition : voici maintenant la vue d'ensemble de l'application.*

## Slide 5 — Architecture générale et flux d'exécution

**Durée : 3 minutes**

Cette figure résume toute l'architecture. À gauche se trouvent les sources : 44 fichiers JSON issus du métamodèle et 29 fiches de procédure. Les pipelines transforment ces sources avant leur chargement.

Au centre, Neo4j contient les classes UML, les documents, les chunks et les concepts métier. SQLite joue un autre rôle : il conserve les utilisateurs, les sessions, les conversations et les messages. Cette séparation évite de confondre le savoir ferroviaire avec les données applicatives.

Lorsqu'une question arrive, le retriever la classe dans un mode, résout les entités mentionnées puis interroge la partie appropriée de Neo4j. L'agent reçoit un contexte contrôlé et le transmet au fournisseur choisi, Mistral, Gemini ou Groq. Le navigateur affiche enfin la réponse et, lorsqu'il existe des relations, un schéma complémentaire.

Insister visuellement sur le sens du flux : sources, préparation, stockage, retrieval, génération, interface.

## Slide 6 — Modèle de données Neo4j et provenance

**Durée : 2 minutes**

Neo4j ne contient pas un seul type de nœud. Une classe UML porte le label `Classe`, un passage porte le label `Chunk`, une fiche porte le label `Document` et une entité extraite porte le label `ConceptMetier`.

Les relations UML, comme `HERITE_DE`, `ASSOCIE_A` ou `COMPOSE_DE`, sont conservées séparément des relations métier. Une assertion métier reste reliée au chunk et au document qui l'ont justifiée. Cette provenance est fondamentale : elle permet de savoir d'où vient une relation, de la réexaminer et de corriger le graphe sans inventer une vérité globale.

Les propriétés `nom`, `description`, `niveau_validation`, `condition` et `exception` servent respectivement à identifier, expliquer et qualifier la connaissance.

## Slide 7 — Organisation du dépôt

**Durée : 1 minute 30**

Le dépôt a été réorganisé par responsabilité. Le paquet `arianes` contient le cœur fonctionnel. Le sous-dossier `graph` construit ou importe les graphes. Le sous-dossier `pipelines` traite les sources et génère les pilotes. Le retriever orchestre les recherches et l'agent orchestre la réponse.

À la racine, `api.py` expose l'application web et `index.html` contient l'interface. Les données sources et produites restent dans leurs dossiers dédiés. Les tests sont séparés du code applicatif et la documentation explique les choix réalisés.

Cette organisation facilite trois opérations : retrouver un traitement, tester une responsabilité isolée et éviter qu'un script expérimental devienne implicitement du code de production.

## Slide 8 — Pipeline UML, du modèle source aux requêtes

**Durée : 2 minutes**

Le pipeline UML commence avec le modèle exporté au format XMI. Le convertisseur le transforme en JSON intermédiaires plus simples à traiter. Le builder normalise ensuite les noms, crée les nœuds et ajoute les relations dans Neo4j. Une phase d'indexation prépare la recherche. Le retriever peut alors exécuter des requêtes structurelles.

Cette chaîne est déterministe : à entrée identique, le même graphe doit être produit. Le LLM ne décide pas si une classe hérite d'une autre. Il ne faut pas lui déléguer une information déjà formalisée dans le métamodèle.

## Slide 9 — Conversion XMI vers JSON

**Durée : 1 minute 30**

Le XMI est riche mais difficile à exploiter directement. Le script de conversion parcourt les éléments UML et produit des objets JSON représentant les classes, leurs attributs, leurs types et leurs références.

Cette étape conserve aussi les identifiants techniques nécessaires pour reconnecter les éléments. Elle traite les différences de représentation, par exemple une cible stockée comme identifiant plutôt que comme nom lisible. Le résultat constitue une représentation intermédiaire contrôlable avant l'import en base.

## Slide 10 — Construction du graphe UML

**Durée : 2 minutes**

Le builder lit les JSON, crée les contraintes d'unicité puis fusionne les nœuds au lieu de les recréer à chaque exécution. Il ajoute les attributs et les types, puis les relations UML.

La fusion, ou `MERGE`, rend l'import réexécutable. Elle évite de multiplier les instances d'une même classe. Les éléments non résolus peuvent recevoir une représentation explicite afin de ne pas perdre la relation, mais ils doivent rester distinguables d'une classe Arianes réelle.

Le nom affiché dans Neo4j doit venir de la propriété `nom`. Si Neo4j affiche `FALSE`, il s'agit généralement d'un réglage de caption qui choisit la propriété booléenne `abstraite`, pas d'une disparition du nom.

## Slide 11 — Pipeline documentaire et double indexation

**Durée : 2 minutes**

Chaque fiche est enregistrée comme document, puis divisée en chunks suffisamment courts pour la recherche, mais assez longs pour préserver le sens. Chaque chunk conserve son texte, son document d'origine et sa position.

Deux index sont complémentaires. L'index vectoriel retrouve un passage même lorsque la question emploie d'autres mots. L'index plein texte favorise les termes précis, les sigles et les noms ferroviaires. Cette combinaison est plus robuste qu'une seule méthode, notamment pour des expressions comme KVB ou SAF.

## Slide 12 — Recherche hybride des passages

**Durée : 2 minutes**

Pour une question documentaire, le système calcule d'abord son embedding. Il obtient une liste de chunks proches par similarité vectorielle et une autre liste par recherche lexicale. Les scores sont normalisés et fusionnés. Le système élimine les doublons, limite le nombre de passages et conserve leur provenance.

La qualité dépend à la fois du découpage, de la requête, de la présence réelle de l'information et de la taille du contexte. Envoyer davantage de texte n'améliore pas toujours la réponse. Un contexte trop grand augmente la latence, le coût et le risque que le modèle se concentre sur un passage secondaire.

## Slide 13 — Transition : extraction et validation du graphe métier

**Durée : 30 secondes**

Nous avons vu les données déjà structurées et les documents. La difficulté suivante consiste à transformer certaines phrases des procédures en relations navigables sans présenter automatiquement chaque proposition du LLM comme une vérité.

## Slide 14 — Extraction métier contrôlée, morceau par morceau

**Durée : 3 minutes**

Le pipeline traite chaque fiche par morceaux. Pour chaque chunk, le LLM reçoit le texte et une consigne d'extraction structurée. Il propose des concepts candidats, des variantes de noms, des définitions et des relations sous la forme source, prédicat, cible.

Une relation doit aussi conserver une citation ou un passage justificatif. Le pipeline normalise ensuite les noms : casse, accents, pluriels et variantes fréquentes. Il tente de rattacher les concepts aux classes UML connues et au document source.

Le point essentiel est que le LLM propose. Il ne valide pas seul. Ses sorties sont des candidats qui passent ensuite par des contrôles. Le traitement par morceaux permet de reprendre après une interruption et de localiser précisément une extraction douteuse.

## Slide 15 — Traitement global et checkpoints

**Durée : 2 minutes**

Le traitement global parcourt les 29 fiches et crée des checkpoints. Après chaque document ou lot, l'état est sauvegardé. Si une API devient indisponible, le pipeline reprend au dernier point connu au lieu de recommencer toutes les extractions.

Les sorties intermédiaires sont volontairement conservées : propositions brutes, corrections et pilotes documentaires. Elles correspondent à des étapes différentes, pas à trois graphes concurrents. Les propositions montrent ce que le modèle a détecté. La correction V3 applique les règles de qualification. Le pilote représente le paquet prêt à examiner ou importer.

## Slide 16 — Décision V3 pour chaque relation extraite

**Durée : 3 minutes**

La validation V3 classe les relations en trois niveaux. `VALIDE` signifie que les contrôles automatiques trouvent un appui documentaire clair, des concepts cohérents et un prédicat acceptable. Cela ne signifie pas qu'un expert métier a certifié la relation.

`PROBABLE` désigne une relation plausible, mais dont la formulation, la correspondance de concept ou la preuve reste imparfaite. Elle peut être conservée pour exploration tout en restant identifiable. `REJETE` correspond à une auto-relation sans sens, une entité absente, une citation introuvable ou une incohérence forte.

Le rapport actuel compte 324 occurrences de concepts dans les pilotes, 117 relations validées, 224 probables et 24 rejetées. Le choix des seuils cherche un compromis : ne pas polluer le noyau fiable, sans supprimer toute la richesse métier.

## Slide 17 — Génération des 29 pilotes

**Durée : 1 minute 30**

Un pilote est généré pour chaque fiche, donc le pipeline ne se limite plus au document Poste. Chaque pilote regroupe les concepts, les relations, les niveaux de validation, les conditions, les exceptions et les références documentaires.

Cette unité par fiche simplifie le contrôle : on peut examiner un domaine isolément, corriger une extraction et réimporter uniquement le pilote concerné. La qualité reste variable selon la précision des documents et doit progresser avec une validation humaine métier.

## Slide 18 — Provenance complète d'une assertion métier

**Durée : 2 minutes**

Prenons une assertion comme « Signal EST_COMMANDE_PAR Poste ». Elle n'apparaît pas seule dans le graphe. Elle reste reliée au concept source, au concept cible, au chunk justificatif et au document d'origine. Son niveau de validation et ses éventuelles conditions sont également conservés.

Cette traçabilité répond à une question essentielle : pourquoi le chatbot affirme-t-il cela ? Elle permet aussi de distinguer deux relations portant le même nom mais provenant de contextes différents. Pour un usage industriel, la provenance est aussi importante que la relation.

## Slide 19 — Transition : retrieval et génération

**Durée : 30 secondes**

Les données sont maintenant préparées. Il reste à choisir correctement lesquelles consulter pour chaque question. C'est le rôle central du retriever.

## Slide 20 — Résolution des entités

**Durée : 2 minutes**

Le système commence par détecter les entités citées dans la question. Il compare les expressions aux noms, aux alias et aux formes normalisées. Il doit par exemple rapprocher « nœud de ligne » de `NoeudDeLigne`, tout en évitant de confondre le mot courant « type » avec un concept métier.

La résolution produit des racines de recherche. Si deux classes distinctes sont reconnues dans une question de chemin, elles deviennent le départ et l'arrivée. Une mauvaise résolution entraîne une recherche correcte sur les mauvaises entités. Les journaux affichent donc les racines choisies pour faciliter le diagnostic.

## Slide 21 — Routage vers six stratégies de recherche

**Durée : 3 minutes**

Le routeur distingue six modes.

`STRUCTURE` traite les attributs, héritages, compositions et types UML. `DOCUMENTAIRE` traite les définitions détaillées et les procédures. `METIER` consulte les concepts et relations extraits. `CHEMIN_UML` calcule un chemin orienté entre deux classes. `CHEMIN_METIER` cherche plusieurs sauts entre concepts métier. `HYBRIDE` combine plusieurs sources lorsqu'une question le nécessite.

Le routage repose sur l'intention linguistique, les entités reconnues et des marqueurs comme « dans l'UML », « procédure », « relation métier » ou « chemin ». L'objectif n'est pas d'écrire une règle pour chaque question possible, mais de reconnaître des familles stables de demandes.

## Slide 22 — Orchestration du retrieval et assemblage du contexte

**Durée : 2 minutes**

Après le routage, chaque stratégie produit un résultat normalisé. Le retriever assemble uniquement les éléments utiles : classes et relations pour l'UML, chunks classés pour le documentaire, assertions et provenance pour le métier.

Il impose des limites de taille, retire les répétitions et structure le contexte. Ce contexte contient des données, pas des instructions à exécuter. L'agent ajoute ensuite une consigne de réponse adaptée au mode, l'historique récent de la conversation et la question.

Les logs `mode`, `racines`, `classes` et `chunks` montrent ce qui a réellement alimenté la génération.

## Slide 23 — Calcul des chemins

**Durée : 2 minutes 30**

Un chemin ne doit pas être inventé par le LLM. Neo4j le calcule à partir des relations existantes. Pour l'UML, le chemin respecte le sens des relations et une limite de huit sauts. Pour le métier, la limite actuelle est de cinq relations.

Le résultat doit être une suite continue : la cible d'une relation devient la source de la suivante. Une ancienne présentation pouvait donner un chemin incohérent en réorientant indépendamment chaque arête. La correction consiste à préserver l'ordre exact du chemin retourné par Neo4j.

Le LLM peut reformuler ce résultat en français, mais il ne doit ni changer l'ordre ni ajouter une relation.

## Slide 24 — Répartition entre calcul déterministe et génération

**Durée : 2 minutes**

Cette matrice montre la frontière de responsabilité. Les réponses `STRUCTURE` et `CHEMIN_UML` peuvent être produites de manière déterministe à partir du graphe. Cela garantit que les noms, les attributs et les chemins restent exacts.

Pour `CHEMIN_METIER`, Neo4j calcule le chemin et le modèle peut seulement le transformer en phrase naturelle. Pour `DOCUMENTAIRE`, `METIER` et `HYBRIDE`, le modèle synthétise les passages contrôlés.

Cette séparation protège les faits structurés tout en conservant une réponse agréable à lire. Elle rend aussi le système moins dépendant d'un fournisseur précis.

## Slide 25 — Choix du fournisseur de génération

**Durée : 2 minutes**

L'utilisateur peut choisir Mistral, Gemini ou Groq. La requête suit le fournisseur sélectionné au lieu de déclencher silencieusement une cascade de secours. Cette décision rend le comportement compréhensible et facilite la comparaison.

Les fournisseurs diffèrent par leurs quotas, leur latence, leur fenêtre de contexte et la qualité de leurs réponses. Une erreur 429 chez Mistral signifie une limite d'usage, pas une panne du retrieval. Une erreur 413 chez Groq indique généralement un contexte trop volumineux. Gemini peut répondre correctement mais avec une latence supérieure.

Le résultat déterministe reste disponible même si la génération distante échoue, lorsque le mode le permet.

## Slide 26 — Séquence d'une question authentifiée

**Durée : 2 minutes**

L'utilisateur se connecte, choisit ou crée une conversation puis envoie une question. L'API vérifie la session, enregistre le message dans SQLite et appelle l'agent. L'agent déclenche le retrieval, appelle éventuellement le fournisseur choisi puis enregistre la réponse. Le navigateur recharge enfin la conversation.

La mémoire conversationnelle ne réside donc pas uniquement dans le prompt en cours. Les messages appartiennent à une conversation, elle-même rattachée à l'utilisateur authentifié. Cela permet de retrouver l'historique après une reconnexion et d'isoler les conversations entre utilisateurs.

## Slide 27 — Interface web

**Durée : 1 minute 30**

L'interface regroupe la liste des conversations, le fil de discussion, le choix du fournisseur et la visualisation du sous-graphe. Le rendu Markdown organise les explications, mais les réponses relationnelles peuvent aussi produire un schéma.

Le schéma reste complémentaire au texte. Pour éviter un dessin illisible, il faut limiter le sous-graphe aux relations pertinentes, utiliser une disposition stable, afficher les libellés et permettre le zoom. Montrer tout Neo4j dans une petite zone ne donne pas une meilleure explication.

## Slide 28 — Couverture de la chaîne par les tests

**Durée : 2 minutes**

La suite actuelle comporte 76 tests principaux et 15 sous-tests, soit 91 contrôles exécutés. Ils vérifient le routage, la résolution des entités, les chemins UML, les relations métier, l'assemblage du contexte, l'API et certains comportements de l'interface.

Ces tests limitent les régressions lorsque le retriever évolue. Ils ne remplacent toutefois pas une évaluation métier. Une réponse peut être techniquement conforme tout en restant peu utile ou insuffisamment précise. Il faut donc compléter les tests automatisés par un jeu de questions représentatives et une appréciation humaine.

## Slide 29 — Transition : démonstration

**Durée : 30 secondes**

Je vais maintenant montrer la chaîne complète avec plusieurs types de questions. L'objectif est d'observer le mode choisi, les données récupérées, la réponse et le schéma associé.

---

# Démonstration — 10 minutes

## Slide 30 — Interface et conversations

**Durée : 2 minutes**

Montrer la connexion, la création d'une conversation, le choix du fournisseur et le retour vers une conversation existante.

Dire : « SQLite associe chaque conversation à l'utilisateur connecté. Je peux créer un nouveau fil sans supprimer les précédents. Le fournisseur est un choix visible, ce qui évite qu'un échec soit masqué par un fallback inattendu. »

Si la démonstration échoue, utiliser la capture prévue et expliquer le flux sans attendre une résolution réseau.

## Slide 31 — Question structurelle UML

**Durée : 2 minutes**

Question conseillée : « Quels sont les différents types de NœudDeLigne dans l'UML ? »

Expliquer : « La présence de “dans l'UML” et la demande de types orientent la question vers le mode structurel. Le système consulte les héritages du graphe. La liste vient de Neo4j, puis elle est mise en forme. »

Question de secours : « Quels sont les attributs et les relations directes de la classe Ligne ? »

## Slide 32 — Question documentaire

**Durée : 2 minutes**

Question conseillée : « Comment construit-on un itinéraire ? »

Expliquer : « Ici, l'utilisateur demande une procédure. Le retriever privilégie les chunks documentaires. L'index hybride sélectionne les passages pertinents et le modèle les synthétise. Il ne faut pas répondre uniquement avec deux relations métier, car elles ne décrivent pas toutes les étapes. »

Observer dans le terminal : mode `DOCUMENTAIRE`, racine `Itineraire` et nombre de chunks.

## Slide 33 — Question métier et chemin

**Durée : 2 minutes**

Questions conseillées : « Quels équipements sont commandés par un poste d'aiguillage ? » puis « Existe-t-il un chemin métier entre un signal et une ligne ? »

Dire : « Le premier résultat utilise les relations métier qualifiées. Le second demande un parcours multi-sauts. Neo4j calcule la chaîne, puis le système la présente en phrase et en schéma. La visualisation ne doit contenir que le voisinage pertinent. »

Rappeler que `PROBABLE` et `VALIDE` doivent rester distinguables si les deux niveaux sont affichés.

## Slide 34 — Tests et journaux

**Durée : 2 minutes**

Montrer les résultats de tests puis une trace de requête. Lire une seule ligne utile : « Retrieval GraphRAG : mode DOCUMENTAIRE, racines Itineraire, quatre chunks ». Expliquer que cette ligne permet de distinguer trois problèmes : mauvais routage, mauvaise récupération ou échec du fournisseur.

Montrer ensuite le code HTTP. Un 200 sur les embeddings prouve que cette étape fonctionne. Un 429 sur le chat signale un quota de génération. Cette lecture évite de modifier le retriever lorsqu'une API externe constitue la cause réelle.

---

## Slide 35 — Limites actuelles

**Durée : 2 minutes**

Le projet possède encore plusieurs limites. La validation métier reste principalement automatique et nécessite une revue experte. Certains documents contiennent des formulations ambiguës ou des concepts absents du métamodèle. Le routage doit continuer à être testé avec des formulations variées. Les fournisseurs gratuits imposent des quotas et des latences difficiles à garantir pendant une démonstration.

Enfin, une visualisation trop dense devient rapidement illisible. L'application doit donc expliquer un sous-graphe pertinent plutôt que prétendre afficher tout le graphe en même temps.

Présenter ces limites comme les frontières actuelles du prototype, avec des actions identifiées pour les réduire.

## Slide 36 — Prochaines étapes

**Durée : 2 minutes**

La première priorité est la validation métier humaine. Une interface pourrait permettre à un expert d'accepter, corriger ou rejeter les relations probables. La deuxième consiste à construire un jeu d'évaluation stable couvrant les six modes et plusieurs formulations par intention.

Il faudra aussi mesurer la précision du retrieval, la fidélité des réponses, le temps de réponse et la disponibilité des fournisseurs. À plus long terme, un modèle local mieux dimensionné ou un service interne pourrait réduire la dépendance aux quotas publics, à condition de disposer des ressources matérielles et d'un niveau de qualité suffisant.

## Slide 37 — Conclusion

**Durée : 1 minute**

Pour conclure, ce projet ne consiste pas simplement à envoyer des documents à un chatbot. Il construit plusieurs représentations de la connaissance et choisit celle qui correspond à la question.

Le graphe UML apporte la structure exacte. Les chunks apportent le détail des procédures. Le graphe métier rend explicites des relations présentes dans les textes. Le retriever orchestre ces sources, tandis que le LLM transforme un contexte contrôlé en réponse accessible.

La phrase à retenir est celle affichée ici : la connaissance reste dans le graphe et dans les documents. Le modèle de langage la rend accessible.

Merci pour votre attention. Je suis maintenant disponible pour vos questions.

---

# Questions probables du public

## Pourquoi utiliser Neo4j plutôt qu'une base relationnelle ?

Parce que les demandes portent souvent sur des voisinages, des héritages et des chemins de plusieurs relations. Neo4j représente et parcourt directement ces liens. SQLite reste mieux adapté aux comptes et aux conversations.

## Quelle est la différence entre RAG et GraphRAG ?

Le RAG retrouve principalement des passages documentaires. Le GraphRAG ajoute une représentation explicite des entités et relations, puis utilise la navigation dans ce graphe pendant la récupération.

## Le LLM peut-il modifier le graphe ?

Pas pendant une conversation normale. Le pipeline d'extraction produit des candidats hors ligne. Des contrôles les qualifient avant import. Cette séparation évite qu'une réponse utilisateur crée immédiatement une nouvelle vérité dans Neo4j.

## Une relation validée est-elle certifiée par un expert ?

Non. Dans l'état actuel, `VALIDE` signifie confirmée par les contrôles automatiques et sa preuve documentaire. Une certification métier humaine reste une prochaine étape.

## Pourquoi conserver les relations probables ?

Elles contiennent une partie de la richesse extraite. Les supprimer ferait perdre des pistes utiles. Elles restent séparées du noyau validé et peuvent être soumises à un expert.

## Pourquoi proposer plusieurs LLM ?

Les fournisseurs diffèrent en disponibilité, quotas, vitesse et qualité. Le choix explicite facilite la comparaison et évite un fallback invisible. La connaissance récupérée reste indépendante du fournisseur.

## Peut-on fonctionner entièrement en local ?

Oui en principe, avec Neo4j, les index et un modèle servi par Ollama. En pratique, la qualité et la vitesse dépendent fortement du modèle, de la mémoire et du processeur ou GPU disponibles.

## Comment mesure-t-on la qualité ?

Il faut séparer la qualité du routage, du retrieval et de la génération. On mesure si le bon mode est choisi, si les bons éléments sont récupérés, puis si la réponse reste fidèle, complète et lisible.

# Plan de secours pour la démonstration

1. Si Mistral retourne 429, sélectionner Gemini ou Groq devant le public et expliquer que le retrieval reste identique.
2. Si tous les fournisseurs échouent, montrer une réponse structurelle déterministe et les captures des réponses génératives.
3. Si Neo4j est indisponible, utiliser les captures des sous-graphes et présenter les résultats des tests.
4. Si l'interface ne répond pas, montrer les slides 30 à 34 puis les logs enregistrés.
5. Ne pas déboguer longuement devant le public. Après trente secondes, passer au support de secours et poursuivre l'explication.

# Répartition temporelle recommandée

- Introduction et problème : 6 minutes.
- Architecture et données : 9 minutes.
- Pipelines UML et documentaire : 8 minutes.
- Extraction et validation métier : 10 minutes.
- Retrieval, agent et fournisseurs : 10 minutes.
- Démonstration : 10 minutes.
- Limites, conclusion et questions : 7 minutes.
