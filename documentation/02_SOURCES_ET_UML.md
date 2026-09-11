# Phase 2 — Préparer les sources et convertir l'UML

[Sommaire](README.md) · [Phase suivante](03_DOCUMENTS_ET_INDEXATION.md)

## Entrées, scripts et sorties

- Sources structurelles : `project_data/xmi/*.txt`, contenant du XML/XMI.
- Convertisseur : `arianes/pipelines/xmi_to_json.py`.
- Sorties : `project_data/uml/<nom_export>.json`.
- Consommateurs : `graph/uml_builder.py` et le catalogue de l'extraction métier.

Après la mise en cohérence du package décrite en phase 1 :

```powershell
python -m arianes.pipelines.xmi_to_json
```

Cette commande traite les exports et écrit les JSON. Elle ne contacte ni Neo4j ni le LLM ; une sortie existante de même nom peut être remplacée.

## Fonctionnement du convertisseur

`parse_xmi` charge l'arbre XML puis construit d'abord une correspondance identifiant → nom, y compris pour les éléments déclarés après leur utilisation. Il lit les références externes, classes, attributs, énumérations, généralisations et associations.

`get_documentation` récupère des descriptions ; `get_multiplicity` lit les bornes ; `est_une_enumeration` identifie certaines énumérations représentées comme classes. Les généralisations donnent des couples enfant/parent. Les associations deviennent `ASSOCIE_A`, `COMPOSE_DE` ou `AGREGE` selon l'agrégation indiquée aux extrémités.

`deduplique` regroupe les classes de même nom dans l'export. Une description complète peut remplacer une description de référence externe. `read_xmi_file` écrit les collections `classes`, `enums`, `generalizations`, `relations` dans le répertoire centralisé.

Le JSON est un intermédiaire inspectable. Les identifiants XMI aident à résoudre les références pendant la conversion, mais ils ne sont pas systématiquement conservés comme identité de chaque élément dans le graphe final. Il ne faut donc pas présenter cette conversion comme une conservation intégrale du XMI.

## Import UML

`importer_modele_depuis_json` transmet les éléments à `ArianeGraphBuilder` :

- `merge_classe` : classe identifiée par son nom, description et caractère abstrait.
- `merge_attribut` : attribut identifié par `classe.nom`, puis lien `A_ATTRIBUT` et type via `EST_DE_TYPE`.
- `merge_enum` : énumération et valeurs liées par `A_VALEUR`.
- `add_relation` : lien UML avec rôle et cardinalité ; seuls quatre types structurels sont acceptés.

Le rôle fait désormais partie de l'identité des relations créées par `MERGE`. Deux rôles différents entre les mêmes classes peuvent subsister. La cardinalité `0..*` est conservée.

## Contrôles à réaliser

Comparer un échantillon XMI/JSON : noms, classe abstraite, parent, rôle à chaque extrémité, cardinalité, type des attributs. Un type non résolu reste non renseigné plutôt que d'être arbitrairement remplacé par `P-String`.

Les limites restantes comprennent la gestion des homonymes, les conflits de types issus de plusieurs fichiers, l'identification des enums par le builder et la navigabilité des associations. Deux relations ayant même type, mêmes extrémités et même rôle ne sont toujours pas distinguées par leur identifiant XMI.

Ne pas confondre une classe `Ligne` avec une ligne ferroviaire concrète : le graphe UML décrit les types du modèle, pas les instances opérationnelles.

`MERGE` recherche un élément selon une clé. Il ne résout pas les contradictions des sources et ne retire pas automatiquement les données devenues obsolètes. Les anciens liens importés avant l'ajout du rôle à la clé nécessitent une stratégie de migration.
