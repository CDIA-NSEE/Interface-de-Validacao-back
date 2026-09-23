from __future__ import annotations

import pytest

from app.core.exceptions import ForbiddenError, UnauthorizedError, ValidationError
from app.schemas import LoginRequest
from app.services.auth_service import AuthService
from tests.unit.services.conftest import make_user


@pytest.fixture()
def service(user_repository, fake_config_repository, settings):
    return AuthService(user_repository, fake_config_repository, settings)


def test_hash_and_verify_password_roundtrip(service):
    hashed = service.hash_password("s3cret")
    assert service.verify_password("s3cret", hashed) is True
    assert service.verify_password("wrong", hashed) is False


def test_authenticate_returns_none_for_unknown_user(session, service):
    assert service.authenticate("nobody", "pw") is None


def test_authenticate_returns_none_for_inactive_user(session, service):
    make_user(session, username="inactive", hashed_password=service.hash_password("pw"), is_active=False)
    assert service.authenticate("inactive", "pw") is None


def test_authenticate_returns_none_for_wrong_password(session, service):
    make_user(session, username="dr.x", hashed_password=service.hash_password("right"))
    assert service.authenticate("dr.x", "wrong") is None


def test_authenticate_returns_user_for_correct_credentials(session, service):
    user = make_user(session, username="dr.x", hashed_password=service.hash_password("right"))
    authenticated = service.authenticate("DR.X", "right")
    assert authenticated.id == user.id


def test_email_domain_allowed_true_when_no_domains_configured(service):
    assert service.email_domain_allowed("user@anything.com") is True


def test_email_domain_allowed_checks_configured_domains(fake_config_repository, service):
    fake_config_repository._data["auth_config.json"] = {"allowed_email_domains": ["bp.com"]}
    assert service.email_domain_allowed("user@bp.com") is True
    assert service.email_domain_allowed("user@other.com") is False
    assert service.email_domain_allowed("no-at-sign") is False


def test_email_domain_allowed_env_override_takes_precedence(fake_config_repository, settings, service):
    fake_config_repository._data["auth_config.json"] = {"allowed_email_domains": ["bp.com"]}
    settings.auth.allowed_email_domains = "other.com"
    assert service.email_domain_allowed("user@other.com") is True
    assert service.email_domain_allowed("user@bp.com") is False


def test_login_raises_validation_error_when_missing_identifier_or_password(service):
    with pytest.raises(ValidationError):
        service.login(LoginRequest(password=""))


def test_login_raises_unauthorized_for_bad_credentials(session, service):
    with pytest.raises(UnauthorizedError):
        service.login(LoginRequest(username="nobody", password="pw"))


def test_login_raises_forbidden_when_domain_not_allowed(session, service, fake_config_repository):
    fake_config_repository._data["auth_config.json"] = {"allowed_email_domains": ["bp.com"]}
    make_user(session, username="dr@other.com", hashed_password=service.hash_password("pw"))

    with pytest.raises(ForbiddenError):
        service.login(LoginRequest(username="dr@other.com", password="pw"))


def test_login_admin_bypasses_domain_check(session, service, fake_config_repository):
    fake_config_repository._data["auth_config.json"] = {"allowed_email_domains": ["bp.com"]}
    make_user(
        session,
        username="admin@other.com",
        hashed_password=service.hash_password("pw"),
        role="admin",
    )

    token_response = service.login(LoginRequest(username="admin@other.com", password="pw"))

    assert token_response.access_token
    assert token_response.user.role == "admin"


def test_user_read_derives_email_only_when_username_has_at_sign():
    from app.models import User

    user = User(id=1, username="plainuser", full_name="Plain", hashed_password="x")
    assert AuthService.user_read(user).email is None

    user2 = User(id=2, username="a@b.com", full_name="Plain", hashed_password="x")
    assert AuthService.user_read(user2).email == "a@b.com"
