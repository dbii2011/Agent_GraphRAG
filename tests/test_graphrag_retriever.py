import time
import unittest

from arianes.retrieval import GraphRAGRetriever, normaliser


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

    def test_normalisation_conserve_la_ligature_oe(self):
        self.assertEqual("noeud de ligne", normaliser("NœudDeLigne"))

    def test_nom_compose_avec_ligature_est_resolu_exactement(self):
        self.retriever._catalogue.append(
            {"nom": "NoeudDeLigne", "description": "", "attributs": []}
        )
        noms = [
            c["nom"] for c in self.retriever.resoudre_classes(
                "Quels sont les types de NœudDeLigne dans le modèle UML ?"
            )
        ]
        self.assertEqual("NoeudDeLigne", noms[0])
        self.assertNotIn("Ligne", noms)

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
            "STRUCTURE",
            self.retriever.determiner_mode("Quels sont ses types dans le UML ?"),
        )
        self.assertEqual(
            "CHEMIN_METIER",
            self.retriever.determiner_mode("Quel chemin relie une ZEP à un poste ?"),
        )
        self.assertEqual(
            "CHEMIN_METIER",
            self.retriever.determiner_mode("Existe-t-il une relation indirecte entre le signal et la ligne ?"),
        )
        self.assertEqual(
            "CHEMIN_UML",
            self.retriever.determiner_mode("Établis un chemin UML entre Habillage et Ligne"),
        )

    def test_routage_separe_les_sources(self):
        cas = [
            ("Quels sont les attributs de Ligne dans le UML ?", "STRUCTURE", True, False, False),
            ("Comment construire un itinéraire ?", "DOCUMENTAIRE", False, True, False),
            ("À quoi un poste est-il rattaché ?", "METIER", False, False, True),
            ("Quel chemin relie Signal et Ligne ?", "CHEMIN_METIER", False, False, True),
            ("Quel chemin UML relie Habillage et Ligne ?", "CHEMIN_UML", True, False, False),
            ("Explique Appareil de voie et ses relations directes", "HYBRIDE", False, True, True),
            ("Explique les attributs et le fonctionnement de Ligne", "HYBRIDE", True, True, False),
            ("Quels équipements sont commandés par un poste ?", "METIER", False, False, True),
            ("Compare la classe UML Poste avec son fonctionnement documentaire", "HYBRIDE", True, True, False),
            ("Explique la classe Poste, ses relations UML et ses relations métier", "HYBRIDE", True, True, True),
        ]
        for question, mode, uml, documents, metier in cas:
            with self.subTest(question=question):
                resultat = self.retriever.analyser_question(question)
                self.assertEqual(mode, resultat["mode"])
                self.assertEqual(uml, resultat["sources"]["uml"])
                self.assertEqual(documents, resultat["sources"]["documents"])
                self.assertEqual(metier, resultat["sources"]["metier"])

    def test_formulations_naturelles_sur_les_classes_restent_structurelles(self):
        questions = [
            "Qu’est-ce que la classe Ligne ?",
            "Quelles sont les relations directes de la classe Ligne ?",
            "À quelles classes Ligne est-elle associée ?",
            "Quelles classes composent une Ligne ?",
            "Quelles classes héritent de RessourceParcoursTopologique ?",
        ]
        for question in questions:
            with self.subTest(question=question):
                resultat = self.retriever.analyser_question(question)
                self.assertEqual("STRUCTURE", resultat["mode"])
                self.assertTrue(resultat["sources"]["uml"])
                self.assertFalse(resultat["sources"]["documents"])
                self.assertFalse(resultat["sources"]["metier"])

    def test_sous_graphe_uml_deux_niveaux_n_est_pas_un_chemin(self):
        analyse = self.retriever.analyser_question(
            "À partir de la classe Ligne, construis le sous-graphe UML sur deux niveaux : "
            "présente sa classe parente, ses attributs, ses associations et compositions "
            "directes, puis les classes reliées à ses voisins au deuxième niveau."
        )

        self.assertEqual("STRUCTURE", analyse["mode"])
        self.assertTrue(analyse["sources"]["uml"])
        self.assertFalse(analyse["sources"]["documents"])
        self.assertFalse(analyse["sources"]["metier"])

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

    def test_chemin_uml_ambigu_propose_des_classes_sans_en_inventer_une(self):
        self.retriever._catalogue.extend([
            {"nom": "HabillageParcours", "description": "", "attributs": []},
            {"nom": "HabillageValeur", "description": "", "attributs": []},
        ])
        resultat = self.retriever._construire_chemin_uml(
            ["Ligne"],
            "Établis un chemin UML de la classe Habillage vers la classe Ligne",
        )
        self.assertFalse(resultat["trouve"])
        self.assertIn("HabillageParcours", resultat["classes_suggerees"])
        self.assertIn("HabillageValeur", resultat["classes_suggerees"])


if __name__ == "__main__":
    unittest.main()
