# Audit technique du projet Arianes — 10 septembre 2026

## Conclusion

La séparation des responsabilités est pertinente, mais la chaîne n'est pas encore suffisamment fiable pour affirmer que tout est correct. Les problèmes ne sont pas limités au prompt ou au choix du LLM : certains prennent naissance lors de la conversion et de l'import des données.

Cet audit n'a modifié aucun code applicatif et n'a effectué aucune écriture dans Neo4j. Ce document est un livrable d'audit.

## Périmètre et limites

Examen du code actif : API, interface, agent, retrieval, builders, pipelines, évaluation, prototype ML et tests ; inventaire de l'organisation et des archives. Les constats ci-dessous distinguent défauts visibles dans le code et conséquences possibles. Il ne s'agit pas d'une certification métier des fiches ferroviaires, d'un contrôle exhaustif du contenu des PDF/PPTX, ni d'une validation de chaque relation du corpus.

La connexion Neo4j à 127.0.0.1:7687 a été refusée pendant la vérification finale. Les constats sur l'import décrivent donc des mécanismes présents dans le code ; leur impact exact dans la base actuelle reste à mesurer. Les fournisseurs LLM n'ont pas été sollicités pour cet audit.

Commande de tests : `python -m pytest tests -q --tb=short`.

Résultat final : **81 tests réussis, 15 sous-tests réussis, 1 avertissement**. La première exécution avait deux erreurs de préparation liées aux permissions du dossier temporaire Windows ; la relance autorisée hors bac à sable les a résolues. L'avertissement concerne la compatibilité Starlette/httpx du client de test.

## 1. Défauts prioritaires

### P1 — L'import UML peut perdre des informations

Fichier : `arianes/graph/uml_builder.py`, lignes 58 et 94–101.

- Une classe est fusionnée par son nom, puis sa description et son caractère abstrait sont systématiquement remplacés. Une définition externe incomplète importée après une définition complète peut donc la dégrader.
- Une relation est fusionnée seulement par classe source, type et classe cible. Deux associations ayant les mêmes extrémités mais des rôles différents deviennent une seule relation ; le dernier rôle et la dernière cardinalité écrasent les précédents.
- Les liens de type d'un attribut sont ajoutés sans résolution des contradictions. Plusieurs types concurrents peuvent subsister pour un même attribut.
- La cardinalité `0..*` est volontairement omise à l'import, alors qu'elle porte une information UML.

Conséquence : même un retriever parfait ne peut pas restituer un modèle dont l'import a perdu les rôles ou mélangé les définitions.

Correction recommandée : conserver les identifiants XMI, définir une priorité entre définition complète et référence externe, identifier les relations avec leur rôle/identifiant d'origine, signaler les conflits avant import. Tester les imports dans plusieurs ordres.

### P1 — La conversion XMI n'utilise pas le répertoire de données actuel

Fichier : `arianes/pipelines/xmi_to_json.py`, lignes 236–249.

Le convertisseur écrit dans `Data/` relativement au répertoire courant, tandis que le builder lit `project_data/uml`. La centralisation dans `arianes/paths.py` n'est donc pas appliquée de bout en bout.

Autres points de fidélité à contrôler : résolution des références de type rencontrées plus tard dans le fichier, valeur par défaut `P-String` pour des types non résolus, priorité des descriptions de stubs, orientation et rôle des extrémités d'association. Une association UML ne doit pas être interprétée comme navigable simplement parce qu'une extrémité apparaît en premier dans le XML.

Correction recommandée : conversion en deux passes, identifiants conservés, références non résolues explicites, comparaison d'un échantillon JSON avec le XMI source.

### P1 — Le score documentaire ne prouve pas le sens d'une relation

Fichier : `arianes/pipelines/validation_metier.py`, lignes 200–243.

Le critère `direction_confirmee` est calculé par `not r.get("corrections")`. L'absence de correction n'est pas une vérification du sens source → cible. Le prédicat est vérifié par des indices lexicaux et l'identification des concepts par leur présence dans le dictionnaire des concepts.

Ces règles constituent des contrôles techniques utiles, mais pas une démonstration que la phrase implique le triplet. Le champ `score_confiance` n'est pas une probabilité calibrée de vérité métier.

Correction recommandée : distinguer conformité du format, présence de la preuve, compatibilité sémantique et validation experte. Conserver explicitement les incertitudes sur la direction et les modalités.

### P1 — PROBABLE et VALIDE sont confondus dans l'exploitation

Fichiers : `selection_prudente.py`, `metier_builder.py` lignes 68 et 132, `retrieval.py` lignes 274–299 et 749–793.

La sélection accepte VALIDE et PROBABLE. Le builder conserve le statut, mais met `valide=true` sur les concepts et les relations importés dans les deux cas. Le retriever filtre principalement sur ce booléen.

Inclure les relations probables peut être un choix légitime ; les présenter ensuite comme toutes validées ne l'est pas. La sélection met également tous les concepts retenus au statut VALIDE sans contrôle indépendant.

Correction recommandée : nommer le booléen `actif` ou `importable`, filtrer les statuts explicitement selon le mode choisi et transmettre l'incertitude au texte et au schéma.

### P1 — Les chemins UML mélangent parcours et signification

Fichier : `arianes/retrieval.py`, autour des lignes 387–409 ; `arianes/agent.py`, sélection et présentation des chemins.

La requête explore les relations dans les deux sens : `(depart)-[...*1..N]-(arrivee)`. Elle conserve correctement leurs extrémités réelles, mais ce n'est pas un parcours strictement unidirectionnel. L'expression « chemin orienté » prête donc à confusion.

Le code trie par longueur et ne conserve que 80 candidats avant le classement détaillé. Il ne cherche pas tous les chemins possibles. Les bonus de motifs et pénalités de classes génériques restent heuristiques. Une succession d'héritages et d'associations ne démontre pas à elle seule une relation fonctionnelle entre les classes de départ et d'arrivée.

Correction recommandée : séparer deux contrats : parcours respectant toutes les flèches, et explication structurelle autorisant explicitement remontées/descentes d'héritage. Évaluer les chemins sur des exemples annotés ; autoriser l'absence de chemin pertinent. Corriger d'abord la fidélité du graphe, avant de modifier encore les bonus ou le prompt.

### P1 — Le filtre documentaire par classes n'exclut pas les autres documents

Fichier : `arianes/retrieval.py`, lignes 858–886.

Le `WHERE ... c.nom IN $classes` est rattaché à un `OPTIONAL MATCH`. Une ligne documentaire sans correspondance est conservée avec une classe nulle. Le code ne réalise donc pas le filtrage strict annoncé par son commentaire.

Correction recommandée : appliquer une condition explicite au niveau des documents, ou distinguer volontairement recherche globale et recherche restreinte. Ajouter un test avec un document très similaire mais hors du périmètre demandé.

## 2. Autres risques fonctionnels

### Recherche documentaire et index

- L'index vectoriel est créé, mais cette recherche utilise `vector.similarity.cosine` sur les chunks, pas une interrogation de l'index vectoriel. Il s'agit d'une recherche vectorielle par calcul direct ; le coût augmente avec le corpus.
- Un embedding absent peut produire un score nul non pris en charge avant la comparaison au seuil.
- Les exceptions du plein texte sont silencieusement ignorées : une panne d'index devient difficile à diagnostiquer.
- Un document lié à plusieurs classes peut produire plusieurs lignes pour un même chunk, ce qui perturbe la fusion des rangs sans déduplication préalable.
- Un petit nombre de passages ne garantit pas la couverture d'une procédure complète.

### Routage, mémoire et réponses

- Le routage reste fondé sur des mots et motifs ; certaines formulations ou questions comportant plusieurs intentions sont fragiles.
- La reprise du contexte antérieur peut ajouter des entités d'une ancienne question à une question déjà autonome.
- La construction du voisinage UML est essentiellement à un saut : reconnaître une demande « deux niveaux » ne suffit pas à exécuter cette profondeur.
- La réponse structurelle utilise des branches déterministes et des détections lexicales. Les questions combinant attributs, parents, associations et compositions exigent des tests de complétude spécifiques.
- La sélection LLM d'un chemin n'intervient pas systématiquement, notamment lorsqu'un seul candidat subsiste. Ce candidat n'est pas automatiquement pertinent.
- Le schéma est une projection limitée ; il ne faut pas le présenter comme l'intégralité des relations disponibles. Texte et schéma doivent partir de la même sélection structurée.

### Réimport et provenance

- Les identifiants documentaires reposent sur un découpage de chaîne par `/`, fragile pour les chemins Windows.
- Le rattachement document → classe repose sur le nom du fichier et une correspondance exacte ; les noms abrégés doivent être contrôlés.
- Une réindexation ne retire pas nécessairement les anciens chunks devenus inutiles.
- Un triplet métier corrigé et réimporté n'inactive pas nécessairement l'ancien triplet.
- Les descriptions et alias des concepts existants peuvent être remplacés lors d'imports successifs.
- Fusionner uniquement sur un nom normalisé peut confondre des concepts homonymes de domaines différents.

L'idempotence d'un `MERGE` à entrée identique n'équivaut pas à une synchronisation correcte après modification des sources.

### API et exploitation

- Deux requêtes simultanées dans la même conversation peuvent obtenir la même position : réservation et écriture des messages ne constituent pas une opération atomique par conversation.
- `FileResponse("index.html")` dépend du répertoire de lancement.
- L'authentification et les contrôles d'appartenance sont de bonnes bases, mais une mise en production demanderait notamment HTTPS/cookie sécurisé, limitation des tentatives, politique d'inscription et gestion des erreurs.
- L'endpoint de schéma n'a pas le même contrôle d'accès que les conversations.
- Les modules API, agent, retrieval et le HTML concentrent beaucoup de responsabilités : leur découpage serait utile après stabilisation des contrats.
- Aucun manifeste standard de dépendances Python n'a été trouvé dans l'inventaire. La reproduction sur un autre poste n'est pas garantie.

## 3. Bilan par fichier actif

### Application

- `api.py` : démarrage, authentification, historique, questions et graphe. Architecture fonctionnelle, mais concurrence des messages, chemins relatifs et durcissement de déploiement à traiter.
- `index.html` : interface et visualisations. Distinguer clairement extrait affiché et graphe complet ; tester la cohérence texte/schéma et les longues étiquettes. Un affichage lisible ne valide pas les relations.
- `arianes/agent.py` : appels fournisseurs, orchestration, réponses structurelles et schémas. Trop de logique de présentation et de sélection mélangée ; expliciter les contrats déterministes et génératifs.
- `arianes/retrieval.py` : routage, résolution des entités, recherche UML/métier/documentaire et fusion. Module central ; corriger filtrage, profondeur, contrats de chemins et observabilité avant d'ajouter des heuristiques.
- `arianes/paths.py` : bonne centralisation des chemins absolus ; adoption incomplète ailleurs.
- `arianes/evaluation.py` : vérifie notamment mode, racines et source retrouvée. Utile pour le retrieval, insuffisant pour valider la justesse et la complétude de toutes les réponses finales.
- Fichiers `__init__.py` : organisation en packages ; aucun problème prioritaire identifié.

### Construction des graphes

- `arianes/graph/uml_builder.py` : import UML, découpage documentaire et embeddings. Priorité haute : identité des éléments, conflits, cardinalités, provenance et synchronisation.
- `arianes/graph/metier_builder.py` : import des concepts, relations et preuves. Priorité haute : propagation des statuts, fusion des concepts et remplacement des relations obsolètes.

### Pipeline métier et conversion

- `xmi_to_json.py` : conversion du modèle source ; répertoire de sortie et fidélité des références à corriger.
- `extraction_metier.py` : candidats issus des classes, extraction LLM par passages, normalisation et consolidation. La présence d'une classe candidate guide le LLM sans prouver qu'elle est évoquée. Harmoniser la normalisation des noms avec celle du retriever ; contrôler collisions d'identifiants et références.
- `extraction_globale.py` : exécution sur le corpus, checkpoints, agrégation. La reprise par existence de fichier ne détecte pas les changements de source ou de configuration ; ajouter empreintes et manifeste.
- `validation_metier.py` : contrôles et classement gradué. Ne pas assimiler contrôle lexical et validation sémantique ; isoler et documenter les corrections spécifiques à certaines fiches.
- `recontrole_metier.py` : relecture hors ligne des preuves et plages de lignes. Bonne protection du périmètre documentaire ; harmoniser les répertoires/version par défaut avec les étapes suivantes.
- `selection_prudente.py` : sélection globale. Le nom « prudente » ne signifie pas « expertisée » ; elle inclut aussi PROBABLE.
- `generer_pilotes.py` : produit des pilotes par document. Vérifier la couverture par rapport à un manifeste du corpus et rendre visible la version des sources.
- `import_pilote.py` : préparation/import du pilote historique Post. Ne pas le confondre avec l'import global ; ses contrôles et ses chemins spécifiques ne couvrent pas automatiquement tous les documents.
- `normalisation_metier.py` : fusion de doublons. Opération sensible : une sauvegarde utilisant des relations non orientées et des `id` absents sur certaines cibles ne garantit pas une restauration fidèle. Exiger export restaurable, prévisualisation et transaction avant fusion destructive.

### Prototype ML

- `ml/reranker.py` : reranker linéaire léger. Vérifier dimensions, valeurs finies et échelles du modèle chargé. Le score ne constitue pas une validation métier.
- `ml/train_reranker.py` : entraînement du prototype. Un résultat d'entraînement n'est pas une preuve de généralisation ; garder un jeu de questions indépendant.
- `ml/build_dataset_from_evaluation.py` : étiquettes faibles basées sur le document attendu, avec texte de chunk vide. Cela ne mesure pas la pertinence précise du passage et crée un décalage avec les caractéristiques calculées en exploitation.
- `ml/evaluate_reranker.py` : comparaison du classement. Interpréter les résultats selon la qualité et l'indépendance du jeu d'évaluation.
- `ml/models/reranker_prototype.json` : modèle de démonstration, pas un modèle métier certifié.

### Tests, documentation, archives et données

- Les dix modules de `tests/` couvrent des comportements utiles : API, propriété des conversations, sécurité, extraction, validation, import, retrieval, sélection et ML. Les tests réussis ne couvrent pas tous les défauts de fidélité des données décrits ici.
- `tests/evaluation_questions.json` : scénarios attendus à compléter par questions composées, paraphrases, profondeur, orientation et cas négatifs.
- `README.md` et `documentation/` : harmoniser commandes, chemins, versions et définition de « validé ». Une commande unittest ne collecte pas les fonctions de test pytest ordinaires.
- `legacy/` : archives, pas chaîne de référence. Exclure ses scripts de la collecte automatique des tests ; éviter les modules de test qui contactent une base dès leur import.
- `project_data/` : conserver sources, propositions, corrections et pilotes, mais avec un manifeste indiquant leur filiation et la version réellement importée. Un nom de dossier V3 ne suffit pas à garantir l'état de Neo4j.
- `reports/` et présentations : vérifier les affirmations contre le code actuel, notamment « index vectoriel utilisé », « chemin orienté », « graphe validé » et nombre de tests. Leur contenu rédactionnel complet n'est pas certifié par cet audit.
- `.gitignore` : protège notamment secrets locaux, caches et bases. Il ne retire pas un secret déjà commité et ne constitue pas un audit de l'historique Git.

## 4. Ordre de correction recommandé

1. Sauvegarder la base et figer un corpus de référence, sans reconstruire immédiatement la base actuelle.
2. Fiabiliser XMI → JSON → UML : identifiants, types, rôles, cardinalités, descriptions et sens.
3. Clarifier les statuts métier et la synchronisation des réimports.
4. Corriger le filtrage documentaire, les valeurs manquantes et les profondeurs demandées.
5. Définir séparément parcours dirigé et explication structurelle UML ; tester ces deux contrats.
6. Garantir que texte et schéma présentent les mêmes faits avec les mêmes réserves.
7. Ajouter des tests d'intégration sur une petite base reproductible, puis seulement comparer les LLM.
8. Finaliser dépendances, configuration, documentation et déploiement.

## 5. Tests de non-régression manquants à ajouter

- Importer définition complète puis stub, puis inverser l'ordre : résultat identique attendu.
- Importer deux associations de mêmes extrémités avec deux rôles : les deux doivent subsister.
- Vérifier références XMI en avant, cardinalités et orientation des compositions.
- Modifier un document puis réimporter : aucun chunk obsolète actif.
- Corriger un triplet puis réimporter : ancien triplet inactif.
- PROBABLE doit rester identifiable dans retrieval, réponse et schéma.
- Demander une procédure avec un document hors sujet très similaire : le périmètre doit être respecté.
- Tester un chunk sans embedding, un index absent et des documents liés à plusieurs classes.
- Question UML composite : toutes les rubriques demandées doivent être présentes.
- Deux niveaux UML : présence réelle des voisins du deuxième niveau.
- Parcours dirigé : aucune arête parcourue à l'envers ; explication structurelle : inversions explicitement signalées.
- Nouvelle question autonome après une ancienne question sur une autre classe : aucune contamination des racines.
- Deux questions simultanées dans la même conversation : ordre et appariement stables.

## Conclusion opérationnelle

Ne pas tout jeter et ne pas tout réorganiser une nouvelle fois. L'organisation générale est exploitable. Il faut stabiliser les contrats entre conversion, import, validation et retrieval. Changer de LLM ne corrigera ni une association écrasée ni un statut de confiance ambigu.
