"""Extrait la couche métier de toutes les fiches Docs/*.txt avec reprise."""

import argparse
import json
import os
import time
import hashlib
from pathlib import Path

from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI

from arianes.paths import METIER_DATA_DIR, PROCEDURES_DIR, PROJECT_ROOT, UML_DATA_DIR
from arianes.pipelines.extraction_metier import charger_catalogue, consolider, extraire_document


RACINE = PROJECT_ROOT


def decouvrir_documents(dossier: Path) -> list[Path]:
    return sorted(
        (chemin for chemin in dossier.glob("*.txt") if chemin.is_file()),
        key=lambda chemin: chemin.name.casefold(),
    )


def chemin_resultat(dossier_sortie: Path, document: Path) -> Path:
    return dossier_sortie / f"{document.stem}.metier.json"


def empreinte(document, configuration):
    return hashlib.sha256(document.read_bytes() + configuration.encode()).hexdigest()


def checkpoint_actuel(chemin, signature):
    try:
        return json.loads(chemin.read_text(encoding="utf-8")).get("empreinte_extraction") == signature
    except (OSError, ValueError):
        return False


def charger_resultats(dossier_sortie: Path) -> list[dict]:
    resultats = []
    for chemin in sorted(dossier_sortie.glob("*.metier.json")):
        try:
            resultats.append(json.loads(chemin.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            print(f"Attention : résultat intermédiaire illisible ignoré : {chemin}")
    return resultats


def sauvegarder_json(chemin: Path, donnees: dict):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    temporaire.write_text(
        json.dumps(donnees, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporaire.replace(chemin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, default=PROCEDURES_DIR)
    parser.add_argument("--data", type=Path, default=UML_DATA_DIR)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=METIER_DATA_DIR / "propositions",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=METIER_DATA_DIR / "proposition_globale.json",
    )
    parser.add_argument("--taille-chunk", type=int, default=6000)
    parser.add_argument("--limite", type=int, help="Limite de fiches, utile pour un essai.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Retraite les fiches déjà extraites au lieu de reprendre.",
    )
    parser.add_argument(
        "--inventaire",
        action="store_true",
        help="Affiche seulement les fiches qui seraient traitées.",
    )
    args = parser.parse_args()

    documents = decouvrir_documents(args.docs)
    if args.limite:
        documents = documents[: args.limite]
    if not documents:
        raise RuntimeError(f"Aucune fiche .txt trouvée dans {args.docs}")

    load_dotenv()
    catalogue_signature = hashlib.sha256(b"".join(
        p.name.encode() + p.read_bytes() for p in sorted(args.data.glob("*.json"))
    )).hexdigest()
    configuration = json.dumps([args.taille_chunk,
        os.getenv("MISTRAL_MODEL", "mistral-small-latest"), catalogue_signature,
        hashlib.sha256(Path(__file__).with_name("extraction_metier.py").read_bytes()).hexdigest(),
        hashlib.sha256(Path(__file__).with_name("validation_metier.py").read_bytes()).hexdigest()])
    signatures = {d.name: empreinte(d, configuration) for d in documents}
    deja_faits = {
        document.name
        for document in documents
        if checkpoint_actuel(chemin_resultat(args.output_dir, document), signatures[document.name]) and not args.force
    }
    a_traiter = [document for document in documents if document.name not in deja_faits]
    print(
        f"Fiches trouvées : {len(documents)} | déjà extraites : {len(deja_faits)} | "
        f"à traiter : {len(a_traiter)}"
    )
    if args.inventaire:
        for document in a_traiter:
            print(f"- {document.name}")
        return

    load_dotenv()
    if not os.getenv("MISTRAL_API_KEY"):
        raise RuntimeError("MISTRAL_API_KEY est absent du fichier .env")
    catalogue = charger_catalogue(args.data)
    llm = ChatMistralAI(
        model=os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
        api_key=os.getenv("MISTRAL_API_KEY"),
        temperature=0,
        timeout=60,
    )

    erreurs = []
    for numero, document in enumerate(a_traiter, 1):
        debut = time.perf_counter()
        try:
            resultat = extraire_document(
                llm,
                document,
                catalogue,
                args.taille_chunk,
            )
            resultat["empreinte_extraction"] = signatures[document.name]
            sauvegarder_json(chemin_resultat(args.output_dir, document), resultat)
            print(
                f"[{numero}/{len(a_traiter)}] OK {document.name} : "
                f"{len(resultat['concepts'])} concepts, "
                f"{len(resultat['relations'])} relations "
                f"({time.perf_counter() - debut:.1f}s)"
            )
        except Exception as exc:
            erreurs.append(
                {"document": document.name, "erreur": f"{type(exc).__name__}: {exc}"}
            )
            print(f"[{numero}/{len(a_traiter)}] ECHEC {document.name} : {exc}")

    echecs = {e["document"] for e in erreurs}
    resultats = [json.loads(chemin_resultat(args.output_dir, d).read_text(encoding="utf-8"))
                 for d in documents if d.name not in echecs
                 and checkpoint_actuel(chemin_resultat(args.output_dir, d), signatures[d.name])]
    if not resultats:
        raise RuntimeError("Aucun résultat intermédiaire exploitable.")
    global_resultat = consolider(resultats)
    global_resultat["documents_traites"] = sorted(
        resultat.get("document_source", "") for resultat in resultats
    )
    global_resultat["erreurs_documents"] = erreurs
    sauvegarder_json(args.output, global_resultat)

    print(
        f"\nProposition globale A_REVOIR : {len(global_resultat['concepts'])} concepts, "
        f"{len(global_resultat['relations'])} relations."
    )
    print(f"Rapport : {args.output}")
    if erreurs:
        print(f"Fiches en échec : {len(erreurs)} (relance la même commande pour reprendre).")


if __name__ == "__main__":
    main()
