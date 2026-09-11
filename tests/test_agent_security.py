import unittest
from unittest.mock import patch

import httpx

from arianes.agent import AgentLG


class FakeResult:
    def __iter__(self):
        return iter([])


class FakeSession:
    def __init__(self):
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, query):
        self.queries.append(query)
        return FakeResult()


class FakeDriver:
    def __init__(self):
        self.fake_session = FakeSession()

    def session(self):
        return self.fake_session


class FakeMessage:
    content = "réponse"
    tool_calls = []


class FakeLLM:
    def __init__(self):
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return FakeMessage()


class FakeRetriever:
    def __init__(self):
        self.history = None

    def retrieve(self, question, historique=None):
        self.history = historique
        return {
            "mode": "DOCUMENTAIRE",
            "classes_racines": ["Ligne"],
            "sous_graphe": {"classes": [{"nom": "Ligne"}]},
            "chunks": [],
            "citations": [],
        }

    @staticmethod
    def contexte_pour_llm(resultat):
        return "contexte contrôlé"


class CypherSecurityTests(unittest.TestCase):
    def setUp(self):
        self.agent = AgentLG.__new__(AgentLG)
        self.agent.driver = FakeDriver()

    def test_match_read_is_accepted(self):
        result = self.agent._valider_et_executer("MATCH (n) RETURN n LIMIT 1")
        self.assertIn("aucun résultat", result)
        self.assertEqual(1, len(self.agent.driver.fake_session.queries))

    def test_write_keyword_is_rejected(self):
        result = self.agent._valider_et_executer("MATCH (n) DELETE n")
        self.assertIn("seule la lecture", result)
        self.assertEqual([], self.agent.driver.fake_session.queries)

    def test_unapproved_start_is_rejected(self):
        result = self.agent._valider_et_executer("SHOW DATABASES")
        self.assertIn("doit commencer", result)
        self.assertEqual([], self.agent.driver.fake_session.queries)

    def test_load_csv_is_rejected(self):
        result = self.agent._valider_et_executer("UNWIND [1] AS x LOAD CSV FROM 'x' AS row RETURN row")
        self.assertIn("seule la lecture", result)

    def test_ask_passes_recent_history_to_executor(self):
        self.agent.llm = FakeLLM()
        self.agent.retriever = FakeRetriever()
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": str(i)}
            for i in range(14)
        ]

        result = self.agent.ask("question suivante", historique=history)

        messages = self.agent.llm.messages
        self.assertEqual("réponse", result)
        self.assertEqual(history, self.agent.retriever.history)
        self.assertEqual(10, len(messages))
        self.assertEqual("6", messages[1]["content"])
        self.assertIn("question suivante", messages[-1]["content"])

    def test_ask_impose_une_reponse_directe_et_ciblee(self):
        self.agent.llm = FakeLLM()
        self.agent.retriever = FakeRetriever()

        self.agent.ask("Donne le sous-graphe métier du poste")

        consigne = self.agent.llm.messages[0]["content"]
        self.assertIn("première phrase", consigne)
        self.assertIn("question ciblée en rapport général", consigne)
        self.assertIn("Adapte le niveau de détail", consigne)
        self.assertIn("trois à six paragraphes", consigne)
        self.assertIn("N'utilise aucun tableau Markdown", consigne)
        self.assertIn("N'affiche aucune citation", consigne)
        self.assertIn("Ignore les chunks non utilisés", consigne)

    def test_graphe_metier_transmet_uniquement_ses_preuves_documentaires(self):
        self.agent.llm = FakeLLM()
        self.agent.retriever = FakeRetriever()
        self.agent.retriever.retrieve = lambda question, historique=None: {
            "mode": "METIER",
            "classes_racines": ["Poste"],
            "sous_graphe": {"classes": []},
            "graphe_metier": {
                "concepts": [{"id": "poste", "nom": "Poste"}],
                "relations": [
                    {"source": "signal", "type": "EST_COMMANDE_PAR", "cible": "poste"}
                ],
            },
            "chunks": [
                {
                    "chunk_id": "preuve-1",
                    "texte": "Le poste comporte la manoeuvre des signaux.",
                    "origine_retrieval": "preuve_graphe_metier",
                },
                {
                    "chunk_id": "hors-sujet",
                    "texte": "Ce passage ne doit pas être transmis.",
                    "origine_retrieval": "recherche_semantique",
                },
            ],
            "citations": [],
        }

        self.agent.ask("Décris le graphe métier du poste")

        contexte = self.agent.llm.messages[-1]["content"]
        consigne = self.agent.llm.messages[0]["content"]
        self.assertIn("Le poste comporte la manoeuvre des signaux.", contexte)
        self.assertNotIn("Ce passage ne doit pas être transmis.", contexte)
        self.assertIn("complément visuel", consigne)
        self.assertIn("phrase complète", consigne)

    def test_ask_n_ajoute_pas_toutes_les_citations_du_retrieval(self):
        self.agent.llm = FakeLLM()
        self.agent.retriever = FakeRetriever()
        self.agent.retriever.retrieve = lambda question, historique=None: {
            "mode": "DOCUMENTAIRE",
            "classes_racines": [],
            "sous_graphe": {"classes": []},
            "chunks": [],
            "citations": ["source sans rapport"],
        }

        resultat = self.agent.ask("question")

        self.assertEqual("réponse", resultat)

    def test_ask_fait_reformuler_le_chemin_controle_par_le_llm(self):
        self.agent.llm = FakeLLM()
        self.agent.retriever = FakeRetriever()
        self.agent.retriever.retrieve = lambda question, historique=None: {
            "mode": "CHEMIN_METIER",
            "chemin_metier": {
                "trouve": True,
                "depart": "signal",
                "arrivee": "ligne",
                "concepts": [
                    {"id": "signal", "nom": "Signal"},
                    {"id": "poste", "nom": "Poste"},
                    {"id": "ligne", "nom": "Ligne"},
                ],
                "relations": [
                    {"source": "signal", "type": "EST_COMMANDE_PAR", "cible": "poste"},
                    {"source": "poste", "type": "LOCALISE_SUR", "cible": "ligne"},
                ],
            },
        }

        resultat = self.agent.ask("Quel chemin relie un signal à une ligne ?")

        self.assertEqual("réponse", resultat)
        self.assertIn("EST_COMMANDE_PAR", self.agent.llm.messages[-1]["content"])
        consigne = self.agent.llm.messages[0]["content"]
        self.assertIn("français naturel", consigne)
        self.assertIn("N'ajoute, ne supprime", consigne)

    def test_schema_reponse_conserve_l_ordre_du_chemin(self):
        schema = AgentLG._schema_depuis_retrieval({
            "chemin_metier": {
                "trouve": True,
                "concepts": [
                    {"id": "signal", "nom": "Signal"},
                    {"id": "poste", "nom": "Poste"},
                    {"id": "ligne", "nom": "Ligne"},
                ],
                "relations": [
                    {"source": "signal", "type": "EST_COMMANDE_PAR", "cible": "poste"},
                    {"source": "poste", "type": "LOCALISE_SUR", "cible": "ligne"},
                ],
            },
            "graphe_metier": {},
        })

        self.assertEqual(["signal", "poste", "ligne"], [n["id"] for n in schema["nodes"]])
        self.assertEqual(2, len(schema["links"]))

    def test_reponse_de_secours_pour_equipements_commandes(self):
        reponse = AgentLG._formater_relations_secours(
            "Quels équipements sont commandés par un poste d’aiguillage ?",
            {
                "concepts": [
                    {"id": "signal", "nom": "Signal"},
                    {"id": "poste", "nom": "Poste d’aiguillage"},
                ],
                "relations": [
                    {"source": "signal", "type": "EST_COMMANDE_PAR", "cible": "poste"},
                ],
            },
        )

        self.assertEqual(
            "Selon les relations validées du graphe, l’équipement commandé est **Signal**.",
            reponse,
        )

    def test_reponse_structurelle_types_de_noeud(self):
        reponse = AgentLG._formater_structure_secours(
            "Quels sont les différents types de nœud ?",
            {
                "relations": [
                    {"source": "NoeudDeLigne", "type": "HERITE_DE", "cible": "Noeud"},
                    {"source": "NoeudDeVoie", "type": "HERITE_DE", "cible": "Noeud"},
                    {"source": "Noeud", "type": "ASSOCIE_A", "cible": "Ligne"},
                ]
            },
            ["Noeud"],
        )

        self.assertIn("NoeudDeLigne", reponse)
        self.assertIn("NoeudDeVoie", reponse)
        self.assertIn("métamodèle UML", reponse)

    def test_reponse_structurelle_combine_attributs_relations_et_parents(self):
        reponse = AgentLG._formater_structure_uml(
            "Quels sont les attributs, les relations directes et les classes parentes "
            "de la classe Ligne dans le métamodèle UML Arianes ?",
            {
                "attributs": [
                    {"classe": "Ligne", "attribut": "code", "type": "P-String"},
                ],
                "relations": [
                    {
                        "source": "Ligne",
                        "type": "ASSOCIE_A",
                        "cible": "TypeLigne",
                        "proprietes": {"role": "typeLigne"},
                    },
                    {
                        "source": "Ligne",
                        "type": "HERITE_DE",
                        "cible": "RessourceParcoursTopologique",
                    },
                ],
                "classes": [{"nom": "Ligne"}],
            },
            ["Ligne"],
        )

        self.assertIn("Attributs directs (1)", reponse)
        self.assertIn("**code**", reponse)
        self.assertIn("Relations UML directes hors héritage (1)", reponse)
        self.assertIn("`ASSOCIE_A`", reponse)
        self.assertIn("Classes parentes", reponse)
        self.assertIn("RessourceParcoursTopologique", reponse)

    def test_selection_llm_chemin_uml_reste_parmi_les_candidats(self):
        self.agent._generer = lambda provider, messages: "CHEMIN_2"
        chemin = {
            "trouve": True,
            "depart": "A",
            "arrivee": "C",
            "candidats": [
                {
                    "id": "CHEMIN_1", "score": 4.0, "longueur": 2,
                    "classes": [{"nom": "A"}, {"nom": "B"}, {"nom": "C"}],
                    "relations": [
                        {"parcours_source": "A", "type": "HERITE_DE", "parcours_cible": "B"},
                        {"parcours_source": "B", "type": "ASSOCIE_A", "parcours_cible": "C"},
                    ],
                },
                {
                    "id": "CHEMIN_2", "score": 3.0, "longueur": 1,
                    "classes": [{"nom": "A"}, {"nom": "C"}],
                    "relations": [
                        {"parcours_source": "A", "type": "ASSOCIE_A", "parcours_cible": "C"},
                    ],
                },
            ],
        }

        resultat = self.agent._selectionner_chemin_uml_avec_llm(
            "Comment A est relié à C ?", chemin, "mistral"
        )

        self.assertEqual("CHEMIN_2", resultat["selection"])
        self.assertEqual("llm_controle", resultat["methode_selection"])
        self.assertEqual("ASSOCIE_A", resultat["relations"][0]["type"])

    def test_selection_llm_chemin_uml_invente_est_rejetee(self):
        self.agent._generer = lambda provider, messages: "CHEMIN_99"
        chemin = {
            "trouve": True,
            "candidats": [
                {
                    "id": "CHEMIN_1", "score": 1.0, "longueur": 1,
                    "classes": [{"nom": "A"}, {"nom": "B"}],
                    "relations": [],
                },
                {
                    "id": "CHEMIN_2", "score": 2.0, "longueur": 2,
                    "classes": [{"nom": "A"}, {"nom": "C"}],
                    "relations": [],
                },
            ],
        }

        with self.assertRaises(RuntimeError):
            self.agent._selectionner_chemin_uml_avec_llm(
                "Comment A est relié à B ?", chemin, "mistral"
            )

    def test_formatage_chemin_uml_conserve_orientation_inverse(self):
        reponse = AgentLG._formater_chemin_uml({
            "trouve": True,
            "depart": "HabillageOriente",
            "arrivee": "Ligne",
            "relations": [
                {
                    "source": "HabillageParcours",
                    "type": "HERITE_DE",
                    "cible": "HabillageOriente",
                    "parcours_source": "HabillageOriente",
                    "parcours_cible": "HabillageParcours",
                    "sens_parcours": "INVERSE",
                },
                {
                    "source": "HabillageParcours",
                    "type": "ASSOCIE_A",
                    "cible": "RessourceParcoursTopologique",
                    "parcours_source": "HabillageParcours",
                    "parcours_cible": "RessourceParcoursTopologique",
                    "sens_parcours": "DIRECT",
                },
            ],
        })

        self.assertIn("HabillageOriente** ← `HERITE_DE` — **HabillageParcours", reponse)
        self.assertIn("HabillageParcours** — `ASSOCIE_A` → **RessourceParcoursTopologique", reponse)

    def test_retirer_sources_visibles(self):
        reponse = (
            "Le signal est commandé par le poste. "
            "[Source : docs\\Post.txt — passage 1]\n\n"
            "### Sources finales utilisées\n"
            "- docs\\Post.txt — passage 1"
        )

        resultat = AgentLG._retirer_sources_visibles(reponse)

        self.assertEqual("Le signal est commandé par le poste.", resultat)

    def test_ask_ne_bascule_pas_sur_un_autre_fournisseur_en_cas_de_429(self):
        class LLM429:
            def invoke(self, messages):
                requete = httpx.Request("POST", "https://api.mistral.ai/v1/chat/completions")
                reponse = httpx.Response(429, request=requete)
                raise httpx.HTTPStatusError("quota dépassé", request=requete, response=reponse)

        self.agent.llm = LLM429()
        self.agent.retriever = FakeRetriever()

        with patch.object(self.agent, "_invoquer_groq") as groq, \
             patch.object(self.agent, "_invoquer_ollama") as local:
            resultat = self.agent.ask("Quels sont les types de Ligne ?")

        self.assertIn("fournisseur mistral", resultat)
        groq.assert_not_called()
        local.assert_not_called()

    def test_structure_sans_enfant_reste_uml(self):
        sous_graphe = {
            "relations": [
                {"source": "NoeudDeLigne", "type": "HERITE_DE", "cible": "Noeud"},
                {"source": "NoeudDeLigne", "type": "ASSOCIE_A", "cible": "TypeNoeudDeLigne"},
            ]
        }

        reponse = AgentLG._formater_structure_secours(
            "Quels sont les types de Nœud De Ligne dans le UML ?",
            sous_graphe,
            ["NoeudDeLigne"],
        )

        self.assertIn("aucune classe", reponse)
        self.assertIn("TypeNoeudDeLigne", reponse)
        self.assertIn("association UML", reponse)

    def test_compaction_groq_conserve_question_et_fin_des_chunks(self):
        messages = [
            {"role": "system", "content": "S" * 6000},
            {"role": "user", "content": "ancien " * 1000},
            {"role": "assistant", "content": "réponse " * 1000},
            {"role": "user", "content": "Question : KVB\n" + "X" * 15000 + "PREUVE_KVB"},
        ]

        resultat = AgentLG._compacter_messages_groq(messages)

        self.assertLessEqual(sum(len(m["content"]) for m in resultat), 18500)
        self.assertTrue(resultat[-1]["content"].startswith("Question : KVB"))
        self.assertTrue(resultat[-1]["content"].endswith("PREUVE_KVB"))

    def test_invoquer_groq_utilise_le_contexte_et_le_modele_configure(self):
        reponse = unittest.mock.Mock()
        reponse.json.return_value = {
            "choices": [{"message": {"content": "Réponse Groq contrôlée."}}]
        }
        with (
            patch("arianes.agent.GROQ_API_KEY", "cle-test"),
            patch("arianes.agent.httpx.post", return_value=reponse) as post,
        ):
            resultat = self.agent._invoquer_groq([
                {"role": "user", "content": "Contexte GraphRAG"}
            ])

        self.assertEqual("Réponse Groq contrôlée.", resultat)
        reponse.raise_for_status.assert_called_once()
        parametres = post.call_args.kwargs
        self.assertEqual("openai/gpt-oss-20b", parametres["json"]["model"])
        self.assertIn("Contexte GraphRAG", parametres["json"]["messages"][0]["content"])

    def test_invoquer_gemini_convertit_les_roles(self):
        reponse = unittest.mock.Mock()
        reponse.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Réponse Gemini."}]}}]
        }
        with (
            patch("arianes.agent.GEMINI_API_KEY", "cle-test"),
            patch("arianes.agent.httpx.post", return_value=reponse) as post,
        ):
            resultat = self.agent._invoquer_gemini([
                {"role": "system", "content": "Consigne"},
                {"role": "user", "content": "Question"},
                {"role": "assistant", "content": "Ancienne réponse"},
            ])

        self.assertEqual("Réponse Gemini.", resultat)
        charge = post.call_args.kwargs["json"]
        self.assertEqual("Consigne", charge["system_instruction"]["parts"][0]["text"])
        self.assertEqual(["user", "model"], [m["role"] for m in charge["contents"]])
        self.assertEqual("cle-test", post.call_args.kwargs["headers"]["x-goog-api-key"])


if __name__ == "__main__":
    unittest.main()
