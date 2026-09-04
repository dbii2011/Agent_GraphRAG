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
        self.assertEqual(
            "CHEMIN_METIER",
            self.retriever.determiner_mode("Quel chemin relie une ZEP à un poste ?"),
        )
        self.assertEqual(
            "CHEMIN_METIER",
            self.retriever.determiner_mode("Existe-t-il une relation indirecte entre le signal et la ligne ?"),
        )

    def test_question_autonome_ne_reutilise_pas_le_contexte_precedent(self):
        self.assertFalse(self.retriever._necessite_contexte("À quoi un poste est-il rattaché ?"))
        self.assertFalse(self.retriever._necessite_contexte("Existe-t-il un chemin entre un signal et une ligne ?"))

    def test_relance_referentielle_reutilise_le_contexte(self):
        self.assertTrue(self.retriever._necessite_contexte("Et quelles sont ses relations ?"))
        self.assertTrue(self.retriever._necessite_contexte("Quel est son fonctionnement ?"))

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

    def test_selection_concept_metier_tolere_post_sans_e(self):
        concepts = [
            {
                "id": "poste_aiguillage",
                "nom": "Poste d'aiguillage",
                "aliases": ["poste"],
                "classes_arianes": ["Poste"],
            },
            {
                "id": "poste_pai",
                "nom": "Poste de VP électrique à enclenchement informatique",
                "aliases": ["PAI"],
                "classes_arianes": [],
            },
        ]
        resultat = self.retriever._selectionner_concepts(
            "Donne-moi le sous-graphe métier d'un post",
            concepts,
            [],
        )
        self.assertEqual(["poste_aiguillage"], resultat)

    def test_selection_extremites_chemin_evite_deux_variantes_du_poste(self):
        concepts = [
            {"id": "poste", "nom": "Poste", "aliases": [], "classes_arianes": ["Poste"]},
            {"id": "poste_aiguillage", "nom": "Poste d'aiguillage", "aliases": ["poste"], "classes_arianes": ["Poste"]},
            {"id": "zone_de_detection", "nom": "Zone de détection", "aliases": [], "classes_arianes": []},
        ]
        resultat = self.retriever._selectionner_extremites_chemin(
            "Quel chemin relie une zone de détection à un poste ?", concepts, []
        )
        self.assertEqual(["zone_de_detection", "poste"], resultat)

    def test_selection_extremites_prefere_le_nom_compose_explicite(self):
        concepts = [
            {"id": "poste", "nom": "Poste", "aliases": [], "classes_arianes": ["Poste"]},
            {"id": "poste_aiguillage", "nom": "Poste d'aiguillage", "aliases": ["poste"], "classes_arianes": ["Poste"]},
            {"id": "signal", "nom": "Signal", "aliases": [], "classes_arianes": ["Signal"]},
        ]
        resultat = self.retriever._selectionner_extremites_chemin(
            "Relie le signal au poste d'aiguillage", concepts, []
        )
        self.assertEqual(["signal", "poste_aiguillage"], resultat)


if __name__ == "__main__":
    unittest.main()
