# Pipeline du graphe métier

> Les pipelines sont maintenant exécutés avec
> `python -m arianes.pipelines.<module>`. Les fiches sont dans
> `project_data/procedures` et les données métier dans `project_data/metier`.

Le pipeline transforme les JSON du métamodèle et les fiches de référence en une
couche `ConceptMetier` contrôlée dans Neo4j. Mistral propose les concepts et les
relations, mais aucune proposition n'est importée sans preuve exacte et validation.

## 1. Extraire une proposition

```powershell
python pipeline_graphe_metier.py extraire Docs/Post.txt `
  --output DataMetier/proposition_poste.json
```

Plusieurs fiches peuvent être traitées ensemble :

```powershell
python pipeline_graphe_metier.py extraire `
  Docs/Post.txt Docs/Itineraire.txt Docs/ZoneDeDetection.txt `
  --output DataMetier/proposition_signalisation.json
```

La sortie porte le statut `A_REVOIR`. Une relation est conservée seulement si :

- son type appartient à la liste autorisée ;
- ses deux concepts existent dans la proposition ;
- sa citation est réellement présente dans le passage traité ;
- les classes Arianes indiquées existent dans les JSON de `Data/`.

## 2. Relire et valider

Relire le fichier produit, notamment `nom`, `aliases`, `classes_arianes`,
`relations` et `preuve`. Après validation métier :

```powershell
python pipeline_graphe_metier.py valider DataMetier/proposition_poste.json
```

## 3. Importer dans Neo4j

Neo4j doit être démarré et les variables du fichier `.env` doivent être valides.

```powershell
python pipeline_graphe_metier.py importer DataMetier/proposition_poste.json
```

L'import est idempotent. Il crée ou met à jour :

- `(:ConceptMetier)` ;
- `(:ConceptMetier)-[:REPRESENTE_PAR]->(:Classe)` ;
- `(:ConceptMetier)-[:DOCUMENTE_PAR]->(:Document)` ;
- `(:ConceptMetier)-[:RELATION_METIER]->(:ConceptMetier)`.

Le retriever de l'agent explore ensuite les concepts détectés, leur voisinage
direct, les classes Arianes correspondantes et les chunks documentaires associés.

## Extraire toutes les fiches

Afficher l'inventaire sans appeler Mistral :

```powershell
python extraire_tout_graphe_metier.py --inventaire
```

Faire un essai sur deux fiches :

```powershelllai
python extraire_tout_graphe_metier.py --limite 2
```

Traiter toutes les fiches de `Docs/` :

```powershell
python extraire_tout_graphe_metier.py
```

Chaque résultat intermédiaire est sauvegardé dans
`DataMetier/propositions/<fiche>.metier.json`. Une interruption ne fait donc pas
perdre les fiches déjà terminées : la même commande reprend automatiquement.
Le fichier consolidé est `DataMetier/proposition_globale.json` et reste
`A_REVOIR`. L'option `--force` permet de recalculer les fiches existantes.
