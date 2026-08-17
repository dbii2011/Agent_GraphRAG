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


if __name__ == "__main__":
    unittest.main()
