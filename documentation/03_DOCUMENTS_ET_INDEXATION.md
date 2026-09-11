# Phase 3 — Découper, vectoriser et retrouver les documents

[Sommaire](README.md) · [Phase suivante](04_EXTRACTION_METIER.md)

## Entrées et effets

Le script `graph/uml_builder.py` traite à la fois les JSON UML et les fiches `project_data/procedures/*.txt`. Il écrit dans Neo4j et appelle l'API Mistral pour les embeddings.

Après préparation de l'environnement, sur une base de travail choisie pour l'import :

```powershell
python -m arianes.graph.uml_builder
```

Ce n'est pas une commande de lancement du chatbot. Elle n'a pas été exécutée pour rédiger ces guides.

## Du texte au stockage

`importer_document` crée un `Document` avec identifiant, titre et chemin source. Le nom de fichier sert aussi à rechercher une classe correspondante pour le lien `DECRIT` ; cette correspondance est une heuristique et peut échouer pour un nom abrégé.

`RecursiveCharacterTextSplitter` découpe le texte avec une taille cible de 800 caractères et un recouvrement de 100 caractères. Le recouvrement conserve une partie du contexte entre passages ; il ne garantit pas qu'une procédure entière tienne dans un passage.

`embed_documents` calcule les vecteurs avec `mistral-embed`. `merge_chunk` enregistre `texte`, `position`, `embedding` dans un nœud `Chunk`, puis crée `Chunk → APPARTIENT_A → Document`. Les identifiants des chunks reposent sur le document et la position.

Le nœud Document n'est pas une copie garantie de tout le texte : le texte consulté est stocké dans les chunks, et le fichier source reste dans le corpus.

## Embedding, index vectoriel et plein texte

Un embedding est une suite de nombres représentant des caractéristiques du texte. La proximité des vecteurs aide à retrouver des formulations voisines ; ce n'est pas une preuve que le passage répond à la question.

Le builder crée `chunk_embeddings`, index vectoriel de dimension 1024 avec similarité cosinus, et `chunk_fulltext`, index plein texte sur `Chunk.texte`.

**Distinction importante dans le code actuel :** `_chercher_chunks` calcule `vector.similarity.cosine` sur les chunks candidats. Il n'appelle pas la recherche par index vectoriel `db.index.vector.queryNodes`. L'index vectoriel existe comme préparation, mais cette branche effectue un calcul direct. Le plein texte utilise bien `db.index.fulltext.queryNodes`.

Le plein texte retrouve des mots et sigles selon l'analyseur de l'index ; ce n'est pas uniquement une comparaison exacte de chaînes.

## Fusion réciproque des rangs

Les classements sémantique et lexical n'ont pas des scores directement comparables. Le retriever additionne des contributions fondées sur la position : `1 / (60 + rang)` pour chaque liste où le chunk apparaît.

Exemple illustratif : un passage classé 1er en sémantique et 3e en lexical reçoit `1/61 + 1/63`, environ 0,0323. Un passage seulement 1er dans une liste reçoit environ 0,0164. La méthode favorise un passage bien placé dans plusieurs recherches ; elle ne calcule pas une probabilité de vérité.

Des filtres précèdent la fusion, notamment le seuil sémantique 0,65. Le filtrage par classes est appliqué après le `OPTIONAL MATCH`, afin d'exclure les documents non rattachés au périmètre demandé. Si les embeddings sont indisponibles, une recherche lexicale seule peut être tentée ; elle n'est pas équivalente en qualité.

## Vérifier la base en lecture seule

Dans Neo4j Browser, exécuter séparément :

```cypher
MATCH (c:Chunk)
RETURN count(c) AS chunks,
       count(c.embedding) AS chunks_avec_embedding;
```

```cypher
MATCH (c:Chunk)
RETURN size(c.embedding) AS dimension, count(*) AS nombre;
```

```cypher
SHOW INDEXES;
```

Un index ONLINE ne prouve pas que le retriever l'utilise. Un vecteur présent de dimension correcte ne garantit pas sa pertinence.

## Limites de mise à jour

Le script vérifie que le nombre de vecteurs reçus correspond au nombre de passages. Toutefois, une réindexation plus courte ne retire pas nécessairement les anciens chunks. Des écritures séparées peuvent laisser un import partiel en cas d'erreur. Comparer les sources, les positions et les comptages avant de déclarer la mise à jour terminée.
