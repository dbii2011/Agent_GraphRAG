# Correction du graphe métier — 31 août 2026

## Résultat et périmètre

Les 29 checkpoints ont été recontrôlés **hors ligne**, sans appel à Mistral et sans écriture dans Neo4j.
Les originaux dans `DataMetier/propositions/` et `DataMetier/proposition_globale.json` sont conservés.
La copie corrigée est dans `DataMetier/corrections_v2/` :

- `propositions/` : un JSON corrigé par fiche ;
- `proposition_globale.json` : version consolidée ;
- `rapport_controle.json` : compteurs, motifs et empreintes SHA-256 des originaux.

Au premier passage : 345 concepts, 341 relations conservées à revoir, 24 relations rejetées,
36 relations conservées ayant reçu une correction. Ces chiffres ne sont **pas** un taux de précision métier.
Les 144 messages historiques `erreurs_validation` proviennent de l'extraction initiale, avant ces 365 relations.

## Modifications

`validation_metier.py` centralise les catégories, les prédicats et leurs contrôles.

- Les concepts peuvent être typés : équipement, objet ferroviaire, acteur, document, procédure,
  localisation, date, valeur, caractéristique, système ou type d'objet.
- Les anciens concepts non reconnaissables restent `INCONNU` : leur catégorie n'est pas devinée.
- Une date ou un document ne peut pas être un organe de commande ou un lieu physique.
- La voix passive ne transforme plus toutes les relations d'une citation en `EST_COMMANDE_PAR`.
  Seules les relations `COMMANDE` dont les deux extrémités sont repérées autour du verbe sont normalisées.
- Les corrections taxonomiques automatiques sont **limitées à des cas relus dans le corpus**,
  avec vérification du document et du passage attendu : RK/PK, typologies de nœuds et de postes.
- Les champs du quai deviennent `A_POUR_CARACTERISTIQUE`, les dates de fermeture deviennent
  `DEBUTE_A` / `SE_TERMINE_A`, le plan du quai devient une source `DECRIT_PAR`.
- Les relations manifestement incompatibles avec les passages audités sont conservées dans
  `relations_rejetees`, avec leur preuve et le motif ; aucun remplacement incertain n'est inventé.
- Les auto-relations sont contrôlées **après** la fusion des concepts. Deux identifiants différents
  peuvent désigner le même nom et devenir une auto-relation pendant la consolidation.
- Les collisions d'identifiants tronqués sont bloquées, pas fusionnées silencieusement.
- Une citation doit être retrouvée dans la plage de lignes de la fiche indiquée lors du recontrôle.
  Les chemins sortant du dossier `Docs/` sont refusés.
- Les preuves distinctes d'un même triplet ne s'écrasent plus à l'import Neo4j.

## Statuts : pas de validation automatique

- `A_REVOIR` : proposition conservée, même après correction technique ;
- `REJETE` : proposition isolée avec `motifs_rejet` ;
- `VALIDE` : réservé à une validation humaine explicite.

Une absence d'avertissement lexical ne démontre ni le sens du prédicat ni sa direction.
La négation et les conditions sont signalées, mais ne sont pas transformées automatiquement en nouveaux faits.
Le mode tolérant reste donc disponible pour les cas ambigus. Aucun statut `VALIDE_AUTO` n'a été ajouté.

## Rejouer le recontrôle

```powershell
python recontroler_graphe_metier.py --output-dir DataMetier/corrections_v2_nouvelle_revue
```

Le script refuse un dossier de sortie déjà existant pour éviter tout écrasement.
Pour une nouvelle extraction Mistral, utiliser des chemins séparés :

```powershell
python extraire_tout_graphe_metier.py --output-dir DataMetier/extraction_v2/propositions --output DataMetier/extraction_v2/proposition_globale.json
```

Puis recontrôler les nouveaux checkpoints avec `--input-dir DataMetier/extraction_v2/propositions`.
L'extraction complète n'a pas été relancée pendant cette correction.

## Avant import

Relire et sélectionner les relations dans une **copie** du JSON corrigé. Ne pas valider tout le lot sans examen.
La commande de validation requiert désormais `--confirmer-relecture` :

```powershell
python pipeline_graphe_metier.py valider DataMetier/selection_relue.json --confirmer-relecture
python pipeline_graphe_metier.py importer DataMetier/selection_relue.json
```

Le builder direct vérifie aussi les statuts **avant sa première écriture**. L'ancien exemple
`DataMetier/poste_aiguillage.json`, sans statuts explicites, n'est plus importable directement sans revue.
Les relations rejetées ou auto-référentes restent bloquées, même si elles sont marquées `VALIDE` manuellement.

## Limites

Ces règles corrigent les problèmes identifiés ; elles ne constituent pas un analyseur sémantique complet.
Certaines relations `EST_UN`, `GERE_PAR`, `COMPOSE_DE` et les relations conditionnelles restent ambiguës.
La vérification experte demeure nécessaire avant d'utiliser ces propositions comme faits du chatbot.
