# Guide d’utilisation — Ariane Cœur

## 1. À quoi sert l’application ?

Ariane Cœur est un assistant de consultation des connaissances Arianes. Vous posez une question en français ; l’application recherche les informations disponibles dans le métamodèle UML, les fiches de procédure et les relations métier enregistrées dans Neo4j.

Elle permet notamment de consulter les attributs d’une classe, de rechercher une procédure, d’explorer les relations entre des concepts et de rechercher un chemin entre deux classes UML.

Demander « comment créer un itinéraire » produit une explication : le chatbot ne crée pas un itinéraire dans le système Arianes. L’interface ne permet pas non plus d’importer une nouvelle fiche ou de modifier les relations du graphe.

## 2. Démarrage rapide

Si l’application est déjà démarrée par la personne responsable du projet, ouvrez l’adresse qu’elle vous communique et passez à la connexion.

Sur le poste où le projet est installé :

1. Démarrez l’instance Neo4j contenant les données Arianes.
2. Ouvrez PowerShell dans le dossier du projet.
3. Lancez le serveur :

```powershell
cd "C:\Users\0404836P\OneDrive - SNCF\AGENT_SNCF"
python -m uvicorn api:app --reload
```

4. Attendez le message `Application startup complete`.
5. Ouvrez [Ariane Cœur](http://127.0.0.1:8000/) dans votre navigateur.

Gardez le terminal ouvert pendant l’utilisation. L’adresse `127.0.0.1` désigne le poste sur lequel vous ouvrez le navigateur : elle ne donne pas accès au serveur d’un collègue depuis un autre ordinateur.

La base doit déjà être alimentée. Démarrer le serveur ne convertit pas les fichiers et ne lance pas les pipelines d’extraction ou d’import.

## 3. Créer un compte et se connecter

À la première utilisation :

1. Cliquez sur **Créer un compte**.
2. Saisissez un nom d’utilisateur de 3 à 50 caractères : lettres, chiffres, point, tiret ou tiret bas. Les espaces ne sont pas acceptés ; le nom est enregistré en minuscules.
3. Choisissez un mot de passe de 10 à 200 caractères.
4. Cliquez sur **Créer le compte**. Une inscription réussie ouvre la session.

Pour les utilisations suivantes, saisissez les mêmes identifiants puis cliquez sur **Se connecter**. Il s’agit d’un compte propre à cette application, distinct des comptes Neo4j, Google, Mistral ou Groq.

Les conversations sont rattachées au compte utilisateur. Le graphe de connaissances est commun aux utilisateurs autorisés de l’application. Un nouveau compte ne constitue donc pas une nouvelle base documentaire.

Il n’existe pas actuellement de bouton « Mot de passe oublié ». En cas de perte, contactez la personne responsable de l’application. Utilisez **Se déconnecter** lorsque vous quittez un poste partagé.

## 4. Se repérer dans l’écran

La colonne de gauche contient **+ Nouvelle conversation**, les conversations enregistrées et **Se déconnecter**.

La zone centrale affiche les questions et réponses. En bas, le menu **Gemini / Mistral / Groq** permet de choisir le fournisseur ; le champ de saisie sert à écrire une question.

Le bouton **Voir le graphe** ouvre un panneau d’exploration de Neo4j.

## 5. Poser une question

1. Choisissez un fournisseur configuré pour l’application.
2. Saisissez votre question.
3. Cliquez sur **Envoyer**, ou appuyez sur **Entrée**.
4. Attendez la réponse avant d’envoyer une nouvelle demande.

**Maj + Entrée** insère un retour à la ligne sans envoyer. La longueur maximale d’une question est de 4 000 caractères.

Le menu choisit le fournisseur qui rédige les réponses nécessitant un LLM. Il n’ouvre pas une connexion à votre compte personnel et ne demande pas de clé dans l’interface. Les clés et les noms exacts des modèles sont configurés sur le serveur. La présence d’un fournisseur dans le menu ne garantit pas que sa clé fonctionne ou que son quota est disponible.

Certaines réponses structurelles sont produites directement à partir du graphe. Changer de fournisseur ne change donc pas nécessairement leur formulation. Le fournisseur choisi n’est pas remplacé automatiquement en cas d’erreur : sélectionnez-en un autre et renvoyez la question si nécessaire.

La recherche par embeddings reste liée à Mistral dans cette version, même si Gemini ou Groq rédige la réponse. Quand les embeddings sont indisponibles, le code peut utiliser le plein texte seul ; la qualité de la recherche peut alors varier.

## 6. Bien formuler les différents types de questions

Le mode de recherche est choisi automatiquement. Il n’existe pas de menu permettant de forcer « UML », « documentaire » ou « métier ». Mentionnez explicitement le périmètre souhaité.

### Consulter la structure UML

Utilisez les mots « classe UML » ou « métamodèle UML » et, si possible, le nom exact de la classe.

Exemples :

> Quels sont les attributs directs de la classe UML Ligne ?

> Quelles sont les relations directes de la classe UML Ligne ? Précise leur type et leur orientation.

> Quelles classes héritent de la classe UML NoeudDeLigne ?

Pour une demande comportant plusieurs parties, vous pouvez demander attributs, relations et parents ensemble. Si la réponse oublie une partie, posez une question ciblée sur celle-ci. Les demandes de sous-graphe à plusieurs niveaux restent à vérifier dans cette version.

### Retrouver une procédure

Nommez la procédure ou l’objet et demandez les étapes, les champs et les conditions.

> Quelle est la procédure de création d’un itinéraire selon les fiches documentaires ? Présente les étapes dans l’ordre, les informations à renseigner et les conditions indiquées.

> Quels champs faut-il renseigner pour créer un quai, selon la fiche de procédure ?

> Que dit la documentation sur les détecteurs de boîtes chaudes ?

Une réponse n’est possible que si des passages pertinents sont disponibles et retrouvés. Ces questions sont des exemples d’utilisation, pas une garantie de présence de chaque fiche dans la base courante.

### Explorer le graphe métier

Précisez « graphe métier » pour éviter une confusion avec les associations UML.

> Quelles sont les relations du concept Quai dans le graphe métier ? Précise les conditions et les exceptions disponibles.

> À quoi un poste d’aiguillage est-il rattaché dans le graphe métier ?

> Quels équipements sont commandés par un poste d’aiguillage dans le graphe métier ?

Une relation métier représente une information extraite d’une fiche. Elle n’est pas nécessairement une relation du métamodèle UML.

### Rechercher un chemin UML

Donnez les deux classes et mentionnez explicitement UML.

> Recherche un chemin UML entre la classe Itineraire et la classe Ligne. Conserve le sens réel des relations et explique chaque étape.

La recherche autorise le parcours des relations dans les deux sens. Par exemple, une relation `A → B` peut être parcourue de B vers A pour trouver une connexion ; cela ne transforme pas la relation enregistrée en `B → A`.

Un chemin trouvé montre une connexion dans le modèle. Il ne constitue pas à lui seul une procédure ou une règle métier. Le chemin proposé doit être interprété avec ses types de relations, en particulier lorsqu’il passe par des classes génériques.

### Rechercher un chemin métier

> Existe-t-il un chemin dans le graphe métier entre Signal et Ligne ? Explique les relations présentes et leurs réserves éventuelles.

Une réponse indiquant qu’aucun chemin n’a été trouvé signifie qu’aucun chemin correspondant n’a été retourné dans les limites de la recherche. Elle ne démontre pas l’absence de lien dans le monde réel.

## 7. Gérer ses conversations

Cliquez sur **+ Nouvelle conversation** pour commencer un autre sujet. La nouvelle conversation est créée côté serveur lors de l’envoi de la première question ; un écran vide n’ajoute pas immédiatement un historique.

Cliquez sur un titre dans la colonne de gauche pour retrouver les messages et les schémas enregistrés. Vous pouvez poursuivre le sujet, par exemple avec « Et ses attributs ? ». Pour éviter les ambiguïtés, répétez le nom de la classe ou du concept lors d’un changement de sujet.

L’historique affiché n’est pas intégralement utilisé comme contexte à chaque demande : la mémoire de réponse est limitée. Une information ancienne peut nécessiter un rappel explicite.

Pour supprimer une conversation, cliquez sur sa croix **✕**, puis confirmez. L’interface ne propose pas d’annulation de cette suppression. Supprimer une conversation ne supprime pas les connaissances Neo4j.

## 8. Explorer le graphe

1. Cliquez sur **Voir le graphe**.
2. Choisissez **Métier** ou **Métamodèle**.
3. Utilisez la molette pour zoomer et le glissement du fond pour déplacer la vue.
4. Utilisez **Recentrer** pour retrouver la vue d’ensemble et **Plein écran** pour agrandir le panneau.
5. Saisissez un nom dans **Rechercher un nœud…** pour mettre en évidence les correspondances.
6. Cliquez sur un nœud pour afficher son nom, sa description et les relations disponibles dans l’aperçu.

La recherche du panneau porte sur les nœuds déjà chargés. Si un nom n’apparaît pas, cela ne prouve pas qu’il est absent de Neo4j.

**Interroger ce concept** prépare une question dans le champ de saisie. Relisez-la, précisez « UML » si vous visez une classe du métamodèle, puis cliquez sur **Envoyer**.

Le panneau affiche un extrait borné du graphe, pas toute la base. Certains nœuds ou liens peuvent être absents de cet extrait, et plusieurs groupes séparés peuvent apparaître.

## 9. Lire les réponses et les schémas

Un **Schéma des relations** peut accompagner une réponse lorsque des relations sont disponibles. Il complète le texte ; il ne prouve pas à lui seul que la relation est correcte et ne représente pas nécessairement toutes les relations de la base.

Dans le graphe métier :

- **VALIDE** désigne une validation documentaire selon les contrôles du pipeline ; ce n’est pas automatiquement une validation par un expert ferroviaire.
- **PROBABLE** désigne une information conservée avec une incertitude. Les conditions, exceptions et réserves doivent être prises en compte.

L’interface ne rend pas encore tous ces statuts visibles de manière uniforme. Les anciens imports peuvent également provenir d’une version antérieure du pipeline.

Les références détaillées aux fichiers et passages ne sont pas affichées dans les réponses de cette version. Pour vérifier une information importante, consultez la fiche de référence avec la personne responsable du corpus. L’assistant est un outil de consultation, pas une consigne opérationnelle faisant autorité.

Si le texte et le schéma se contredisent, signalez la question exacte et la réponse au responsable. Ne déduisez pas une règle de cette contradiction.

## 10. Résoudre les difficultés courantes

### La page ne s’ouvre pas

Vérifiez que le serveur est démarré, que son terminal est encore ouvert et que vous utilisez le port affiché. Si le port 8000 est indisponible :

```powershell
python -m uvicorn api:app --reload --port 8001
```

Ouvrez alors [l’application sur le port 8001](http://127.0.0.1:8001/).

### Neo4j est indisponible

Démarrez l’instance attendue. La personne responsable peut contrôler `NEO4J_URI`, `NEO4J_USER` et `NEO4J_PASSWORD` dans la configuration.

[Le contrôle de santé](http://127.0.0.1:8000/health) vérifie la connexion Neo4j. Un résultat positif ne certifie ni la présence des fiches, ni l’état des quotas LLM, ni la qualité des réponses.

### Le fournisseur refuse la requête ou signale une surcharge

Le responsable doit consulter le code d’erreur dans le terminal. Une erreur 429 indique une limitation de débit ou de quota ; 401/403 peut concerner la clé ou les permissions ; 413 indique une requête trop volumineuse. Un message générique ne suffit pas à conclure à une panne du fournisseur.

Attendez avant de réessayer, ou choisissez un autre fournisseur configuré. Pour une demande volumineuse, posez une question plus ciblée ou commencez une nouvelle conversation.

### La réponse est hors sujet ou utilise le mauvais mode

Créez une nouvelle conversation et indiquez le périmètre explicitement : « dans le métamodèle UML », « selon la fiche de procédure » ou « dans le graphe métier ». Répétez le nom complet de l’objet.

### La réponse est trop courte

Précisez le contenu attendu : « Décris les étapes dans l’ordre, les champs obligatoires, les conditions et les exceptions présentes dans la fiche ». Une demande plus détaillée ne peut toutefois pas compenser des passages manquants.

### Une réponse est déjà en cours

Attendez sa fin avant de renvoyer la question. Si le traitement échoue, consultez l’erreur affichée et les journaux. Évitez de multiplier les demandes identiques.

## 11. Parcours de découverte en cinq minutes

1. Connectez-vous et choisissez un fournisseur configuré.
2. Demandez : « Quels sont les attributs directs de la classe UML Ligne ? »
3. Créez une nouvelle conversation et demandez une procédure documentaire.
4. Créez une nouvelle conversation et demandez les relations d’un concept dans le graphe métier.
5. Ouvrez **Voir le graphe**, sélectionnez un nœud et essayez **Interroger ce concept**.
6. Rouvrez une ancienne conversation pour vérifier la sauvegarde de l’historique.

Ces étapes font découvrir les fonctions principales ; elles ne constituent pas une validation complète du système.

## 12. Informations pour la personne qui installe l’application

Le serveur attend un environnement Python avec les dépendances du projet, une base Neo4j alimentée, son mot de passe et au moins une clé parmi `MISTRAL_API_KEY`, `GEMINI_API_KEY` et `GROQ_API_KEY`. Les variables de modèle doivent désigner des modèles accessibles avec les clés utilisées ; les valeurs par défaut du code ne garantissent pas leur disponibilité.

Dans un environnement Python adapté au projet :

```powershell
python -m pip install -r requirements.txt
```

Les dépendances ne sont pas encore verrouillées par version. Une installation sur un nouveau poste doit être vérifiée avant une démonstration.

Les paramètres privés sont dans `.env`. Ne saisissez pas les clés dans le chat. Après une modification de configuration, redémarrez le serveur.

Par défaut, les comptes et conversations sont conservés dans `ariane_coeur.db`, tandis que les connaissances sont dans Neo4j. Sauvegarder seulement les fichiers Python ne sauvegarde pas ces deux bases.

Pour arrêter le serveur local, utilisez **Ctrl + C** dans son terminal. Cela ne supprime pas les conversations enregistrées.

Les commandes de reconstruction et d’import sont réservées à la maintenance du corpus. Elles ne sont pas nécessaires à l’utilisation quotidienne et ne doivent pas être lancées pour résoudre un simple problème d’affichage.
