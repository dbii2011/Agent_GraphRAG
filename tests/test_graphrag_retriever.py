import time
import unittest

from graphrag_retriever import GraphRAGRetriever, normaliser


class GraphRAGRetrieverTests(unittest.TestCase):
    def setUp(self):
        self.retriever = GraphRAGRetriever(None, None)
        self.retriever._catalogue = [
            {"nom": "SEL", "description": "", "attributs": []},
            {"nom": "Ligne", "description": "ligne ferroviaire", "attributs": []},
            {"nom": "Zone", "description": "", "attributs": []},
            {"nom": "ZoneDeDetection", "description": "détection ferroviaire", "attributs": []},
            {"nom": "VoieDeLigne", "description": "", "attributs": []},
        ]
        self.retriever._catalogue_charge_a = time.time()

    def test_normalisation_decoupe_camel_case_et_accents(self):
        self.assertEqual("zone de detection", normaliser("ZoneDeDétection"))

    def test_classe_courte_absente_des_sous_chainages(self):
        noms = [c["nom"] for c in self.retriever.resoudre_classes("attributs de la classe Ligne")]
        self.assertEqual("Ligne", noms[0])
        self.assertNotIn("SEL", noms)

    def test_expression_precise_ecarte_la_classe_generique(self):
        noms = [c["nom"] for c in self.retriever.resoudre_classes("fonctionnement de la zone de détection")]
        self.assertEqual("ZoneDeDetection", noms[0])
        self.assertNotIn("Zone", noms)

    def test_modes_de_retrieval(self):
        self.assertEqual("STRUCTURE", self.retriever.determiner_mode("Quels sont ses attributs ?"))
        self.assertEqual("DOCUMENTAIRE", self.retriever.determiner_mode("Comment appliquer cette procédure ?"))
        self.assertEqual("HYBRIDE", self.retriever.determiner_mode("Explique ses attributs et son fonctionnement"))

    def test_selection_concept_metier_poste_aiguillage(self):
        concepts = [
            {
                "id": "poste_aiguillage",
                "nom": "Poste d'aiguillage",
                "aliases": ["poste"],
                "classes_arianes": ["Poste"],
            },
            {
                "id": "zep",
                "nom": "Zone élémentaire de protection",
                "aliases": ["ZEP"],
                "classes_arianes": ["ZEP"],
            },
        ]
        resultat = self.retriever._selectionner_concepts(
            "Comment fonctionne un poste d'aiguillage ?",
            concepts,
            ["Poste"],
        )
        self.assertEqual("poste_aiguillage", resultat[0])
        self.assertNotIn("zep", resultat)


if __name__ == "__main__":
    unittest.main()
