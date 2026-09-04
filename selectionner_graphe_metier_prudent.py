"""Crée une sélection automatique conservatrice avant import dans Neo4j.

Cette sélection ne remplace pas une expertise métier. Elle accepte uniquement
les relations dont la preuve a été retrouvée dans le document et dont le seul
avertissement éventuel porte sur la catégorie des concepts.
"""

import argparse
import json
from pathlib import Path


def est_acceptable(relation: dict) -> bool:
    if relation.get("motifs_rejet") or relation.get("statut") == "REJETE":
        return False
    avertissements = relation.get("avertissements", [])
    return all("source ou cible" in avertissement.lower() for avertissement in avertissements)


def selectionner(definition: dict) -> dict:
    relations = [r for r in definition.get("relations", []) if est_acceptable(r)]
    ids_utilises = {identifiant for r in relations for identifiant in (r["source"], r["cible"])}
    concepts = [c for c in definition.get("concepts", []) if c["id"] in ids_utilises]

    concepts_valides = [{**c, "statut": "VALIDE"} for c in concepts]
    relations_valides = [
        {
            **r,
            "statut": "VALIDE",
            "validation": "AUTO_PRUDENTE_PREUVE_DOCUMENTAIRE",
        }
        for r in relations
    ]
    return {
        "domaine": definition.get("domaine", "gestion_ferroviaire"),
        "statut": "VALIDE",
        "methode_validation": "AUTO_PRUDENTE_PREUVE_DOCUMENTAIRE",
        "concepts": concepts_valides,
        "relations": relations_valides,
        "relations_exclues": len(definition.get("relations", [])) - len(relations_valides),
        "avertissement": (
            "Validation automatique conservatrice : une validation experte reste souhaitable."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("DataMetier/corrections_v2/proposition_globale.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("DataMetier/selection_auto_prudente.json"),
    )
    args = parser.parse_args()
    definition = json.loads(args.input.read_text(encoding="utf-8"))
    resultat = selectionner(definition)
    args.output.write_text(json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Sélection créée : {len(resultat['concepts'])} concepts, "
        f"{len(resultat['relations'])} relations, "
        f"{resultat['relations_exclues']} relations exclues."
    )


if __name__ == "__main__":
    main()
