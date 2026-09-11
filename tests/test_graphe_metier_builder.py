import unittest
from pathlib import Path

from arianes.graph.metier_builder import charger_definition
from arianes.paths import METIER_DATA_DIR


class GrapheMetierBuilderTests(unittest.TestCase):
    def test_definition_poste_aiguillage_est_coherente(self):
        chemin = METIER_DATA_DIR / "poste_aiguillage.json"
        definition = charger_definition(chemin)
        ids = {concept["id"] for concept in definition["concepts"]}

        self.assertEqual("poste_aiguillage", definition["racine"])
        self.assertIn("poste_aiguillage", ids)
        self.assertIn("aiguillage", ids)
        self.assertTrue(definition["relations"])
        self.assertTrue(all(relation.get("preuve") for relation in definition["relations"]))


if __name__ == "__main__":
    unittest.main()
