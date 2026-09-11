"""Importe dans Neo4j des sous-graphes métier validés et sourcés."""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase
from arianes.paths import METIER_DATA_DIR
from arianes.pipelines.validation_metier import normaliser, verifier_import


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
    definition = deepcopy(definition)
    verifier_import(definition)
    with driver.session() as session:
        existants = {
            normaliser(record["nom"]): {"id": record["id"], "nom": record["nom"]}
            for record in session.run(
                "MATCH (c:ConceptMetier) RETURN c.id AS id, c.nom AS nom"
            )
            if record["nom"]
        }
        correspondances = {
            concept["id"]: existants[normaliser(concept["nom"])]["id"]
            for concept in definition["concepts"]
            if normaliser(concept["nom"]) in existants
            and existants[normaliser(concept["nom"])]["id"] != concept["id"]
        }
        if correspondances:
            for concept in definition["concepts"]:
                concept["id"] = correspondances.get(concept["id"], concept["id"])
            for relation in definition["relations"]:
                relation["source"] = correspondances.get(relation["source"], relation["source"])
                relation["cible"] = correspondances.get(relation["cible"], relation["cible"])

            fusionnes = {}
            for concept in definition["concepts"]:
                courant = fusionnes.setdefault(concept["id"], concept)
                for champ in ("aliases", "classes_arianes", "documents"):
                    courant[champ] = sorted(set(courant.get(champ, [])) | set(concept.get(champ, [])))
            definition["concepts"] = list(fusionnes.values())
            verifier_import(definition)

        session.run(
            "CREATE CONSTRAINT concept_metier_id IF NOT EXISTS "
            "FOR (c:ConceptMetier) REQUIRE c.id IS UNIQUE"
        ).consume()

        for concept in definition["concepts"]:
            session.run(
                """
                MERGE (c:ConceptMetier {id: $id})
                SET c.nom = $nom, c.aliases = $aliases, c.description = $description,
                    c.domaine = $domaine, c.categorie = $categorie, c.valide = ($statut = 'VALIDE'),
                    c.actif = true, c.validation_documentaire = ($statut = 'VALIDE'),
                    c.statut = $statut, c.validation_experte = $validation_experte
                WITH c
                UNWIND $classes AS nom_classe
                MATCH (classe:Classe {nom: nom_classe})
                MERGE (c)-[:REPRESENTE_PAR]->(classe)
                """,
                **{
                    **concept,
                    "categorie": concept.get("categorie", "INCONNU"),
                    "statut": concept.get("statut", "PROBABLE"),
                    "validation_experte": bool(concept.get("validation_experte", False)),
                },
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
            chunk_ids = preuve.get("chunk_ids", []) if isinstance(preuve, dict) else []
            if not chunk_ids and source_document and citation:
                citation_normalisee = normaliser(citation)
                candidats = session.run(
                    "MATCH (chunk:Chunk)-[:APPARTIENT_A]->(d:Document) "
                    "WHERE toLower(d.id) ENDS WITH toLower($document) "
                    "OR toLower(d.titre) ENDS WITH toLower($document) "
                    "RETURN chunk.id AS id, chunk.texte AS texte ORDER BY chunk.position",
                    document=source_document,
                )
                chunk_ids = [
                    candidat["id"] for candidat in candidats
                    if citation_normalisee in normaliser(candidat["texte"])
                    or (
                        len(normaliser(candidat["texte"])) >= 30
                        and normaliser(candidat["texte"]) in citation_normalisee
                    )
                ]
            session.run(
                """
                MATCH (a:ConceptMetier {id: $source})
                MATCH (b:ConceptMetier {id: $cible})
                MERGE (a)-[r:RELATION_METIER {type: $type,
                    source_document: $source_document, preuve: $citation, lignes: $lignes}]->(b)
                SET r.preuve = $citation, r.source_document = $source_document,
                    r.lignes = $lignes, r.valide = ($statut = 'VALIDE'),
                    r.actif = true, r.validation_documentaire = ($statut = 'VALIDE'),
                    r.chunk_ids = $chunk_ids, r.condition = $condition,
                    r.exception = $exception, r.validation = $validation,
                    r.statut = $statut, r.score_confiance = $score_confiance,
                    r.niveau_validation = $niveau_validation,
                    r.validation_experte = $validation_experte,
                    r.avertissements = $avertissements,
                    r.criteres_json = $criteres_json
                WITH a, b
                UNWIND $chunk_ids AS chunk_id
                MATCH (chunk:Chunk {id: chunk_id})
                MERGE (a)-[:ETAYE_PAR]->(chunk)
                MERGE (b)-[:ETAYE_PAR]->(chunk)
                """,
                source=relation["source"],
                cible=relation["cible"],
                type=relation["type"],
                citation=citation,
                source_document=source_document,
                lignes=lignes,
                chunk_ids=chunk_ids,
                condition=relation.get("condition", ""),
                exception=relation.get("exception", ""),
                validation=relation.get("validation", definition.get("methode_validation", "Relecture explicite")),
                statut=relation.get("statut", "PROBABLE"),
                score_confiance=float(relation.get("score_confiance", 0.5)),
                niveau_validation=relation.get("niveau_validation", "DOCUMENTAIRE"),
                validation_experte=bool(relation.get("validation_experte", False)),
                avertissements=relation.get("avertissements", []),
                criteres_json=json.dumps(relation.get("criteres", {}), ensure_ascii=False),
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
        default=METIER_DATA_DIR / "poste_aiguillage.json",
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
