"""Compare le reranker au score de fusion par validation croisée par question."""

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.reranker import LinearReranker
from ml.train_reranker import charger_dataset, entrainer


def metriques_classement(groupes_scores, k=5):
    mrr, ndcg, recall = [], [], []
    for labels, scores in groupes_scores:
        ordre = np.argsort(-scores)
        tries = labels[ordre]
        positions = np.flatnonzero(tries == 1)
        mrr.append(0.0 if not len(positions) else 1.0 / (positions[0] + 1))
        gains = sum(float(label) / math.log2(rang + 2) for rang, label in enumerate(tries[:k]))
        ideal = sorted(labels, reverse=True)[:k]
        gain_ideal = sum(float(label) / math.log2(rang + 2) for rang, label in enumerate(ideal))
        ndcg.append(gains / gain_ideal if gain_ideal else 0.0)
        recall.append(float(tries[:k].sum()) / max(1.0, float(labels.sum())))
    return {
        "mrr": float(np.mean(mrr)),
        f"ndcg@{k}": float(np.mean(ndcg)),
        f"recall@{k}": float(np.mean(recall)),
    }


def validation_croisee(lignes, x, y):
    indices_par_question = defaultdict(list)
    for indice, ligne in enumerate(lignes):
        indices_par_question[str(ligne["question_id"])].append(indice)
    baseline, ml = [], []
    for indices_test in indices_par_question.values():
        masque = np.ones(len(y), dtype=bool)
        masque[indices_test] = False
        if len(set(y[masque])) < 2:
            continue
        weights, bias, means, scales = entrainer(x[masque], y[masque])
        modele = LinearReranker(weights, bias, means, scales)
        x_test, y_test = x[indices_test], y[indices_test]
        scores_ml = np.asarray([modele.predict_proba_features(row) for row in x_test])
        baseline.append((y_test, x_test[:, 2]))
        ml.append((y_test, scores_ml))
    if not ml:
        raise RuntimeError("Pas assez de groupes annotés pour la validation croisée.")
    return {
        "questions_evaluees": len(ml),
        "baseline_score_fusion": metriques_classement(baseline),
        "reranker_validation_croisee": metriques_classement(ml),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    args = parser.parse_args()
    lignes, x, y = charger_dataset(args.dataset)
    print(json.dumps(validation_croisee(lignes, x, y), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
