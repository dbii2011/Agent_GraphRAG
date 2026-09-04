import unittest

from Agent_LG import AgentLG


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
            "mode": "STRUCTURE",
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
        self.assertIn("ne transforme pas une question ciblée en rapport général", consigne)
        self.assertIn("N'ajoute ni définition, ni attributs", consigne)
        self.assertIn("N'utilise aucun tableau Markdown", consigne)
        self.assertIn("N'affiche aucune citation", consigne)
        self.assertIn("Ignore les chunks non utilisés", consigne)

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

    def test_retirer_sources_visibles(self):
        reponse = (
            "Le signal est commandé par le poste. "
            "[Source : docs\\Post.txt — passage 1]\n\n"
            "### Sources finales utilisées\n"
            "- docs\\Post.txt — passage 1"
        )

        resultat = AgentLG._retirer_sources_visibles(reponse)

        self.assertEqual("Le signal est commandé par le poste.", resultat)


if __name__ == "__main__":
    unittest.main()
