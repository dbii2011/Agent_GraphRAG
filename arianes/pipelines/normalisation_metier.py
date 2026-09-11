"""Détecte et fusionne prudemment les doublons nominaux de ConceptMetier."""

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

from arianes.paths import METIER_DATA_DIR
from arianes.pipelines.validation_metier import normaliser


def choisir_canonique(concepts: list[dict]) -> dict:
    """Privilégie un concept typé, puis l'identifiant le plus court et stable."""
    return sorted(
        concepts,
        key=lambda c: (
            c.get("categorie") in (None, "", "INCONNU"),
            len(c.get("id", "")),
            c.get("id", ""),
        ),
    )[0]


def trouver_doublons(session) -> list[dict]:
    concepts = [
        record.data()
        for record in session.run(
            "MATCH (c:ConceptMetier) RETURN c.id AS id, c.nom AS nom, "
            "c.categorie AS categorie, c.domaine AS domaine ORDER BY c.id"
        )
    ]
    groupes = defaultdict(list)
    for concept in concepts:
        groupes[normaliser(concept.get("nom", ""))].append(concept)
    return [
        {
            "nom_normalise": nom,
            "canonique": choisir_canonique(groupe),
            "doublons": [c for c in groupe if c != choisir_canonique(groupe)],
        }
        for nom, groupe in groupes.items()
        if nom and len(groupe) > 1
    ]


def sauvegarder(session, groupes: list[dict], dossier: Path) -> Path:
    ids = [
        concept["id"]
        for groupe in groupes
        for concept in [groupe["canonique"], *groupe["doublons"]]
    ]
    noeuds = [
        record.data()
        for record in session.run(
            "MATCH (c:ConceptMetier) WHERE c.id IN $ids "
            "RETURN c.id AS id, properties(c) AS proprietes",
            ids=ids,
        )
    ]
    relations = [
        record.data()
        for record in session.run(
            "MATCH (a)-[r]-(b) WHERE a:ConceptMetier AND a.id IN $ids "
            "RETURN a.id AS source, type(r) AS type, b.id AS cible, "
            "labels(b) AS labels_cible, properties(r) AS proprietes",
            ids=ids,
        )
    ]
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"concepts_metier_avant_fusion_{datetime.now():%Y%m%d_%H%M%S}.json"
    chemin.write_text(
        json.dumps({"groupes": groupes, "noeuds": noeuds, "relations": relations}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return chemin


def fusionner(session, canonique: str, doublon: str):
    # Relations métier sortantes et entrantes, avec toutes leurs preuves.
    session.run(
        """
        MATCH (canon:ConceptMetier {id: $canonique})
        MATCH (dup:ConceptMetier {id: $doublon})-[r:RELATION_METIER]->(cible:ConceptMetier)
        WHERE cible <> canon
        MERGE (canon)-[nouvelle:RELATION_METIER {
            type: r.type, source_document: r.source_document,
            preuve: r.preuve, lignes: r.lignes
        }]->(cible)
        SET nouvelle += properties(r)
        """,
        canonique=canonique,
        doublon=doublon,
    ).consume()
    session.run(
        """
        MATCH (canon:ConceptMetier {id: $canonique})
        MATCH (source:ConceptMetier)-[r:RELATION_METIER]->(dup:ConceptMetier {id: $doublon})
        WHERE source <> canon
        MERGE (source)-[nouvelle:RELATION_METIER {
            type: r.type, source_document: r.source_document,
            preuve: r.preuve, lignes: r.lignes
        }]->(canon)
        SET nouvelle += properties(r)
        """,
        canonique=canonique,
        doublon=doublon,
    ).consume()

    # Liens de traçabilité sortants vers classes, documents et chunks.
    for type_relation in ("REPRESENTE_PAR", "DOCUMENTE_PAR", "ETAYE_PAR"):
        session.run(
            f"""
            MATCH (canon:ConceptMetier {{id: $canonique}})
            MATCH (dup:ConceptMetier {{id: $doublon}})-[r:{type_relation}]->(cible)
            MERGE (canon)-[nouvelle:{type_relation}]->(cible)
            SET nouvelle += properties(r)
            """,
            canonique=canonique,
            doublon=doublon,
        ).consume()

    session.run(
        "MATCH (dup:ConceptMetier {id: $doublon}) DETACH DELETE dup",
        doublon=doublon,
    ).consume()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Applique les fusions après sauvegarde.")
    args = parser.parse_args()
    load_dotenv()
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD")),
    )
    try:
        with driver.session() as session:
            groupes = trouver_doublons(session)
            print(json.dumps(groupes, ensure_ascii=False, indent=2))
            if args.apply and groupes:
                sauvegarde = sauvegarder(session, groupes, METIER_DATA_DIR / "sauvegardes")
                for groupe in groupes:
                    for doublon in groupe["doublons"]:
                        fusionner(session, groupe["canonique"]["id"], doublon["id"])
                print(f"Fusion terminée. Sauvegarde : {sauvegarde}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
