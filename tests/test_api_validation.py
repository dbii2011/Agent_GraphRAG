import unittest
import uuid

from fastapi import HTTPException

import api
from api import _uuid_valide


class ApiValidationTests(unittest.TestCase):
    def test_valid_uuid_is_parsed(self):
        value = str(uuid.uuid4())
        self.assertEqual(uuid.UUID(value), _uuid_valide(value))

    def test_invalid_uuid_returns_http_400(self):
        with self.assertRaises(HTTPException) as raised:
            _uuid_valide("invalide")
        self.assertEqual(400, raised.exception.status_code)

    def test_health_reports_unavailable_neo4j(self):
        class Driver:
            def verify_connectivity(self):
                raise RuntimeError("indisponible")

        class Agent:
            driver = Driver()

        previous = api.agent
        api.agent = Agent()
        try:
            with self.assertRaises(HTTPException) as raised:
                api.health()
            self.assertEqual(503, raised.exception.status_code)
        finally:
            api.agent = previous


if __name__ == "__main__":
    unittest.main()
