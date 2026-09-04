"""Recontrôle hors ligne les checkpoints sans écraser les originaux ni appeler Neo4j."""

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from pipeline_graphe_metier import consolider
from validation_metier import categorie_concept, controler_relation, VERSION_VALIDATION

RACINE = Path(__file__).resolve().parent


def lire_passage(preuve, docs):
    if not isinstance(preuve, dict):
        raise ValueError("preuve non structurée")
    nom = preuve.get("document", "")
    chemin = (docs / nom).resolve()
    if not nom or chemin.parent != docs.resolve() or chemin.suffix.lower() != ".txt":
        raise ValueError("document hors du corpus")
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    plage = str(preuve.get("lignes", ""))
    debut, fin = map(int, plage.split("-"))
    if not 1 <= debut <= fin <= len(lignes):
        raise ValueError("plage de lignes invalide")
    return "\n".join(lignes[debut - 1:fin])


def recontroler(definition, docs):
    resultat = deepcopy(definition)
    concepts = {c["id"]: c for c in resultat["concepts"]}
    if len(concepts) != len(resultat["concepts"]):
        raise ValueError("Concepts dupliqués dans le checkpoint")
    for c in concepts.values():
        c["categorie"] = categorie_concept(c)
        c["statut"] = "A_REVOIR"
    resultat["relations"] = []
    resultat.setdefault("relations_rejetees", [])
    for relation in definition["relations"]:
        try:
            passage = lire_passage(relation.get("preuve"), docs)
        except (ValueError, OSError, UnicodeError) as exc:
            rejet = deepcopy(relation)
            rejet.update(statut="REJETE", motifs_rejet=[f"preuve invérifiable : {exc}"])
            resultat["relations_rejetees"].append(rejet)
            continue
        controle = controler_relation(relation, concepts, passage)
        destination = "relations_rejetees" if controle["statut"] == "REJETE" else "relations"
        resultat[destination].append(controle)
    resultat.update(statut="A_REVOIR", version_validation=VERSION_VALIDATION)
    return resultat


def executer(entree, sortie, docs):
    fichiers = sorted(entree.glob("*.metier.json"))
    if not fichiers:
        raise ValueError("Aucun checkpoint trouvé")
    # Ne jamais écraser un précédent audit ou un checkpoint source.
    if sortie.exists():
        raise ValueError("Le dossier de sortie existe déjà. Choisir un nouveau --output-dir.")
    resultats, empreintes = [], {}
    for fichier in fichiers:
        contenu = fichier.read_bytes()
        empreintes[fichier.name] = hashlib.sha256(contenu).hexdigest()
        resultat = recontroler(json.loads(contenu), docs)
        resultats.append((fichier.name, resultat))
    global_resultat = recontroler(consolider([r for _, r in resultats]), docs)
    global_resultat["documents_traites"] = sorted(r.get("document_source", n) for n, r in resultats)
    global_resultat["erreurs_documents"] = []
    rejetes = global_resultat["relations_rejetees"]
    rapport = {
        "version_validation": VERSION_VALIDATION,
        "empreintes_originaux_sha256": empreintes,
        "documents": len(resultats),
        "concepts": len(global_resultat["concepts"]),
        "relations_conservees_a_revoir": len(global_resultat["relations"]),
        "relations_rejetees": len(rejetes),
        "relations_corrigees_conservees": sum(bool(r.get("corrections")) for r in global_resultat["relations"]),
        "motifs_rejets": dict(Counter(m for r in rejetes for m in r.get("motifs_rejet", []))),
        "note": "Aucun résultat n'est validé métier automatiquement. Les erreurs_validation historiques concernent des propositions déjà rejetées lors de l'extraction.",
    }
    sortie.mkdir(parents=True, exist_ok=False)
    (sortie / "propositions").mkdir()
    def sauvegarder(path, obj):
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    for nom, resultat in resultats:
        sauvegarder(sortie / "propositions" / nom, resultat)
    sauvegarder(sortie / "proposition_globale.json", global_resultat)
    sauvegarder(sortie / "rapport_controle.json", rapport)
    return rapport


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RACINE / "DataMetier/propositions")
    parser.add_argument("--output-dir", type=Path, default=RACINE / "DataMetier/corrections_v2")
    parser.add_argument("--docs", type=Path, default=RACINE / "Docs")
    args = parser.parse_args()
    rapport = executer(args.input_dir, args.output_dir, args.docs)
    print(json.dumps({k: v for k, v in rapport.items() if k != "empreintes_originaux_sha256"}, ensure_ascii=True, indent=2))
