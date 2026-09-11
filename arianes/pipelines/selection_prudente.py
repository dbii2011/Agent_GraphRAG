"""Crée un pilote global gradué : relations VALIDE, PROBABLE et REJETE."""

import argparse
import json
from pathlib import Path

from arianes.paths import METIER_DATA_DIR


def est_acceptable(relation: dict) -> bool:
    return (
        relation.get("statut") in {"VALIDE", "PROBABLE"}
        and not relation.get("motifs_rejet")
    )


def selectionner(definition: dict) -> dict:
    relations = [r for r in definition.get("relations", []) if est_acceptable(r)]
    ids_utilises = {identifiant for r in relations for identifiant in (r["source"], r["cible"])}
    concepts = [c for c in definition.get("concepts", []) if c["id"] in ids_utilises]

    concepts_valides = [
        {**c, "statut": c.get("statut") if c.get("statut") in {"VALIDE", "PROBABLE"}
         else "PROBABLE", "validation_experte": False}
        for c in concepts
    ]
    relations_retenues = [
        {
            **r,
            "validation": "CLASSIFICATION_DOCUMENTAIRE_AUTOMATIQUE_V3",
            "validation_experte": False,
        }
        for r in relations
    ]
    return {
        "domaine": definition.get("domaine", "gestion_ferroviaire"),
        "statut": "PROBABLE" if any(r["statut"] == "PROBABLE" for r in relations_retenues) else "VALIDE",
        "methode_validation": "CLASSIFICATION_DOCUMENTAIRE_AUTOMATIQUE_V3",
        "validation_experte": False,
        "concepts": concepts_valides,
        "relations": relations_retenues,
        "relations_valides": sum(r["statut"] == "VALIDE" for r in relations_retenues),
        "relations_probables": sum(r["statut"] == "PROBABLE" for r in relations_retenues),
        "relations_rejetees": definition.get("relations_rejetees", []),
        "relations_exclues": (
            len(definition.get("relations", [])) - len(relations_retenues)
            + len(definition.get("relations_rejetees", []))
        ),
        "avertissement": (
            "Validation documentaire automatique : aucune certification experte ferroviaire."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=METIER_DATA_DIR / "corrections_v3" / "proposition_globale.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=METIER_DATA_DIR / "pilote_global_documentaire.json",
    )
    args = parser.parse_args()
    definition = json.loads(args.input.read_text(encoding="utf-8"))
    resultat = selectionner(definition)
    args.output.write_text(json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"Sélection créée : {len(resultat['concepts'])} concepts, "
        f"{len(resultat['relations'])} relations "
        f"({resultat['relations_valides']} VALIDE, {resultat['relations_probables']} PROBABLE), "
        f"{resultat['relations_exclues']} exclues."
    )


if __name__ == "__main__":
    main()
