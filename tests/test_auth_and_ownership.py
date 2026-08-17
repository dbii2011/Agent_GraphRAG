import unittest

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import api


class AuthAndOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_engine = api.engine
        api.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(api.engine)
        cls.alice = TestClient(api.app)
        cls.bob = TestClient(api.app)

    @classmethod
    def tearDownClass(cls):
        api.engine.dispose()
        api.engine = cls.previous_engine

    def test_01_registration_sets_session_and_me_works(self):
        response = self.alice.post("/auth/register", json={
            "nom_utilisateur": "Alice.Test",
            "mot_de_passe": "mot-de-passe-alice",
        })
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual("alice.test", response.json()["nom_utilisateur"])
        self.assertIn(api.SESSION_COOKIE, response.cookies)
        self.assertEqual(200, self.alice.get("/auth/me").status_code)

    def test_02_conversations_are_isolated_by_user(self):
        self.bob.post("/auth/register", json={
            "nom_utilisateur": "bob.test",
            "mot_de_passe": "mot-de-passe-bob",
        })
        alice_id = self.alice.get("/auth/me").json()["id"]
        conversation_id = api._creer_conversation("Conversation Alice", api.uuid.UUID(alice_id))

        alice_list = self.alice.get("/conversations")
        bob_list = self.bob.get("/conversations")
        self.assertEqual([conversation_id], [c["id"] for c in alice_list.json()])
        self.assertEqual([], bob_list.json())
        self.assertEqual(404, self.bob.get(f"/conversations/{conversation_id}/messages").status_code)

    def test_03_logout_revokes_session(self):
        self.assertEqual(204, self.alice.post("/auth/logout").status_code)
        self.assertEqual(401, self.alice.get("/auth/me").status_code)


if __name__ == "__main__":
    unittest.main()
