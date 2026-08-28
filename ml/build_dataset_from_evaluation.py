"""Construit un dataset prototype depuis evaluation_graphrag.json."""

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.reranker import extraire_features


def construire(rapport: dict) -> list[dict]:
    exemples = []
    for cas in rapport.get("cas", []):
        source_attendue = cas.get("attendus", {}).get("source")
        scores = cas.get("retrieval", {}).get("scores_chunks", [])
        if not source_attendue or not scores:
            continue
        for rang, score in enumerate(scores, 1):
            citation = score.get("citation", "")
            chunk = {
                "citation": citation,
                "titre": citation.split(" — passage", 1)[0],
                "score_semantique": score.get("semantique"),
                "score_lexical": score.get("lexical"),
                "score_fusion": score.get("fusion"),
                "texte": "",
            }
            exemples.append(
                {
                    "question_id": cas.get("numero"),
                    "question": cas["question"],
                    "chunk_id": citation,
                    "features": extraire_features(cas["question"], chunk, rang).tolist(),
                    "label": int(source_attendue.casefold() in citation.casefold()),
                    "label_source": "weak_expected_document",
                }
            )
    return exemples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rapport", type=Path, nargs="?", default=Path("evaluation_graphrag.json"))
    parser.add_argument("--output", type=Path, default=Path("ml/datasets/reranker_prototype.jsonl"))
    args = parser.parse_args()
    exemples = construire(json.loads(args.rapport.read_text(encoding="utf-8")))
    if not exemples or len({e["label"] for e in exemples}) < 2:
        raise RuntimeError("Le rapport ne fournit pas assez d'exemples positifs et négatifs.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(json.dumps(exemple, ensure_ascii=False) for exemple in exemples) + "\n",
        encoding="utf-8",
    )
    print(
        f"Dataset : {len(exemples)} exemples, "
        f"{sum(e['label'] for e in exemples)} positifs.\n{args.output}"
    )


if __name__ == "__main__":
    main()
