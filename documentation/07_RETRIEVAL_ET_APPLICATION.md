# Phase 7 — De la question à la réponse

[Sommaire](README.md) · [Phase suivante](08_TESTS_EXPLOITATION_ML.md)

## Entrée et sortie

L'interface envoie question, identifiant de conversation et fournisseur à `POST /ask`. `api.py` vérifie l'utilisateur et la conversation, lit l'historique SQLite, enregistre la question et appelle `AgentLG.ask`. La sortie contient le texte et, éventuellement, un schéma de relations. L'API enregistre cette sortie avant de la retourner au navigateur.

Le module `retrieval.py` rassemble les données ; `agent.py` les présente ou demande leur reformulation au fournisseur choisi. La requête conversationnelle normale lit Neo4j ; elle ne déclenche pas les imports.

## Routage et résolution

`_necessite_contexte` décide si une relance a besoin de la question précédente. Certaines mentions explicites de classe ou concept permettent de reconnaître une question autonome. Cette détection reste heuristique.

`analyser_question` utilise des mots et expressions pour sélectionner les sources. Six modes sont présents :

- STRUCTURE : classes, attributs et voisinage UML.
- DOCUMENTAIRE : passages de définition ou de procédure.
- METIER : concepts et relations métier.
- CHEMIN_UML : connexion entre deux classes du modèle.
- CHEMIN_METIER : parcours entre concepts métier.
- HYBRIDE : combinaison des sources sélectionnées par le routeur.

Il ne s'agit pas d'un classifieur entraîné ni d'un choix libre du LLM. Une formulation nouvelle peut être mal routée.

`resoudre_classes` compare la question au catalogue chargé depuis Neo4j, à l'aide de la normalisation, des noms et de scores lexicaux. Exemple : « nœud de ligne » peut être rapproché de `NoeudDeLigne`. Le résultat contient les candidats et les racines retenues ; reconnaître une racine ne garantit pas que tout le contexte associé soit pertinent.

La normalisation du retriever et celle de l'extraction métier ne sont pas identiques : le traitement CamelCase du premier ne doit pas être attribué automatiquement au second.

## Récupération du contexte

`_construire_sous_graphe` récupère actuellement le voisinage UML direct, ses attributs et relations, avec des limites de volume. Reconnaître une demande « deux niveaux » ne signifie pas que cette profondeur soit entièrement prise en charge.

`_construire_graphe_metier` sélectionne des concepts et leurs relations actives admises. `_chercher_preuves_metier` récupère les chunks mentionnés par ces relations. `_chercher_chunks` exécute la recherche décrite en phase 3 : l'orchestrateur demande quatre passages pour la branche documentaire, puis privilégie les preuves métier et borne l'ensemble à douze chunks.

`contexte_pour_llm` sérialise le résultat : mode, racines, sous-graphes, chemins et passages. Le contexte est une sélection, pas une copie de toute la base.

## Les chemins UML autorisent les deux sens

La recherche UML explore `HERITE_DE`, `COMPOSE_DE`, `ASSOCIE_A` et `AGREGE` sans imposer un parcours dans le sens de chaque flèche. Elle conserve en revanche source et cible réelles de chaque relation.

Un parcours B → A peut donc utiliser une relation stockée A → B. La réponse doit rendre cette différence compréhensible, sans inventer une relation inverse. Le choix de rechercher dans les deux sens est conservé.

La recherche est bornée, retient d'abord jusqu'à 80 chemins ordonnés par longueur, puis les filtre et classe. Un choix LLM parmi les candidats peut intervenir dans l'agent. Il ne s'agit ni de tous les chemins possibles, ni d'une garantie du chemin le plus pertinent fonctionnellement. Un chemin via une classe générique peut être structurellement existant mais peu explicatif.

Le chemin métier suit une autre requête : plus court chemin jusqu'à cinq relations, parmi les éléments admis. Ne pas attribuer son algorithme au chemin UML.

## Réponse et fournisseur

Les réponses STRUCTURE utilisent `_formater_structure_uml` pour une restitution déterministe. Les questions composées peuvent demander attributs, parents et associations ; certaines formulations restent à tester.

Les chemins UML sont présentés par `_formater_chemin_uml` après sélection. Les modes documentaire, métier et hybride sollicitent généralement un LLM. Le fournisseur sélectionné parmi Mistral, Gemini et Groq est appelé explicitement ; la présence d'anciennes fonctions de secours Ollama ne signifie pas qu'une cascade automatique soit le parcours actif.

Le prompt demande une réponse fondée sur le contexte, des conditions et exceptions, et une formulation prudente pour PROBABLE. Ces consignes ne garantissent pas la fidélité. Les références techniques aux fichiers et passages sont masquées dans la réponse visible.

`_schema_depuis_retrieval` construit un schéma complémentaire et borné. Son alignement complet avec le texte reste une limite connue. Le panneau « Voir le graphe » est encore une autre projection limitée de Neo4j, et non l'ensemble de la base.

## Comptes, conversations et limites d'exploitation

SQLite conserve utilisateurs, sessions, conversations, messages et visualisations. Le mot de passe est dérivé avec sel ; les sessions utilisent un cookie HttpOnly et des jetons dont l'empreinte est stockée. Les conversations sont vérifiées par propriétaire.

La mémoire transmise au modèle est bornée. Une nouvelle conversation ne supprime pas les anciennes. Le verrou ajouté contre les demandes simultanées est local au processus ; il ne règle pas une architecture multi-workers.

`/health` vérifie Neo4j. `/providers` indique les clés configurées, pas leur validité auprès des fournisseurs. La présence d'un code HTTP 200 pour les embeddings ne prouve pas la disponibilité de l'API de génération.
