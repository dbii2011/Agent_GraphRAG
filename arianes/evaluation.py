"""Évalue le retrieval GraphRAG et, en option, les réponses finales de Mistral."""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langchain_mistralai import MistralAIEmbeddings
from neo4j import GraphDatabase

from .agent import AgentLG
from .paths import PROJECT_ROOT, TESTS_DIR
from .retrieval import GraphRAGRetriever


RACINE = PROJECT_ROOT
QUESTIONS_PAR_DEFAUT = TESTS_DIR / "evaluation_questions.json"
RAPPORT_PAR_DEFAUT = PROJECT_ROOT / "reports" / "evaluation_graphrag.json"


def contient_source(resultat: dict, source_attendue: str) -> bool:
    attendue = source_attendue.casefold()
    valeurs = []
    for document in resultat["sous_graphe"]["documents"]:
        valeurs.extend(
            str(document.get(cle) or "") for cle in ("id", "titre", "source")
        )
    for chunk in resultat["chunks"]:
        valeurs.extend(
            str(chunk.get(cle) or "") for cle in ("document", "titre", "citation")
        )
    return any(attendue in valeur.casefold() for valeur in valeurs)


def evaluer_cas(cas: dict, resultat: dict) -> tuple[list[dict], bool]:
    controles = []

    def ajouter(nom: str, attendu, obtenu, succes: bool):
        controles.append(
            {"controle": nom, "attendu": attendu, "obtenu": obtenu, "succes": succes}
        )

    ajouter(
        "mode",
        cas["mode"],
        resultat["mode"],
        resultat["mode"] == cas["mode"],
    )
    if "classes" in cas:
        attendues = cas["classes"]
        obtenues = resultat["classes_racines"]
        ajouter(
            "classes_racines",
            attendues,
            obtenues,
            all(classe in obtenues for classe in attendues),
        )
    if "source" in cas:
        trouvee = contient_source(resultat, cas["source"])
        ajouter("source", cas["source"], trouvee, trouvee)

    if cas.get("sans_reponse_attendue"):
        aucun_ancrage = not resultat["classes_racines"] and not resultat["chunks"]
        ajouter(
            "absence_ancrage",
            True,
            aucun_ancrage,
            aucun_ancrage,
        )

    return controles, all(controle["succes"] for controle in controles)


def historique_du_cas(cas: dict) -> list[dict[str, str]]:
    contexte = cas.get("contexte")
    if not contexte:
        return []
    return [{"role": "user", "content": contexte}]


def executer(args) -> tuple[dict, int]:
    load_dotenv()
    cle_mistral = os.getenv("MISTRAL_API_KEY")
    mot_de_passe = os.getenv("NEO4J_PASSWORD")
    if not cle_mistral:
        raise RuntimeError("MISTRAL_API_KEY est absent du fichier .env")
    if not mot_de_passe:
        raise RuntimeError("NEO4J_PASSWORD est absent du fichier .env")

    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), mot_de_passe),
    )
    embeddings = MistralAIEmbeddings(
        model="mistral-embed",
        api_key=cle_mistral,
    )
    retriever = GraphRAGRetriever(driver, embeddings)
    agent = None
    if args.with_llm:
        agent = AgentLG()

    cas_evalues = []
    try:
        driver.verify_connectivity()
        for numero, cas in enumerate(questions, 1):
            debut = time.perf_counter()
            historique = historique_du_cas(cas)
            entree = {
                "numero": numero,
                "question": cas["question"],
                "attendus": cas,
            }
            try:
                resultat = retriever.retrieve(cas["question"], historique=historique)
                controles, succes = evaluer_cas(cas, resultat)
                entree.update(
                    {
                        "succes": succes,
                        "controles": controles,
                        "retrieval": {
                            "mode": resultat["mode"],
                            "classes_racines": resultat["classes_racines"],
                            "classes_sous_graphe": [
                                c["nom"] for c in resultat["sous_graphe"]["classes"]
                            ],
                            "sources": resultat["citations"],
                            "scores_chunks": [
                                {
                                    "citation": chunk["citation"],
                                    "semantique": chunk.get("score_semantique"),
                                    "lexical": chunk.get("score_lexical"),
                                    "fusion": chunk.get("score_fusion"),
                                }
                                for chunk in resultat["chunks"]
                            ],
                            "nombre_chunks": len(resultat["chunks"]),
                        },
                    }
                )
                if agent:
                    entree["reponse"] = agent.ask(cas["question"], historique=historique)
            except Exception as exc:
                entree.update({"succes": False, "erreur": f"{type(exc).__name__}: {exc}"})
            entree["duree_secondes"] = round(time.perf_counter() - debut, 3)
            cas_evalues.append(entree)
            marqueur = "OK" if entree["succes"] else "ECHEC"
            print(f"[{numero:02d}/{len(questions):02d}] {marqueur} - {cas['question']}")
    finally:
        driver.close()
        if agent:
            agent.close()

    reussis = sum(cas["succes"] for cas in cas_evalues)
    rapport = {
        "date_utc": datetime.now(timezone.utc).isoformat(),
        "avec_mistral": args.with_llm,
        "total": len(cas_evalues),
        "reussis": reussis,
        "echoues": len(cas_evalues) - reussis,
        "taux_reussite": round(reussis / max(1, len(cas_evalues)), 4),
        "cas": cas_evalues,
    }
    args.output.write_text(
        json.dumps(rapport, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"\nRésultat : {reussis}/{len(cas_evalues)} réussis "
        f"({rapport['taux_reussite']:.0%})"
    )
    print(f"Rapport : {args.output}")
    return rapport, 0 if reussis == len(cas_evalues) else 1


def analyser_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--questions",
        type=Path,
        default=QUESTIONS_PAR_DEFAUT,
        help="Fichier JSON contenant les questions et résultats attendus.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RAPPORT_PAR_DEFAUT,
        help="Chemin du rapport JSON produit.",
    )
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="Appelle aussi Mistral pour produire la réponse finale de chaque cas.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    try:
        _, code = executer(analyser_arguments())
    except Exception as exc:
        print(f"Erreur d'évaluation : {type(exc).__name__}: {exc}", file=sys.stderr)
        code = 2
    raise SystemExit(code)
