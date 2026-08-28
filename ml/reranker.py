"""Reranker linéaire léger pour les chunks GraphRAG."""

import json
import math
import re
import unicodedata
from pathlib import Path

import numpy as np


FEATURE_NAMES = [
    "score_semantique",
    "score_lexical_log",
    "score_fusion",
    "recouvrement_question_texte",
    "recouvrement_question_titre",
    "classe_dans_question",
    "signal_semantique_present",
    "signal_lexical_present",
    "rang_reciproque",
    "longueur_texte_log",
]


def normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFKD", texte or "")
    texte = "".join(c for c in texte if not unicodedata.combining(c)).lower()
    return " ".join(re.findall(r"[a-z0-9]+", texte))


def _tokens(texte: str) -> set[str]:
    mots_vides = {
        "a", "au", "aux", "ce", "ces", "dans", "de", "des", "du", "en",
        "est", "et", "la", "le", "les", "ou", "par", "pour", "que", "qui",
        "son", "sur", "un", "une",
    }
    return {
        mot for mot in normaliser(texte).split() if len(mot) >= 2 and mot not in mots_vides
    }


def _recouvrement(question: str, texte: str) -> float:
    question_tokens = _tokens(question)
    if not question_tokens:
        return 0.0
    return len(question_tokens & _tokens(texte)) / len(question_tokens)


def extraire_features(question: str, chunk: dict, rang: int) -> np.ndarray:
    semantique = float(chunk.get("score_semantique") or 0.0)
    lexical = max(0.0, float(chunk.get("score_lexical") or 0.0))
    fusion = float(chunk.get("score_fusion") or 0.0)
    texte = str(chunk.get("texte") or "")
    titre = str(chunk.get("titre") or chunk.get("citation") or "")
    classe = normaliser(str(chunk.get("classe") or ""))
    question_normalisee = normaliser(question)
    classe_dans_question = float(
        bool(classe and re.search(rf"\b{re.escape(classe)}\b", question_normalisee))
    )
    return np.asarray(
        [
            semantique,
            math.log1p(lexical),
            fusion,
            _recouvrement(question, texte),
            _recouvrement(question, titre),
            classe_dans_question,
            float("score_semantique" in chunk),
            float("score_lexical" in chunk),
            1.0 / max(1, rang),
            math.log1p(len(texte)),
        ],
        dtype=float,
    )


class LinearReranker:
    """Régression logistique sérialisée en JSON, sans scikit-learn."""

    def __init__(self, weights, bias, means, scales, metadata=None):
        self.weights = np.asarray(weights, dtype=float)
        self.bias = float(bias)
        self.means = np.asarray(means, dtype=float)
        self.scales = np.asarray(scales, dtype=float)
        self.metadata = metadata or {}
        if len(self.weights) != len(FEATURE_NAMES):
            raise ValueError("Nombre de poids incompatible avec les features du reranker.")

    @classmethod
    def load(cls, path: str | Path):
        donnees = json.loads(Path(path).read_text(encoding="utf-8"))
        if donnees.get("feature_names") != FEATURE_NAMES:
            raise ValueError("Le modèle utilise une version différente des features.")
        return cls(
            donnees["weights"],
            donnees["bias"],
            donnees["means"],
            donnees["scales"],
            donnees.get("metadata"),
        )

    def save(self, path: str | Path):
        chemin = Path(path)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(
            json.dumps(
                {
                    "model_type": "logistic_regression",
                    "feature_names": FEATURE_NAMES,
                    "weights": self.weights.tolist(),
                    "bias": self.bias,
                    "means": self.means.tolist(),
                    "scales": self.scales.tolist(),
                    "metadata": self.metadata,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def predict_proba_features(self, features: np.ndarray) -> float:
        standardisees = (features - self.means) / self.scales
        logit = float(np.clip(standardisees @ self.weights + self.bias, -30, 30))
        return 1.0 / (1.0 + math.exp(-logit))

    def rerank(self, question: str, chunks: list[dict]) -> list[dict]:
        resultat = []
        for rang, chunk in enumerate(chunks, 1):
            copie = dict(chunk)
            features = extraire_features(question, copie, rang)
            copie["score_reranker"] = self.predict_proba_features(features)
            copie["rang_avant_reranking"] = rang
            resultat.append(copie)
        return sorted(
            resultat,
            key=lambda chunk: (
                -chunk["score_reranker"],
                -float(chunk.get("score_fusion") or 0.0),
            ),
        )
