from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock, patch

import jwt
from fastapi import HTTPException
from jwt.exceptions import InvalidTokenError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app import auth
from app.models import User


class CognitoAuthenticationTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        self.previous_jwks_client = auth._jwks_client
        self.previous_jwks_last_fetched = auth._jwks_last_fetched
        auth._jwks_client = None
        auth._jwks_last_fetched = 0

    def tearDown(self):
        auth._jwks_client = self.previous_jwks_client
        auth._jwks_last_fetched = self.previous_jwks_last_fetched
        self.engine.dispose()

    def _session(self):
        return Session(self.engine)

    def test_builds_jwks_url_and_requires_pool_configuration(self):
        with patch.object(auth, "COGNITO_USER_POOL_ID", "pool-123"), patch.object(
            auth, "COGNITO_REGION", "sa-east-1"
        ):
            self.assertEqual(
                auth._get_jwks_url(),
                "https://cognito-idp.sa-east-1.amazonaws.com/pool-123/.well-known/jwks.json",
            )

        with patch.object(auth, "COGNITO_USER_POOL_ID", None):
            with self.assertRaisesRegex(RuntimeError, "COGNITO_USER_POOL_ID"):
                auth._get_jwks_url()

    def test_jwks_client_is_cached_and_refreshed_after_ttl(self):
        first_client = MagicMock(name="first_client")
        second_client = MagicMock(name="second_client")

        with (
            patch.object(auth, "COGNITO_USER_POOL_ID", "pool-123"),
            patch.object(auth, "PyJWKClient", side_effect=[first_client, second_client]) as client,
            patch.object(auth.time, "time", side_effect=[100.0, 200.0, 4000.0]),
        ):
            self.assertIs(auth._get_jwks_client(), first_client)
            self.assertIs(auth._get_jwks_client(), first_client)
            self.assertIs(auth._get_jwks_client(), second_client)

        self.assertEqual(client.call_count, 2)

    def test_decodes_cognito_token_with_expected_key_and_claims(self):
        signing_key = MagicMock()
        signing_key.key = "public-key"
        jwks_client = MagicMock()
        jwks_client.get_signing_key_from_jwt.return_value = signing_key
        payload = {"sub": "cognito-sub", "token_use": "access"}

        with (
            patch.object(auth, "COGNITO_USER_POOL_ID", "pool-123"),
            patch.object(auth, "COGNITO_CLIENT_ID", "client-123"),
            patch.object(auth, "COGNITO_REGION", "us-east-2"),
            patch.object(auth, "_get_jwks_client", return_value=jwks_client),
            patch.object(auth.jwt, "decode", return_value=payload) as decode,
        ):
            self.assertEqual(auth._decode_cognito_token("jwt-token"), payload)

        jwks_client.get_signing_key_from_jwt.assert_called_once_with("jwt-token")
        decode.assert_called_once_with(
            "jwt-token",
            "public-key",
            algorithms=["RS256"],
            audience="client-123",
            issuer="https://cognito-idp.us-east-2.amazonaws.com/pool-123",
            options={"verify_exp": True},
        )

    def test_decode_requires_pool_configuration(self):
        with patch.object(auth, "COGNITO_USER_POOL_ID", None):
            with self.assertRaisesRegex(RuntimeError, "COGNITO_USER_POOL_ID"):
                auth._decode_cognito_token("jwt-token")

    def test_creates_and_reuses_user_from_access_token_claims(self):
        payload = {
            "sub": "cognito-sub",
            "email": "doctor@example.org",
            "name": "Dra. Ana",
        }

        with self._session() as session, patch.object(
            auth, "email_domain_allowed", return_value=True
        ):
            created = auth.get_or_create_user_from_token(session, payload)
            reused = auth.get_or_create_user_from_token(session, payload)

            self.assertEqual(created.id, reused.id)
            self.assertEqual(created.username, "cognito-sub")
            self.assertEqual(created.full_name, "Dra. Ana")
            self.assertEqual(created.role, "doctor")
            self.assertTrue(created.is_active)
            self.assertEqual(auth.get_user_by_cognito_sub(session, "cognito-sub").id, created.id)
            self.assertIsNone(auth.get_user_by_cognito_sub(session, "missing-sub"))

    def test_uses_cognito_username_or_fallback_name(self):
        with self._session() as session, patch.object(
            auth, "email_domain_allowed", return_value=True
        ):
            username_user = auth.get_or_create_user_from_token(
                session,
                {"sub": "sub-username", "cognito:username": "medico.cognito"},
            )
            fallback_user = auth.get_or_create_user_from_token(
                session,
                {"sub": "sub-fallback"},
            )
            username_full_name = username_user.full_name
            fallback_full_name = fallback_user.full_name

        self.assertEqual(username_full_name, "medico.cognito")
        self.assertEqual(fallback_full_name, "Cognito User")

    def test_rejects_missing_sub_disallowed_domain_and_inactive_user(self):
        with self._session() as session:
            with self.assertRaises(HTTPException) as missing_sub:
                auth.get_or_create_user_from_token(session, {"email": "doctor@example.org"})
            self.assertEqual(missing_sub.exception.status_code, 401)

            with patch.object(auth, "email_domain_allowed", return_value=False):
                with self.assertRaises(HTTPException) as disallowed:
                    auth.get_or_create_user_from_token(
                        session,
                        {"sub": "blocked-sub", "email": "doctor@blocked.example"},
                    )
            self.assertEqual(disallowed.exception.status_code, 403)

            inactive = User(
                username="inactive-sub",
                full_name="Usuario Inativo",
                is_active=False,
            )
            session.add(inactive)
            session.commit()
            with self.assertRaises(HTTPException) as inactive_error:
                auth.get_or_create_user_from_token(session, {"sub": "inactive-sub"})
            self.assertEqual(inactive_error.exception.status_code, 401)

    def test_current_user_rejects_missing_invalid_and_wrong_token_type(self):
        with self._session() as session:
            with self.assertRaises(HTTPException) as missing:
                auth.get_current_user(None, session)
            self.assertEqual(missing.exception.status_code, 401)

            with patch.object(
                auth,
                "_decode_cognito_token",
                side_effect=InvalidTokenError("invalid token"),
            ):
                with self.assertRaises(HTTPException) as invalid:
                    auth.get_current_user("invalid", session)
            self.assertEqual(invalid.exception.status_code, 401)

            with patch.object(
                auth,
                "_decode_cognito_token",
                return_value={"sub": "subject", "token_use": "id"},
            ):
                with self.assertRaises(HTTPException) as wrong_type:
                    auth.get_current_user("id-token", session)
            self.assertEqual(wrong_type.exception.status_code, 401)

    def test_current_user_accepts_access_token_and_active_user(self):
        expected_user = User(username="subject", full_name="Dra. Ana")
        payload = {"sub": "subject", "token_use": "access"}

        with self._session() as session, patch.object(
            auth, "_decode_cognito_token", return_value=payload
        ), patch.object(
            auth, "get_or_create_user_from_token", return_value=expected_user
        ) as get_or_create:
            current = auth.get_current_user("access-token", session)

        self.assertIs(current, expected_user)
        get_or_create.assert_called_once_with(session, payload)
        self.assertIs(auth.get_current_active_user(expected_user), expected_user)

    def test_active_user_dependency_rejects_inactive_user(self):
        inactive = User(username="inactive", full_name="Inativo", is_active=False)
        with self.assertRaises(HTTPException) as error:
            auth.get_current_active_user(inactive)
        self.assertEqual(error.exception.status_code, 401)

    def test_legacy_access_token_contains_subject_and_future_expiration(self):
        before = datetime.now(timezone.utc).timestamp()
        token = auth.create_access_token("legacy-user")
        payload = jwt.decode(token, "legacy-secret", algorithms=["HS256"])

        self.assertEqual(payload["sub"], "legacy-user")
        self.assertGreater(payload["exp"], before)


if __name__ == "__main__":
    unittest.main()
