# Corrections de l'audit — premier lot

La recherche de chemins UML dans les deux sens est conservée. Aucun import,
recalcul d'embedding, appel LLM ou changement de la base Neo4j n'a été lancé.

## Changements réalisés

- UML : protection des descriptions complètes face aux références externes ;
  identité des relations incluant le rôle ; conservation de `0..*` ; contrôle
  des types de relation autorisés ; noms de fichiers portables Windows/POSIX.
- XMI : index des noms construit avant résolution des attributs ; type inconnu
  laissé non renseigné au lieu d'inventer `P-String` ; rôle corrigé lorsque
  l'extrémité composite/agrégée est inversée ; sortie dans `project_data/uml`.
- Retrieval : filtre documentaire appliqué après OPTIONAL MATCH ; scores absents
  pris en charge ; déduplication des contributions par chunk ; erreurs plein
  texte journalisées ; meilleure reconnaissance des questions structurelles
  composées et des nouvelles questions explicitant une classe.
- Validation V4 : absence de correction ne signifie plus direction confirmée.
  Les relations incertaines restent PROBABLE, elles ne sont pas éliminées.
- Import métier : `actif` est séparé de la validation documentaire ; `valide`
  correspond au statut VALIDE. Le retrieval accepte aussi les relations PROBABLE
  actives et reste compatible avec les anciens enregistrements.
- Extraction : reprise contrôlée par empreinte de source, catalogue, modèle,
  taille de chunk et code d'extraction/validation ; agrégation limitée aux
  documents sélectionnés et réussis, sans anciens checkpoints périmés.
- API : protection de `/schema`, chemin absolu de l'interface, gestion SQLite
  conditionnelle, erreur interne non exposée, refus d'une seconde demande
  concurrente sur une conversation (déploiement mono-processus seulement).
- Dépendances déclarées ; pytest limité au dossier tests, hors archives legacy.
- Cinq tests de non-régression ajoutés. Un ancien test a été corrigé : citation
  exacte ne signifie pas à elle seule validation du sens d'un triplet.

## Limites et travail restant

Ce lot ne clôt pas tous les points de l'audit :

- Les relations et descriptions déjà importées ne sont pas réparées.
- L'identité des relations par rôle ne remplace pas encore une identité XMI
  complète ; ne pas réimporter aveuglément dans la base existante (risque de
  coexistence avec des relations anciennes sans rôle).
- La synchronisation transactionnelle des documents et triplets obsolètes,
  ainsi que la sauvegarde/restauration du script de fusion, restent à traiter.
- L'utilisation effective de l'index vectoriel, les sous-graphes UML à profondeur
  demandée et l'alignement complet texte/schéma restent à vérifier/corriger.
- La validation automatique V4 reste prudente et n'est pas une expertise métier.
  Les anciens JSON V3 ne sont pas automatiquement reclassés.
- Les dépendances ne sont pas encore verrouillées par version ; un déploiement
  multi-workers et la sécurité de production nécessitent un travail séparé.

Avant une migration : sauvegarde restaurable, base de test, comparaison des
comptages et des relations, puis approbation de la modification de la base active.
