# Présenter le projet et préparer une démonstration

Cette trame remplace les deux anciens discours, conservés dans les archives. Elle présente le fonctionnement actuel sans annoncer des résultats non vérifiés. Adapter les captures à une exécution réelle et ne jamais afficher de clé API ou de mot de passe.

## 0–5 minutes : le besoin

« Nous avons deux sources complémentaires : un modèle informatique qui décrit les objets et leurs relations, et des fiches qui expliquent leur utilisation métier. Le chatbot doit consulter la bonne source selon la question. Une classe UML n’est pas un équipement réel et une relation trouvée dans un texte n’est pas automatiquement une règle validée par un expert. »

Montrer une fiche anonymisée et un extrait UML. Expliquer ce qu’est un nœud, une relation orientée et une propriété avec les données effectivement présentes.

## 5–15 minutes : préparer UML et les documents

« Le convertisseur transforme l’export XMI en JSON exploitable. Le builder traduit ce JSON en nœuds et relations Neo4j. Pour les fiches, il crée des documents et des petits passages, appelés chunks. Chaque passage reçoit une représentation numérique de son contenu : l’embedding. »

« La recherche plein texte retrouve des mots. La similarité vectorielle rapproche des contenus. Notre code fusionne ensuite les positions dans les classements, plutôt que d’additionner des scores de nature différente. »

Préciser qu’un index vectoriel est créé mais que le retrieval actuel calcule directement les similarités cosinus ; ne pas annoncer une interrogation de cet index si le code ne la fait pas.

Captures suggérées : JSON UML, nœud Classe avec son nom, Document relié à ses Chunk, résultat des comptages d’embeddings. Préparation : [guides 02](02_SOURCES_ET_UML.md) et [03](03_DOCUMENTS_ET_INDEXATION.md).

## 15–25 minutes : extraire le métier

« Pour chaque fiche, le programme sélectionne des classes candidates à partir des noms présents dans le texte. Ce premier tri réduit ce que le LLM doit examiner. Le LLM propose ensuite des concepts et relations, avec un passage justificatif. Le résultat est un JSON à contrôler, pas encore un graphe à considérer comme vrai. »

Distinguer les petits chunks utilisés pour la recherche des morceaux plus grands envoyés pendant l’extraction. Expliquer le rôle de l’extraction globale : répéter le même traitement sur les fiches et reprendre les documents déjà réussis lorsque les signatures concordent.

Captures : passage source, candidats, proposition JSON et citation correspondante. Préparation : [guide 04](04_EXTRACTION_METIER.md).

## 25–35 minutes : contrôler puis importer

« Les contrôles vérifient que la relation est structurée correctement, que ses deux concepts existent et que sa preuve et son sens sont étayés. Un niveau probable garde une information incertaine visible comme telle. Le niveau validé ici est documentaire et automatique : il ne signifie pas qu’un expert ferroviaire l’a approuvée. »

Montrer un exemple réellement accepté, un probable et un rejet avec son motif. Ne pas inventer ces exemples à partir de noms de classes. Expliquer que le contrôleur actuel confirme automatiquement peu de directions : cette limite influence le nombre de relations classées probables.

« Les pilotes sont les résultats sélectionnés avant import. Le builder métier les ajoute dans Neo4j et les relie aux documents, passages et classes quand les correspondances existent. Le graphe métier et UML cohabitent mais leurs types de nœuds et relations restent distincts. »

Captures : rapport de contrôle, pilote d’une fiche, provenance d’une relation importée. Préparation : [guides 05](05_VALIDATION_ET_PILOTES.md) et [06](06_IMPORT_ET_PROVENANCE.md).

## 35–45 minutes : répondre à une question

« Le navigateur envoie la question à l’API. L’API vérifie la session et la conversation. L’agent appelle le retriever, qui choisit le mode et rapproche les mots de la question des entités du graphe. Selon le besoin, il récupère les attributs UML, des passages de procédure ou des relations métier. »

« La réponse repose sur ces éléments. Certaines réponses structurelles sont formatées directement. Pour une explication documentaire, le fournisseur choisi rédige à partir du contexte disponible. SQLite conserve l’historique ; Neo4j conserve les connaissances. Changer de fournisseur ne corrige pas une mauvaise sélection de contexte. »

Pour les chemins UML, distinguer sens de parcours et orientation réelle des liens. Une chaîne techniquement connectée n’est pas nécessairement l’explication métier la plus pertinente. La recherche est bornée, pas exhaustive.

Préparation : [guide 07](07_RETRIEVAL_ET_APPLICATION.md).

## 45–55 minutes : démonstration préparée

Avant la séance, vérifier que `arianes` est importable, démarrer Neo4j et l’application, puis tester le fournisseur choisi. Préparer des captures de secours datées si le réseau ou les quotas empêchent le direct.

Poser séparément des questions simples pour rendre le routage observable :

1. « Quels sont les attributs directs de la classe UML Ligne ? »
2. « Quelle est sa classe parente dans le métamodèle UML ? » Si la résolution du pronom n’est pas fiable, répéter explicitement `Ligne` et expliquer la limite.
3. Une question de procédure portant sur une fiche réellement indexée, avec le texte source ouvert à côté.
4. Une question sur les relations métier d’un concept réellement importé, avec le niveau documentaire visible dans les données de contrôle.
5. Une question portant sur une entité absente, pour vérifier que l’application reconnaît son manque d’information.

Ne pas promettre une réponse précise avant d’avoir effectué cette répétition. Montrer le contexte et le résultat ensemble permet de distinguer une erreur de retrieval d’une mauvaise reformulation.

## 55–60 minutes : bilan et limites

« Le prototype relie des sources hétérogènes et rend leur consultation plus accessible. Ses limites portent sur la qualité des fiches, les correspondances entre concepts, le routage, la validation automatique et les contraintes des fournisseurs. Un modèle local dépend fortement du matériel. Un accès API professionnel et un environnement de développement stabilisé facilitent la continuité du service. »

Présenter des chiffres uniquement issus d’une exécution identifiable. Les tests automatisés ne remplacent ni les essais réels ni la relecture métier. Le prototype de reranking ML reste une piste optionnelle, pas un résultat de qualité démontré en production.

Terminer par trois suites : mieux relire les sources, évaluer des questions représentatives et stabiliser le déploiement. Voir le [guide 08](08_TESTS_EXPLOITATION_ML.md).
