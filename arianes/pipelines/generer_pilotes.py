"""Génère un pilote documentaire gradué pour chaque fiche et une synthèse globale."""

import argparse
import json
from pathlib import Path

from arianes.paths import METIER_DATA_DIR
from arianes.pipelines.selection_prudente import selectionner


def generer(dossier_entree: Path, dossier_sortie: Path) -> dict:
    fichiers = sorted(dossier_entree.glob("*.metier.json"))
    if not fichiers:
        raise ValueError(f"Aucune proposition contrôlée dans {dossier_entree}")
    dossier_sortie.mkdir(parents=True, exist_ok=True)
    bilan = []
    for fichier in fichiers:
        definition = json.loads(fichier.read_text(encoding="utf-8"))
        pilote = selectionner(definition)
        sortie = dossier_sortie / fichier.name.replace(".metier.json", ".pilote.json")
        sortie.write_text(json.dumps(pilote, ensure_ascii=False, indent=2), encoding="utf-8")
        bilan.append({
            "document": definition.get("document_source", fichier.stem),
            "fichier": sortie.name,
            "concepts": len(pilote["concepts"]),
            "relations_valides": pilote["relations_valides"],
            "relations_probables": pilote["relations_probables"],
            "relations_rejetees": len(pilote["relations_rejetees"]),
        })
    rapport = {
        "documents": len(bilan),
        "concepts": sum(x["concepts"] for x in bilan),
        "relations_valides": sum(x["relations_valides"] for x in bilan),
        "relations_probables": sum(x["relations_probables"] for x in bilan),
        "relations_rejetees": sum(x["relations_rejetees"] for x in bilan),
        "pilotes": bilan,
        "validation_experte": False,
    }
    (dossier_sortie / "rapport_pilotes.json").write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return rapport


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir", type=Path,
        default=METIER_DATA_DIR / "corrections_v3" / "propositions",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=METIER_DATA_DIR / "pilotes_documentaires",
    )
    args = parser.parse_args()
    print(json.dumps(generer(args.input_dir, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
