"""Importe dans Neo4j des sous-graphes métier validés et sourcés."""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


def charger_definition(chemin: Path) -> dict:
    definition = json.loads(chemin.read_text(encoding="utf-8"))
    ids = {concept["id"] for concept in definition["concepts"]}
    if len(ids) != len(definition["concepts"]):
        raise ValueError("Les identifiants des concepts métier doivent être uniques.")
    for relation in definition["relations"]:
        if relation["source"] not in ids or relation["cible"] not in ids:
            raise ValueError(f"Relation vers un concept inconnu : {relation}")
    return definition


def importer(driver, definition: dict) -> dict:
    with driver.session() as session:
        session.run(
            "CREATE CONSTRAINT concept_metier_id IF NOT EXISTS "
            "FOR (c:ConceptMetier) REQUIRE c.id IS UNIQUE"
        ).consume()

        for concept in definition["concepts"]:
            session.run(
                """
                MERGE (c:ConceptMetier {id: $id})
                SET c.nom = $nom, c.aliases = $aliases, c.description = $description,
                    c.domaine = $domaine, c.valide = true
                WITH c
                UNWIND $classes AS nom_classe
                MATCH (classe:Classe {nom: nom_classe})
                MERGE (c)-[:REPRESENTE_PAR]->(classe)
                """,
                **concept,
                domaine=definition["domaine"],
                classes=concept.get("classes_arianes", []),
            ).consume()
            session.run(
                """
                MATCH (c:ConceptMetier {id: $id})
                UNWIND $documents AS fichier
                MATCH (d:Document)
                WHERE toLower(d.id) ENDS WITH toLower(fichier)
                   OR toLower(d.titre) ENDS WITH toLower(fichier)
                MERGE (c)-[:DOCUMENTE_PAR]->(d)
                """,
                id=concept["id"],
                documents=concept.get("documents", []),
            ).consume()

        for relation in definition["relations"]:
            preuve = relation.get("preuve", "")
            if isinstance(preuve, dict):
                citation = preuve.get("citation", "")
                source_document = preuve.get("document", "")
                lignes = preuve.get("lignes", "")
            else:
                citation = str(preuve)
                source_document = ""
                lignes = ""
            session.run(
                """
                MATCH (a:ConceptMetier {id: $source})
                MATCH (b:ConceptMetier {id: $cible})
                MERGE (a)-[r:RELATION_METIER {type: $type}]->(b)
                SET r.preuve = $citation, r.source_document = $source_document,
                    r.lignes = $lignes, r.valide = true
                """,
                source=relation["source"],
                cible=relation["cible"],
                type=relation["type"],
                citation=citation,
                source_document=source_document,
                lignes=lignes,
            ).consume()

        compte = session.run(
            """
            MATCH (c:ConceptMetier {domaine: $domaine})
            OPTIONAL MATCH (c)-[r:RELATION_METIER]->()
            RETURN count(DISTINCT c) AS concepts, count(DISTINCT r) AS relations
            """,
            domaine=definition["domaine"],
        ).single()
    return dict(compte)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "definition",
        nargs="?",
        type=Path,
        default=Path("DataMetier/poste_aiguillage.json"),
    )
    args = parser.parse_args()
    load_dotenv()
    if not os.getenv("NEO4J_PASSWORD"):
        raise RuntimeError("NEO4J_PASSWORD est absent du fichier .env")
    definition = charger_definition(args.definition)
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD")),
    )
    try:
        resultat = importer(driver, definition)
    finally:
        driver.close()
    print(
        f"Sous-graphe importé : {resultat['concepts']} concepts, "
        f"{resultat['relations']} relations métier."
    )


if __name__ == "__main__":
    main()
