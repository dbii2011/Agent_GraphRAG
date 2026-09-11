# Phase 4 — Extraire les concepts et les relations métier

[Sommaire](README.md) · [Phase suivante](05_VALIDATION_ET_PILOTES.md)

## Ce que produit cette phase

Entrées : fiches texte et JSON UML. Scripts : `pipelines/extraction_metier.py` et `pipelines/extraction_globale.py`. Sorties : propositions JSON par fiche et proposition consolidée. Cette phase utilise Mistral mais n'importe rien dans Neo4j.

Les relations métier proviennent des phrases de la fiche, proposées sous forme de triplets par le LLM. Elles ne sont pas simplement recopiées depuis les associations UML. Le catalogue UML aide à reconnaître les classes connues et à proposer des correspondances ; un concept métier peut exister sans classe UML correspondante.

## Déroulement d'une fiche

1. `charger_catalogue` lit les JSON de `project_data/uml`, pas Neo4j. Il rassemble noms, descriptions, attributs et fichiers d'origine.
2. `decouper_document` regroupe des lignes en morceaux d'environ 6 000 caractères, avec numéros de début et fin. Une très longue ligne peut dépasser cette taille ; il ne s'agit pas du découpage documentaire 800/100.
3. `classes_candidates` compare lexicalement le passage aux noms normalisés du catalogue. Il retient jusqu'à 30 candidats selon les correspondances exactes et le recouvrement de mots. Les descriptions sont fournies au LLM mais ne sont pas directement le signal de ce score.
4. `prompt_extraction` demande des concepts, alias, descriptions, catégories, correspondances UML et relations. Une relation doit mentionner source, prédicat, cible, citation exacte et éventuelles conditions ou exceptions.
5. `extraire_json_message` récupère le JSON, même entouré de balises Markdown. Une sortie syntaxiquement lisible n'est pas encore une extraction correcte.
6. `valider_extraction` vérifie identifiants, classes connues, prédicats et preuves dans le passage ; les rejets restent traçables.
7. `consolider` rapproche les concepts de même nom normalisé et conserve les preuves distinctes. Une auto-relation apparue après fusion est rejetée. La consolidation peut reclasser en PROBABLE, faute de passage source au moment de son contrôle : le recontrôle de la phase 5 est nécessaire.

`extraire_document` orchestre ces appels pour la fiche. Le checkpoint est écrit après une fiche complète, pas après chaque morceau : une interruption au milieu d'une fiche peut obliger à la reprendre.

## Commandes

Prérequis commun : package `arianes` importable selon la phase 1 et clé Mistral configurée.

Inventaire sans appel LLM ni écriture Neo4j :

```powershell
python -m arianes.pipelines.extraction_globale --inventaire
```

Exemple d'une fiche, avec une sortie explicite :

```powershell
python -m arianes.pipelines.extraction_metier extraire project_data/procedures/Post.txt --output project_data/metier/extraction_20260911/poste.json
```

Campagne complète, dans un répertoire de travail dédié :

```powershell
python -m arianes.pipelines.extraction_globale --output-dir project_data/metier/extraction_20260911/propositions --output project_data/metier/extraction_20260911/proposition_globale.json
```

Pour un essai, ajouter `--limite 2` avec des sorties séparées de la campagne complète. `--force` demande le recalcul. Ces chemins datés sont des exemples ; choisir un identifiant de campagne qui ne confonde pas les résultats précédents.

## Reprise et contrôle des sorties

La reprise compare une empreinte comprenant le document, le catalogue, le modèle, la taille des morceaux et les fichiers de code d'extraction/validation. Un ancien checkpoint dépourvu de cette empreinte sera retraité. Seuls les documents sélectionnés et réussis sont consolidés ; les échecs sont listés dans `erreurs_documents`.

Vérifier `document_source`, les extrémités des relations, les citations, `relations_rejetees` et les documents en échec. Le message console « A_REVOIR » désigne la proposition de travail ; les statuts détaillés des relations doivent être lus dans le JSON.

Les rapprochements lexicaux n'épuisent pas les synonymes. Un mauvais texte source ou un catalogue incomplet produit des candidats insuffisants. Les fiches doivent conserver titres, ordre des étapes, tableaux intelligibles, conditions et exceptions après conversion en texte.
