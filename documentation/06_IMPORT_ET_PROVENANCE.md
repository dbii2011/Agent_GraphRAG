# Phase 6 — Importer la couche métier et vérifier sa provenance

[Sommaire](README.md) · [Phase suivante](07_RETRIEVAL_ET_APPLICATION.md)

## Trois traitements différents

`graph/metier_builder.py` est l'importeur générique. Il accepte les statuts VALIDE et PROBABLE après ses contrôles d'admissibilité. `pipelines/import_pilote.py` ajoute des vérifications pour le fichier historique `pilote_poste_selection.json` ; son interface n'accepte pas un chemin de pilote quelconque. Enfin, la sous-commande `extraction_metier importer` filtre uniquement VALIDE : elle n'est pas équivalente au builder générique.

Entrée normale de la chaîne graduée : `project_data/metier/pilote_global_20260911.json`. Sortie : nœuds et relations Neo4j. Une connexion Neo4j est nécessaire ; l'import ne demande pas de génération LLM.

## Import générique

Après sélection, revue et préparation d'une base de test :

```powershell
python -m arianes.graph.metier_builder project_data/metier/pilote_global_20260911.json
```

Cette commande écrit en base. Elle ne comporte pas d'option de simulation et ne supprime pas automatiquement les anciennes relations contradictoires. Les imports existants doivent être comparés avant toute migration de la base utilisée par le chatbot.

`charger_definition` contrôle les identifiants et références. `verifier_import` refuse notamment les rejets, extrémités absentes, auto-relations et preuves mal structurées. Il n'effectue pas à lui seul la vérification complète de chaque citation dans chaque fichier et chaque chunk : le recontrôle documentaire est une étape distincte.

`importer` recherche les concepts existants par nom normalisé, crée les concepts, puis les correspondances et relations avec leurs preuves. Cette fusion par nom peut confondre des homonymes ; les réimports peuvent remplacer des descriptions ou alias. Les écritures sont réalisées en plusieurs transactions, donc une interruption peut laisser un résultat partiel.

## Relations de traçabilité

- `ConceptMetier → REPRESENTE_PAR → Classe` : correspondance avec une classe UML ; pas un héritage.
- `ConceptMetier → DOCUMENTE_PAR → Document` : fiche associée au concept.
- `ConceptMetier → ETAYE_PAR → Chunk` : passage étayant une relation impliquant ce concept.
- `ConceptMetier → RELATION_METIER → ConceptMetier` : assertion avec son prédicat dans `type`, citation, document, lignes, `chunk_ids`, conditions, exceptions et statut.

`ETAYE_PAR` ne signifie pas que le passage définit entièrement le concept. La provenance précise d'une relation réside aussi dans les propriétés de cette relation.

Si une classe ou un document cible manque, un lien de correspondance peut ne pas être créé. Si aucune citation n'est retrouvée dans les chunks, le builder peut importer une relation avec une preuve structurée mais sans `chunk_ids`. Il faut donc contrôler la couverture des preuves après import.

## Actif et validé

Le builder actuel écrit `actif=true` pour les éléments admis. Il écrit `valide=true` et `validation_documentaire=true` seulement lorsque le statut vaut VALIDE. Une relation PROBABLE peut donc être active et consultable.

Le retriever utilise `actif`, avec compatibilité sur l'ancien champ `valide` lorsque `actif` est absent. Cette compatibilité ne reclassifie pas les anciens JSON ni les anciennes relations V3. Une migration doit traiter leur statut explicitement.

## Pilote Post historique

Précontrôle avec lecture de Neo4j, sans écriture :

```powershell
python -m arianes.pipelines.import_pilote
```

L'option `--importer` déclenche les écritures après contrôle. Le script vérifie l'unicité des correspondances, les citations dans les lignes et les chunks, ainsi que certains conflits de concepts existants. Il ne représente pas le pipeline de tous les pilotes documentaires.

## Vérifications de lecture

Exécuter dans Neo4j Browser :

```cypher
MATCH (c:ConceptMetier)
RETURN c.statut AS statut, c.actif AS actif, c.valide AS valide, count(*) AS nombre;
```

```cypher
MATCH ()-[r:RELATION_METIER]->()
RETURN r.source_document AS document, r.statut AS statut,
       count(*) AS relations,
       sum(CASE WHEN size(coalesce(r.chunk_ids, [])) = 0 THEN 1 ELSE 0 END) AS sans_chunk
ORDER BY document, statut;
```

Pour examiner les preuves d'une relation :

```cypher
MATCH (a:ConceptMetier)-[r:RELATION_METIER]->(b:ConceptMetier)
RETURN a.nom, r.type, b.nom, r.preuve, r.source_document,
       r.condition, r.exception, r.statut LIMIT 50;
```

Ces contrôles n'ont pas été exécutés pendant la révision documentaire : aucun chiffre actuel de la base n'est affirmé.

## Sauvegardes et normalisation

`pipelines/normalisation_metier.py` affiche les groupes de doublons sans `--apply`. L'application des fusions sauvegarde un extrait puis redirige des relations et supprime les doublons. L'export de ce script n'a pas été démontré comme une sauvegarde complète restaurable de la base ; ne pas l'utiliser comme seule protection avant fusion.

Une sauvegarde de base, un essai de restauration et une comparaison avant/après restent nécessaires pour une migration fiable. `MERGE` rend certaines opérations répétables à entrée identique ; il n'assure ni synchronisation des suppressions, ni résolution des contradictions.
