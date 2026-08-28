"""Entraîne le reranker linéaire à partir d'un fichier JSONL annoté."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.reranker import FEATURE_NAMES, LinearReranker


def charger_dataset(path: Path):
    lignes = [
        json.loads(ligne)
        for ligne in path.read_text(encoding="utf-8").splitlines()
        if ligne.strip()
    ]
    if not lignes:
        raise ValueError("Le dataset est vide.")
    x = np.asarray([ligne["features"] for ligne in lignes], dtype=float)
    y = np.asarray([ligne["label"] for ligne in lignes], dtype=float)
    if x.ndim != 2 or x.shape[1] != len(FEATURE_NAMES):
        raise ValueError("Dimensions de features incompatibles.")
    if set(np.unique(y)) != {0.0, 1.0}:
        raise ValueError("Le dataset doit contenir des labels 0 et 1.")
    return lignes, x, y


def entrainer(x, y, epochs=1500, learning_rate=0.03, l2=0.01):
    means = x.mean(axis=0)
    scales = x.std(axis=0)
    scales[scales < 1e-9] = 1.0
    z = (x - means) / scales
    weights = np.zeros(z.shape[1], dtype=float)
    bias = 0.0
    positifs = max(1.0, y.sum())
    negatifs = max(1.0, len(y) - y.sum())
    poids_exemples = np.where(y == 1, len(y) / (2 * positifs), len(y) / (2 * negatifs))
    for _ in range(epochs):
        logits = np.clip(z @ weights + bias, -30, 30)
        predictions = 1.0 / (1.0 + np.exp(-logits))
        erreurs = (predictions - y) * poids_exemples
        weights -= learning_rate * ((z.T @ erreurs) / len(y) + l2 * weights)
        bias -= learning_rate * float(erreurs.mean())
    return weights, bias, means, scales


def metriques(model, x, y):
    scores = np.asarray([model.predict_proba_features(row) for row in x])
    predictions = (scores >= 0.5).astype(float)
    accuracy = float((predictions == y).mean())
    tp = float(((predictions == 1) & (y == 1)).sum())
    fp = float(((predictions == 1) & (y == 0)).sum())
    fn = float(((predictions == 0) & (y == 1)).sum())
    precision = tp / max(1.0, tp + fp)
    recall = tp / max(1.0, tp + fn)
    return {"accuracy": accuracy, "precision": precision, "recall": recall}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, default=Path("ml/models/reranker.json"))
    parser.add_argument("--epochs", type=int, default=1500)
    parser.add_argument("--learning-rate", type=float, default=0.03)
    args = parser.parse_args()
    lignes, x, y = charger_dataset(args.dataset)
    weights, bias, means, scales = entrainer(
        x, y, epochs=args.epochs, learning_rate=args.learning_rate
    )
    model = LinearReranker(
        weights,
        bias,
        means,
        scales,
        metadata={
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "examples": len(lignes),
            "positives": int(y.sum()),
            "prototype": True,
        },
    )
    model.metadata["training_metrics"] = metriques(model, x, y)
    model.save(args.output)
    print(json.dumps(model.metadata, ensure_ascii=False, indent=2))
    print(f"Modèle enregistré : {args.output}")


if __name__ == "__main__":
    main()
