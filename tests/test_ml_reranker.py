import unittest

import numpy as np

from ml.build_dataset_from_evaluation import construire
from ml.reranker import FEATURE_NAMES, LinearReranker, extraire_features
from ml.train_reranker import entrainer


class RerankerMLTests(unittest.TestCase):
    def test_features_ont_la_dimension_attendue(self):
        features = extraire_features(
            "procédure courant de Foucault",
            {
                "texte": "Utilisation du frein à courant de Foucault",
                "titre": "CourantDeFoucault.txt",
                "classe": "Ligne",
                "score_semantique": 0.91,
                "score_lexical": 4.2,
                "score_fusion": 0.03,
            },
            1,
        )
        self.assertEqual(len(FEATURE_NAMES), len(features))
        self.assertTrue(np.isfinite(features).all())

    def test_modele_apprend_un_signal_separable_et_rerank(self):
        x = np.zeros((8, len(FEATURE_NAMES)))
        x[:4, 0] = [0.95, 0.92, 0.90, 0.88]
        x[4:, 0] = [0.20, 0.25, 0.30, 0.35]
        y = np.asarray([1, 1, 1, 1, 0, 0, 0, 0], dtype=float)
        weights, bias, means, scales = entrainer(x, y, epochs=800)
        modele = LinearReranker(weights, bias, means, scales)
        self.assertGreater(
            modele.predict_proba_features(x[0]),
            modele.predict_proba_features(x[-1]),
        )

        chunks = [
            {"chunk_id": "faible", "score_semantique": 0.25, "score_fusion": 0.03},
            {"chunk_id": "fort", "score_semantique": 0.94, "score_fusion": 0.02},
        ]
        reranked = modele.rerank("question", chunks)
        self.assertEqual("fort", reranked[0]["chunk_id"])
        self.assertIn("score_reranker", reranked[0])

    def test_dataset_faible_supervision_annote_la_source_attendue(self):
        rapport = {
            "cas": [
                {
                    "numero": 1,
                    "question": "Question",
                    "attendus": {"source": "Bon.txt"},
                    "retrieval": {
                        "scores_chunks": [
                            {"citation": "docs\\Bon.txt — passage 1", "semantique": 0.9},
                            {"citation": "docs\\Autre.txt — passage 1", "semantique": 0.8},
                        ]
                    },
                }
            ]
        }
        exemples = construire(rapport)
        self.assertEqual([1, 0], [exemple["label"] for exemple in exemples])


if __name__ == "__main__":
    unittest.main()
