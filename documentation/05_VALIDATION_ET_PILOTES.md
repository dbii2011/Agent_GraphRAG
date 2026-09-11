# Phase 5 — Contrôler les propositions et produire les pilotes

[Sommaire](README.md) · [Phase suivante](06_IMPORT_ET_PROVENANCE.md)

## Entrées et résultats

Entrées : checkpoints `*.metier.json` et fiches sources. Traitements : `validation_metier.py`, `recontrole_metier.py`, `selection_prudente.py`, `generer_pilotes.py`. Sorties : propositions recontrôlées, rapport de contrôle, pilote par fiche et sélection globale. Ces traitements locaux ne nécessitent pas de LLM et n'écrivent pas dans Neo4j.

## Ce que contrôle réellement la V4

Le contrôleur déclare `VERSION_VALIDATION = 4`. `controler_relation` vérifie les extrémités, les auto-relations, le prédicat autorisé, la présence de la citation et certaines incompatibilités de catégories. Des règles particulières à des passages déjà examinés subsistent : il ne s'agit pas d'une compréhension sémantique générale.

La voix passive est normalisée pour certains triplets COMMANDE lorsque les deux concepts sont repérés de part et d'autre de « commandé par ». Cela évite d'inverser systématiquement toutes les relations d'une phrase passive.

Les statuts détaillés sont :

- `REJETE` : erreur bloquante, conservée avec ses motifs.
- `PROBABLE` : proposition conservée avec une incertitude, sans certification.
- `VALIDE` : contrôles documentaires satisfaits selon les critères du code, distinct de `validation_experte`.

La direction n'est plus réputée confirmée par simple absence de correction. **Dans l'implémentation V4 actuelle, la confirmation automatique de direction est limitée au motif EST_COMMANDE_PAR avec extrémités reconnues dans la citation.** Les autres prédicats restent généralement PROBABLE après ce contrôle, même s'ils paraissent logiques. Ils restent sélectionnables ; ils ne sont pas supprimés pour cette seule raison.

Le score additionne des critères pondérés ; `score_confiance` n'est pas une probabilité calibrée. Une citation retrouvée ne garantit ni l'interprétation correcte, ni l'universalité de la relation. Les modalités et négations ne sont détectées que par un ensemble limité d'expressions.

## Recontrôle sur les véritables lignes

`lire_passage` résout le document dans le corpus autorisé et contrôle la plage de lignes. `recontroler` confronte chaque citation au passage réel. `executer` traite les fichiers, consolide, recontrôle le résultat global et produit les empreintes des checkpoints sources.

Après la phase 4 et la mise en cohérence du package :

```powershell
python -m arianes.pipelines.recontrole_metier --input-dir project_data/metier/extraction_20260911/propositions --docs project_data/procedures --output-dir project_data/metier/controle_20260911
```

Le dossier de sortie doit être nouveau : le script refuse un dossier existant. Il produit `propositions/`, `proposition_globale.json` et `rapport_controle.json`. Les originaux d'extraction restent conservés.

Le défaut du CLI pointe encore vers `corrections_v2` : utiliser les chemins explicites de cette procédure évite de mélanger les générations.

## Sélection globale et pilotes par fiche

`selectionner` conserve les relations VALIDE ou PROBABLE sans motifs bloquants, puis les concepts participant aux relations retenues. Les statuts des concepts déjà admis sont conservés ; les autres deviennent PROBABLE. La sélection indique `validation_experte=false`.

```powershell
python -m arianes.pipelines.generer_pilotes --input-dir project_data/metier/controle_20260911/propositions --output-dir project_data/metier/pilotes_20260911
python -m arianes.pipelines.selection_prudente --input project_data/metier/controle_20260911/proposition_globale.json --output project_data/metier/pilote_global_20260911.json
```

La génération individuelle crée un `<fiche>.pilote.json` par entrée et `rapport_pilotes.json`. Elle traite les fiches présentes dans le répertoire, sans nombre de documents fixé dans le code. Les sommes de concepts par pilote ne sont pas le nombre de concepts uniques de Neo4j.

Les valeurs par défaut de ces deux scripts pointent encore vers `corrections_v3`. Certaines chaînes de métadonnées mentionnent encore V3 alors que le contrôleur est V4. Conserver le rapport de contrôle, les empreintes et les commandes de campagne comme provenance ; ne pas déduire la version du seul nom de fichier ou de cette étiquette historique.

## Validation manuelle historique

`extraction_metier valider ... --confirmer-relecture` marque tout le contenu du fichier VALIDE et le réécrit. Ce n'est pas une interface de revue relation par relation, ni une preuve automatique d'expertise. Cette commande n'est pas nécessaire pour conserver les relations PROBABLE via le builder générique. Ne pas l'utiliser simplement pour faire disparaître un avertissement.

Avant import, examiner les concepts homonymes, les directions, les formulations conditionnelles, les preuves et les rejets. Un pilote est un paquet documentaire sélectionné ; sa présence sur disque n'indique pas qu'il a été importé.
