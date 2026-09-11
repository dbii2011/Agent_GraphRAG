# Captures à ajouter au rapport

Déposez les images dans ce dossier avec les noms exacts ci-dessous. Le rapport les affichera automatiquement. En leur absence, un cadre réservé reste visible dans le PDF.

Avant toute capture, masquez les clés API, mots de passe, cookies, jetons, adresses internes et données personnelles.

1. `architecture_globale.png` — schéma global XMI/JSON/Documents → Neo4j → Retriever → Mistral → API/UI.
2. `xmi_source.png` — extrait lisible du métamodèle XMI.
3. `json_converti.png` — classe JSON avec attributs et relations.
4. `neo4j_schema.png` — sous-graphe de classes, attributs et relations techniques.
5. `arborescence_projet.png` — explorateur ou commande montrant les fichiers du dépôt.
6. `neo4j_indexes.png` — résultat de `SHOW INDEXES` et éventuellement `SHOW CONSTRAINTS`.
7. `neo4j_compteurs.png` — compteurs de labels, relations et chunks munis d'embeddings.
8. `reponse_structurelle.png` — réponse sur une classe, par exemple `Ligne`.
9. `reponse_documentaire.png` — réponse fondée sur une fiche de procédure avec sources.
10. `frontend_connexion.png` — page de connexion ou d'inscription.
11. `frontend_conversations.png` — liste des conversations et conversation active.
12. `memoire_conversation.png` — question initiale puis question de suivi contextuelle.
13. `proposition_metier.png` — JSON extrait par le pipeline métier, sans secret.
14. `graphe_metier_neo4j.png` — concepts métier reliés aux classes et documents.
15. `reranker_metriques.png` — terminal de l'entraînement et de l'évaluation ML.
16. `tests_29_passes.png` — résultat de `python -m pytest -q`.
17. `evaluation_12_sur_12.png` — résultat de `evaluate_graphrag.py`.
18. `github_depot.png` — page du dépôt privé sans information sensible.

Conseils :

- privilégier le format PNG et une largeur d'au moins 1400 pixels ;
- recadrer l'image sur l'information importante ;
- utiliser le même thème visuel pour toutes les captures ;
- éviter les captures trop longues : en créer plusieurs si nécessaire ;
- mettre à jour dans `rapport.tex` les chiffres qui évoluent après reconstruction du graphe.
