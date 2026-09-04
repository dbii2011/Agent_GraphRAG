# Rapport Overleaf — GraphRAG Arianes

Ce dossier constitue un projet Overleaf complet. Le fichier principal est `main.tex`.

## Importer dans Overleaf

1. Utiliser l'archive `rapport_overleaf.zip` fournie à la racine du dépôt.
2. Dans Overleaf, créer un projet avec **New Project → Upload Project**.
3. Sélectionner l'archive ZIP.
4. Vérifier dans **Menu → Main document** que `main.tex` est sélectionné.
5. Utiliser le compilateur pdfLaTeX. Aucune option `shell-escape` n'est nécessaire.

## Personnalisation obligatoire

Modifier uniquement le début de `config.tex` :

```tex
\newcommand{\Auteur}{Prénom NOM}
\newcommand{\Formation}{...}
\newcommand{\Etablissement}{...}
\newcommand{\EncadrantEntreprise}{...}
\newcommand{\EncadrantAcademique}{...}
\newcommand{\PeriodeStage}{...}
```

Ajouter ensuite les captures dans `figures/` en suivant `figures/README.md`. Une capture absente est remplacée par un cadre : le rapport reste compilable.

## Structure

- `main.tex` : point d'entrée ;
- `config.tex` : identité, mise en page et commandes ;
- `frontmatter/` : couverture et résumés ;
- `chapters/` : corps du rapport ;
- `appendices/` : inventaire et commandes ;
- `bibliographie.bib` : références ;
- `figures/` : captures d'écran.

Le rapport reflète l'état du projet au 1er septembre 2026 : graphe technique et documentaire complet dans Neo4j, extraction métier exécutée sur 29 fiches, et seul pilote métier `Post.txt` importé après revue.
