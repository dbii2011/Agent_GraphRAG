# Premier import métier : poste d'aiguillage

La sélection `DataMetier/pilote_poste_selection.json` contient 7 concepts et 6 relations.
Elle résulte d'une revue documentaire assistée de `Docs/Post.txt`, autorisée pour ce pilote,
et non d'une certification par un expert ferroviaire. Le reste du corpus demeure à revoir.

Les concepts métier restent distincts des classes UML, dans la même base Neo4j.
Les correspondances exactes retenues sont Poste, Signal, AppareilDeVoie, Ligne et Pk.
Les types PAI et PRCI n'ont pas de correspondance UML ajoutée arbitrairement.

Relations retenues : commande des signaux et appareils de voie par le poste ;
localisation ligne/PK conditionnelle pour les postes de voie principale ;
PAI et PRCI comme deux exemples non exhaustifs de types de poste.
Le rattachement facultatif à un SAF et les impacts de modification ne sont pas importés.

## État vérifié après import

Dans la base `neo4j` du projet : 7 concepts métier, 6 relations métier,
5 liens `REPRESENTE_PAR`, 7 liens `DOCUMENTE_PAR` et 9 liens `ETAYE_PAR`
vers 3 chunks distincts de `Post.txt` (passages 1, 3 et 6).
Les 998 classes UML sont conservées. Une seconde importation identique n'a créé aucun doublon.
Trois questions de retrieval ont retrouvé les relations attendues et leurs citations,
sans appel au modèle d'embedding pour les questions structurelles.

## Exécution

```powershell
python importer_pilote_metier.py
python importer_pilote_metier.py --importer
```

La première commande est en lecture seule. Les contrôles précèdent les écritures :
classes/documents uniques, citations présentes dans les lignes du fichier et dans les chunks Neo4j,
absence de collision avec des concepts d'un autre domaine.
La seconde ajoute les données via le builder ; les MERGE rendent une reprise sans changement idempotente.
Ce script ne supprime aucune donnée. Le builder utilise plusieurs transactions : en cas d'interruption,
rejouer le précontrôle puis la même importation pour compléter le pilote.

## Provenance et retrieval

- `REPRESENTE_PAR` : concept métier vers classe UML ;
- `DOCUMENTE_PAR` : concept vers fiche source ;
- `ETAYE_PAR` : concept vers chunk qui étaye une relation à laquelle il participe ;
- `RELATION_METIER` : prédicat, citation, document, lignes, `chunk_ids`, condition et méthode de validation.

`ETAYE_PAR` n'affirme pas que chaque chunk décrit intégralement le concept.
La preuve précise de chaque relation est portée par ses propres `chunk_ids`.
Le retriever ne retient que les nœuds et relations `valide=true`, retrouve les chunks de preuve
et les insère dans le contexte, même pour une question structurelle. Les conditions sont transmises au LLM.

Après redémarrage de l'application si elle ne recharge pas automatiquement le code, tester :

- « Quels équipements sont commandés par un poste d'aiguillage ? Cite la fiche. »
- « PAI et PRCI sont-ils des types de poste d'aiguillage ? »
- « Comment localise-t-on un poste de voie principale ? »

Pour voir le pilote dans Neo4j Browser :

```cypher
MATCH (c:ConceptMetier {domaine: "Pilote poste d'aiguillage"})
OPTIONAL MATCH (c)-[r]->(n)
RETURN c, r, n;
```
