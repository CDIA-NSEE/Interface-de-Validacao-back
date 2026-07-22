import unittest
from unittest.mock import MagicMock, patch

from fastapi import Depends, FastAPI
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

import app.main as main_module
from app.auth import oauth2_scheme


class HealthCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main_module.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def setUp(self):
        self.previous_db_initialized = main_module._db_initialized

    def tearDown(self):
        main_module._db_initialized = self.previous_db_initialized

    def test_health_is_public_and_reports_database_connection(self):
        main_module._db_initialized = False
        with (
            patch.object(
                main_module,
                "create_db_and_tables",
                side_effect=AssertionError("health must not initialize the database schema"),
            ),
            patch.object(main_module, "_database_connection_is_available", return_value=True),
        ):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "connected"})

    def test_health_returns_sanitized_503_when_database_is_unavailable(self):
        with patch.object(main_module, "_database_connection_is_available", return_value=False):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Banco de dados indisponivel."})

    def test_health_with_trailing_slash_does_not_initialize_schema_when_unavailable(self):
        main_module._db_initialized = False
        with (
            patch.object(
                main_module,
                "create_db_and_tables",
                side_effect=AssertionError("health must not initialize the database schema"),
            ),
            patch.object(main_module, "_database_connection_is_available", return_value=False),
        ):
            response = self.client.get("/health/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Banco de dados indisponivel."})

    def test_protected_route_requires_authorization(self):
        with patch.object(main_module, "_db_initialized", True):
            response = self.client.get("/auth/me")

        self.assertEqual(response.status_code, 401)

    def test_database_probe_executes_a_minimal_query(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.__exit__.return_value = False

        with patch.object(main_module.engine, "connect", return_value=connection):
            self.assertTrue(main_module._database_connection_is_available())

        statement = connection.execute.call_args.args[0]
        self.assertEqual(str(statement), "SELECT 1")

    def test_database_probe_hides_sqlalchemy_failures(self):
        with patch.object(
            main_module.engine,
            "connect",
            side_effect=SQLAlchemyError("sensitive connection details"),
        ):
            self.assertFalse(main_module._database_connection_is_available())


class OpenApiDocumentationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main_module.app.openapi_schema = None
        cls.schema = main_module.app.openapi()
        cls.client = TestClient(main_module.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_uses_expected_documentation_groups(self):
        self.assertEqual(
            [tag["name"] for tag in self.schema["tags"]],
            [
                "Sistema",
                "Autenticacao",
                "Validacao",
                "Suporte",
                "Exames",
                "Diagnosticos",
                "Dashboard",
            ],
        )

    def test_every_operation_has_tag_summary_and_description(self):
        for path, path_item in self.schema["paths"].items():
            for method, operation in path_item.items():
                with self.subTest(path=path, method=method):
                    self.assertTrue(operation.get("tags"))
                    self.assertTrue(operation.get("summary"))
                    self.assertTrue(operation.get("description"))

    def test_swagger_accepts_a_manual_cognito_bearer_token(self):
        self.assertIsInstance(oauth2_scheme, OAuth2PasswordBearer)

        security_scheme = self.schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]
        self.assertEqual(security_scheme["type"], "http")
        self.assertEqual(security_scheme["scheme"], "bearer")
        self.assertEqual(security_scheme["bearerFormat"], "JWT")
        self.assertNotIn("flows", security_scheme)
        self.assertEqual(
            self.schema["paths"]["/auth/me"]["get"]["security"],
            [{"OAuth2PasswordBearer": []}],
        )

    def test_runtime_oauth2_scheme_extracts_bearer_token(self):
        auth_app = FastAPI()

        @auth_app.get("/protected")
        def protected(token: str = Depends(oauth2_scheme)) -> dict:
            return {"token": token}

        with TestClient(auth_app) as client:
            response = client.get(
                "/protected",
                headers={"Authorization": "Bearer cognito-access-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"token": "cognito-access-token"})

    def test_health_contract_is_described_without_authentication(self):
        operation = self.schema["paths"]["/health"]["get"]

        self.assertNotIn("security", operation)
        self.assertIn("200", operation["responses"])
        self.assertIn("503", operation["responses"])

    def test_documentation_routes_do_not_initialize_database_schema(self):
        with (
            patch.object(main_module, "_db_initialized", False),
            patch.object(
                main_module,
                "create_db_and_tables",
                side_effect=AssertionError(
                    "documentation must not initialize the database schema"
                ),
            ),
        ):
            docs_response = self.client.get("/docs")
            oauth_redirect_response = self.client.get("/docs/oauth2-redirect")
            redoc_response = self.client.get("/redoc")
            openapi_response = self.client.get("/openapi.json")

        self.assertEqual(docs_response.status_code, 200)
        self.assertEqual(oauth_redirect_response.status_code, 200)
        self.assertEqual(redoc_response.status_code, 200)
        self.assertEqual(openapi_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
