import json
import os
from neo4j import GraphDatabase
from datetime import datetime
import glob
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = "data"
DOCS_DIR = "docs"

URI = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")

class ArianeGraphBuilder:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def _run(self, query, **params):
        with self.driver.session() as session:
            session.run(query, **params)

    # ------------------------------------------------------------------
    # Contraintes
    # ------------------------------------------------------------------
    def create_constraints(self):
        for stmt in [
        "CREATE CONSTRAINT classe_nom  IF NOT EXISTS FOR (c:Classe)   REQUIRE c.nom IS UNIQUE",
        "CREATE CONSTRAINT enum_nom    IF NOT EXISTS FOR (e:Enum)     REQUIRE e.nom IS UNIQUE",
        "CREATE CONSTRAINT type_nom    IF NOT EXISTS FOR (t:Type)     REQUIRE t.nom IS UNIQUE",
        "CREATE CONSTRAINT attr_key    IF NOT EXISTS FOR (a:Attribut) REQUIRE a.key IS UNIQUE",
        "CREATE CONSTRAINT doc_id      IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
        "CREATE CONSTRAINT chunk_id    IF NOT EXISTS FOR (c:Chunk)    REQUIRE c.id IS UNIQUE",
    ]:
            self._run(stmt)

    # ------------------------------------------------------------------
    # Classe
    # ------------------------------------------------------------------
    def merge_classe(self, nom, description=None, abstraite=False, attributs=None):
        self._run(
            "MERGE (c:Classe{nom:$nom}) SET c.description=$desc, c.abstraite=$abs",
            nom=nom, desc=description, abs=abstraite,
        )
        for a in (attributs or []):
            self.merge_attribut(classe=nom, **a)

    def merge_attribut(self, classe, nom, type=None, description=None,
                        defaut=None, deprecated=False, obligatoire=None):
        key = f"{classe}.{nom}"
        self._run(
            """
            MERGE (c:Classe{nom:$classe})
            MERGE (a:Attribut{key:$key})
            SET a.nom=$nom, a.description=$desc, a.defaut=$defaut,
                a.deprecated=$dep, a.obligatoire=$obl
            MERGE (c)-[:A_ATTRIBUT]->(a)
            """,
            classe=classe, key=key, nom=nom, desc=description,
            defaut=defaut, dep=deprecated, obl=obligatoire,
        )
        if type:
            label = "Enum" if type.startswith("Enum") else "Type"
            self._run(
                f"MERGE (a:Attribut{{key:$key}}) MERGE (t:{label}{{nom:$t}}) MERGE (a)-[:EST_DE_TYPE]->(t)",
                key=key, t=type,
            )


    def merge_enum(self, nom, valeurs):
        self._run("MERGE (:Enum{nom:$nom})", nom=nom)
        for v in valeurs:
            self._run(
                "MERGE (e:Enum{nom:$e}) MERGE (val:ValeurEnum{key:$k}) SET val.nom=$v MERGE (e)-[:A_VALEUR]->(val)",
                e=nom, v=v, k=f"{nom}.{v}",
            )

    def add_relation(self, source, relation, target, role=None, cardinalite=None):
        self._run(
            f"""
            MERGE (s:Classe{{nom:$s}}) MERGE (t:Classe{{nom:$t}})
            MERGE (s)-[r:{relation}]->(t)
            SET r.role=$role, r.cardinalite=$card
            """,
            s=source, t=target, role=role, card=cardinalite,
        )

    def merge_document(self, doc_id, titre, source=None):
        self._run(
            "MERGE (d:Document{id:$id}) SET d.titre=$titre, d.source=$source",
            id=doc_id, titre=titre, source=source,
        )

    def merge_chunk(self, chunk_id, doc_id, texte, position, embedding):
        self._run(
        """
        MERGE (c:Chunk{id:$cid})
        SET c.texte=$texte, c.position=$pos, c.embedding=$embedding
        WITH c
        MATCH (d:Document{id:$did})
        MERGE (c)-[:APPARTIENT_A]->(d)
        """,
        cid=chunk_id, texte=texte, pos=position, did=doc_id, embedding=embedding,
    )
        
    def lier_document_a_classe(self, doc_id, nom_classe):
        self._run(
        """
        MATCH (d:Document{id:$did}), (c:Classe{nom:$nom})
        MERGE (d)-[:DECRIT]->(c)
        """,
        did=doc_id, nom=nom_classe,
    ) 

def importer_modele_depuis_json(fichier_json, builder):
    with open(fichier_json, "r", encoding="utf-8") as f:
        modele = json.load(f)

    for e in modele.get("enums", []):
        builder.merge_enum(e["nom"], e["valeurs"])

    for c in modele.get("classes", []):
        kwargs = {}
        if c.get("abstraite"): kwargs["abstraite"] = True
        if c.get("description"): kwargs["description"] = c["description"]
        if c.get("attributs"): kwargs["attributs"] = c["attributs"]
        builder.merge_classe(c["nom"], **kwargs)

    for g in modele.get("generalizations", []):
        builder.add_relation(g["source"], "HERITE_DE", g["cible"])

    for r in modele.get("relations", []):
        kwargs = {}
        if r.get("role"): kwargs["role"] = r["role"]
        if r.get("cardinalite") and r["cardinalite"] != "0..*":
            kwargs["cardinalite"] = r["cardinalite"]
        builder.add_relation(r["source"], r["type"], r["cible"], **kwargs)

    print(f"Importation de {fichier_json} terminée avec succès")

def parser_nom_fichier(chemin_fichier):
    nom_fichier = os.path.basename(chemin_fichier)
    nom_sans_ext = os.path.splitext(nom_fichier)[0]
    if "_" in nom_sans_ext :
        nom_classe, reste = nom_sans_ext.split("_", 1)
        return nom_classe, reste
    else :
        return nom_sans_ext, ""

def importer_document(chemin_fichier, builder, splitter, embeddings_model):
    nom_classe, reste = parser_nom_fichier(chemin_fichier)
    doc_id = chemin_fichier.split("/")[-1]

    with open(chemin_fichier, "r", encoding="utf-8") as f:
        texte = f.read()

    builder.merge_document(doc_id, titre=doc_id, source=chemin_fichier)
    builder.lier_document_a_classe(doc_id, nom_classe)

    # 1. Découpage du texte
    chunks = splitter.split_text(texte)
    
    # 2. Calcul des embeddings en lot (plus rapide que un par un)
    embeddings = embeddings_model.embed_documents(chunks)

    # 3. Insertion dans Neo4j
    for i, (chunk_texte, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = f"{doc_id}_chunk_{i}"
        builder.merge_chunk(chunk_id, doc_id, chunk_texte, position=i, embedding=embedding)


def main():
    # 1. Charger les variables d'environnement (pour récupérer MISTRAL_API_KEY)
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("MISTRAL_API_KEY")
    
    # 2. Créer l'INSTANCE du modèle d'embedding
    embeddings_model = MistralAIEmbeddings(model="mistral-embed", api_key=api_key)

    b = ArianeGraphBuilder(URI, USER, PASSWORD)
    b.create_constraints()
    fichiers_json = sorted(glob.glob(f"{DATA_DIR}/*.json"))

    if not fichiers_json:
        print(f"Aucun fichier JSON trouvé dans '{DATA_DIR}'.")
        b.close()
        return

    print(f"{len(fichiers_json)} fichier(s) trouvé(s) dans '{DATA_DIR}'.")

    for fichier in fichiers_json:
        print(f"\n--- Traitement de {fichier} ---")
        try:
            importer_modele_depuis_json(fichier, b)
        except Exception as e:
            print(f"Erreur lors de l'import de {fichier} : {e}")
    
    # --- Import des documents texte ---
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    fichiers_txt = sorted(glob.glob(f"{DOCS_DIR}/*.txt"))
    if not fichiers_txt:
        print(f"Aucun fichier texte trouvé dans '{DOCS_DIR}'.")
    else:
        print(f"\n{len(fichiers_txt)} fichier(s) texte trouvé(s) dans '{DOCS_DIR}'.")
        for fichier in fichiers_txt:
            print(f"--- Import de {fichier} ---")
            try:
                # 3. Passer l'INSTANCE (embeddings_model) et non la CLASSE
                importer_document(fichier, b, splitter, embeddings_model)
            except Exception as e:
                print(f"Erreur lors de l'import de {fichier} : {e}")

    b.close()
    print("\nImportation de tous les fichiers terminée.")

if __name__ == "__main__":
    main()
   
    

