import unittest
from pathlib import Path

from arianes.pipelines.extraction_metier import (
    classes_candidates,
    consolider,
    decouper_document,
    extraire_document,
    filtrer_valides,
    marquer_valide,
    valider_extraction,
)
from arianes.paths import PROCEDURES_DIR
from arianes.pipelines.extraction_globale import decouvrir_documents, chemin_resultat


class FauxMessage:
    def __init__(self, content):
        self.content = content


class FauxLLM:
    def invoke(self, _prompt):
        return FauxMessage(
            """{
              "domaine": "Signalisation",
              "concepts": [
                {"id_local": "poste", "nom": "Poste", "aliases": [],
                 "description": "Poste ferroviaire", "classes_arianes": ["Poste"]},
                {"id_local": "type_poste", "nom": "Type de poste", "aliases": [],
                 "description": "Technologie du poste",
                 "classes_arianes": ["TypeModeFonctionnementPoste"]}
              ],
              "relations": [
                {"source": "poste", "type": "A_POUR_TECHNOLOGIE", "cible": "type_poste",
                 "citation_exacte": "Pour les postes d’aiguillages, le typage est affiné selon leurs technologies"}
              ]
            }"""
        )


class PipelineGrapheMetierTests(unittest.TestCase):
    def test_classes_candidates_retrouve_poste(self):
        catalogue = {
            "Poste": {"nom": "Poste", "description": "", "attributs": set()},
            "Ligne": {"nom": "Ligne", "description": "", "attributs": set()},
        }
        resultat = classes_candidates("Un itinéraire est rattaché au poste", catalogue)
        self.assertEqual("Poste", resultat[0]["nom"])

    def test_decoupage_conserve_les_lignes(self):
        chemin = PROCEDURES_DIR / "Post.txt"
        morceaux = decouper_document(chemin, taille_max=1000)
        self.assertEqual(1, morceaux[0]["debut"])
        self.assertEqual(
            len(chemin.read_text(encoding="utf-8").splitlines()),
            morceaux[-1]["fin"],
        )

    def test_relation_sans_preuve_exacte_est_rejetee(self):
        extraction = {
            "domaine": "Signalisation",
            "concepts": [
                {"id_local": "poste", "nom": "Poste", "classes_arianes": ["Poste"]},
                {"id_local": "aiguillage", "nom": "Aiguillage", "classes_arianes": ["Aiguillage"]},
            ],
            "relations": [
                {
                    "source": "poste",
                    "type": "COMMANDE",
                    "cible": "aiguillage",
                    "citation_exacte": "phrase inventée absente du document",
                }
            ],
        }
        resultat = valider_extraction(
            extraction,
            Path("Post.txt"),
            {"debut": 1, "fin": 2, "texte": "Le poste est décrit dans GAIA."},
            {"Poste", "Aiguillage"},
        )
        self.assertEqual([], resultat["relations"])
        self.assertTrue(resultat["erreurs_validation"])

    def test_relation_sourcee_devient_valide_documentairement(self):
        citation = "Le poste commande les aiguilles de la zone concernée."
        extraction = {
            "domaine": "Signalisation",
            "concepts": [
                {"id_local": "poste", "nom": "Poste", "classes_arianes": ["Poste"]},
                {"id_local": "aiguillage", "nom": "Aiguillage", "classes_arianes": ["Aiguillage"]},
            ],
            "relations": [
                {
                    "source": "poste",
                    "type": "COMMANDE",
                    "cible": "aiguillage",
                    "citation_exacte": citation,
                }
            ],
        }
        resultat = valider_extraction(
            extraction,
            Path("Post.txt"),
            {"debut": 10, "fin": 12, "texte": citation},
            {"Poste", "Aiguillage"},
        )
        self.assertEqual(1, len(resultat["relations"]))
        # Citation présente, mais « aiguilles » ne confirme pas à elle seule
        # le concept « Aiguillage » ni le sens du triplet : conserver sans certifier.
        self.assertEqual("PROBABLE", resultat["relations"][0]["statut"])
        self.assertFalse(resultat["relations"][0]["validation_experte"])

    def test_est_un_sans_predicat_taxonomique_reste_a_revoir(self):
        extraction = {
            "domaine": "Infrastructure",
            "concepts": [
                {"id_local": "acces", "nom": "Accès", "classes_arianes": ["Acces"]},
                {"id_local": "localisation", "nom": "Localisation", "classes_arianes": []},
            ],
            "relations": [
                {
                    "source": "acces",
                    "type": "EST_UN",
                    "cible": "localisation",
                    "citation_exacte": "La localisation de l’accès est obligatoire.",
                }
            ],
        }
        resultat = valider_extraction(
            extraction,
            Path("Acces.txt"),
            {"debut": 1, "fin": 2, "texte": "La localisation de l’accès est obligatoire."},
            {"Acces"},
        )
        self.assertEqual(1, len(resultat["relations"]))
        self.assertIn(
            "prédicat non confirmé textuellement",
            resultat["relations"][0]["avertissements"],
        )

    def test_formulation_passive_conserve_la_direction_et_change_le_type(self):
        citation = "L’entrée de chaque canton est normalement commandée par un signal."
        extraction = {
            "domaine": "Signalisation",
            "concepts": [
                {"id_local": "canton", "nom": "Canton", "classes_arianes": ["Canton"]},
                {"id_local": "signal", "nom": "Signal", "classes_arianes": ["Signal"]},
            ],
            "relations": [
                {
                    "source": "canton",
                    "type": "COMMANDE",
                    "cible": "signal",
                    "citation_exacte": citation,
                }
            ],
        }
        resultat = valider_extraction(
            extraction,
            Path("Canton.txt"),
            {"debut": 1, "fin": 1, "texte": citation},
            {"Canton", "Signal"},
        )
        relation = resultat["relations"][0]
        self.assertEqual("canton", relation["source"])
        self.assertEqual("signal", relation["cible"])
        self.assertEqual("EST_COMMANDE_PAR", relation["type"])

    def test_import_filtre_tout_ce_qui_n_est_pas_valide(self):
        definition = consolider(
            [
                {
                    "domaine": "Signalisation",
                    "concepts": [
                        {
                            "id": "poste",
                            "nom": "Poste",
                            "aliases": [],
                            "description": "",
                            "classes_arianes": ["Poste"],
                            "documents": ["Post.txt"],
                            "statut": "A_REVOIR",
                        }
                    ],
                    "relations": [],
                    "erreurs_validation": [],
                }
            ]
        )
        self.assertEqual([], filtrer_valides(definition)["concepts"])
        marquer_valide(definition)
        self.assertEqual(1, len(filtrer_valides(definition)["concepts"]))

    def test_extraction_document_ne_modifie_pas_neo4j(self):
        document = PROCEDURES_DIR / "Post.txt"
        catalogue = {
            "Poste": {"nom": "Poste", "description": "", "attributs": set()},
            "TypeModeFonctionnementPoste": {
                "nom": "TypeModeFonctionnementPoste",
                "description": "",
                "attributs": set(),
            },
        }
        resultat = extraire_document(
            FauxLLM(), document, catalogue, taille_chunk=100_000
        )
        self.assertEqual("Post.txt", resultat["document_source"])
        self.assertEqual(2, len(resultat["concepts"]))
        self.assertEqual(1, len(resultat["relations"]))

    def test_script_global_decouvre_uniquement_les_fiches_txt(self):
        dossier = PROCEDURES_DIR
        documents = decouvrir_documents(dossier)
        self.assertTrue(documents)
        self.assertTrue(all(document.suffix.lower() == ".txt" for document in documents))
        sortie = chemin_resultat(Path("sortie"), documents[0])
        self.assertTrue(sortie.name.endswith(".metier.json"))


if __name__ == "__main__":
    unittest.main()
