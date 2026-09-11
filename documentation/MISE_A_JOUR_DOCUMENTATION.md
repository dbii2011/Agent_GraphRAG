# Bilan de la révision documentaire

Date : 11 septembre 2026.

## Périmètre et méthode

Lecture des huit textes techniques existants et confrontation avec les modules actifs : API, agent, retrieval, chemins, builders, pipelines, évaluation, prototype ML et configuration de tests. Réécriture de la documentation courante par phase. Les anciens textes ont été déplacés sans modification dans `archives/2026-09-11/` : aucune suppression définitive.

Le guide d’utilisation et le rapport de stage PDF ont été conservés sans modification à la demande de l’utilisateur. Leurs descriptions historiques ne constituent pas une certification du comportement actuel. Le seul changement apporté à la structure du code pendant cette révision est le renommage du package `ariane/` en `arianes/` ; le contenu des fichiers Python n’a pas été modifié. Aucune extraction LLM ni import Neo4j n’a été lancé. La suite locale a ensuite été exécutée : 86 tests et 15 sous-tests réussis, avec un avertissement de dépréciation Starlette/httpx.

## Remplacement des anciens documents

- `README_PROJET.md` : remplacé par le sommaire et les guides 01 à 08.
- `Commandes.txt` : remplacé par des commandes commentées par phase, avec prérequis et effets. Les anciennes instructions propres au poste et erreurs de terminal ne sont plus une procédure d’installation.
- `BILAN_SCRIPTS_PYTHON.md` : réécrit pour les modules actuels, en distinguant les scripts actifs des prototypes historiques.
- `GUIDE_GRAPHE_METIER.md` : remplacé par les guides 04, 05 et 06.
- `CORRECTIONS_METIER.md` : remplacé par l’explication des contrôles actuels, sans présenter V3 comme la dernière version du contrôleur.
- `PILOTE_METIER.md` : remplacé par la distinction entre pilotes documentaires généraux et parcours d’import spécialisé Post.
- `SCRIPT_ORAL_PRESENTATION_1H.md` et `SCRIPT_PRESENTATION_ARCHITECTURE_PIPELINES.md` : remplacés par la trame 09, reliée aux guides techniques.

## Incohérences rendues explicites

1. Le dossier physique a été renommé de `ariane/` vers `arianes/`, conformément aux imports existants. La documentation et le code utilisent désormais le même namespace.
2. Un index vectoriel créé n’implique pas qu’il est interrogé : le retrieval actuel utilise un calcul direct de cosinus pour sa recherche vectorielle.
3. Les données métier probables peuvent être importées par le builder général ; elles ne doivent pas être présentées comme une validation humaine.
4. Les anciens noms de sorties V2/V3 ne certifient pas un recontrôle par le contrôleur actuel, qui déclare la version 4. Certains chemins par défaut diffèrent entre étapes : les guides utilisent des chemins explicites.
5. La confirmation automatique de direction est limitée, notamment au traitement prévu pour `EST_COMMANDE_PAR`. Une relation logique peut rester probable.
6. Les chemins UML autorisent les deux sens de parcours. Le sens des relations reste celui de la base. La recherche est bornée et ne garantit pas le meilleur chemin métier.
7. Le sous-graphe UML courant n’est pas une exploration arbitraire de profondeur demandée par l’utilisateur. Les demandes composées ou nouvelles doivent être évaluées.
8. `MERGE` ne remplace pas une synchronisation des sources : les anciens chunks ou liens peuvent nécessiter une stratégie explicite de mise à jour.
9. Le diagnostic de normalisation n’est pas une fusion ; l’application des fusions est une opération destructive. Sa sauvegarde locale n’est pas une sauvegarde complète de Neo4j.
10. Les nombres de fiches, concepts et tests des anciens documents ne sont pas présentés comme des mesures actuelles.

## Intégrité des documents conservés

Empreintes SHA-256 de référence avant révision :

```text
GUIDE_UTILISATION.md
B399E529BC618D1EBD430553D80A64D7B3A92D9BE45779B88DF0EDBC3CA83E0E

Rapport_Stage_GraphRAG.pdf
F3579DCE1236D89F428CF3C57CEF1459A3CAC3A15AEC12C72058F255ED6C9BA6
```

La révision documentaire explique les limites connues ; elle ne prétend pas les avoir corrigées dans le programme. Les vérifications de la base active, de disponibilité des modèles et de pertinence des réponses restent des opérations distinctes.

## Vérifications de livraison

- Empreintes SHA-256 des deux documents protégés identiques aux références ci-dessus.
- 50 liens locaux contrôlés dans les 14 documents Markdown révisés ou créés, README racine et notice d’archives compris : aucune cible manquante.
- Blocs de code Markdown contrôlés : aucune clôture manquante.
- Options des principales commandes d’extraction, recontrôle et sélection confrontées aux arguments déclarés dans les scripts ; commandes non exécutées.
