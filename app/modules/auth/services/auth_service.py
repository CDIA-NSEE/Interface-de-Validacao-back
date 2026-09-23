from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.exceptions import ForbiddenError, UnauthorizedError, ValidationError
from app.core.settings import Settings
from app.models import User
from app.repositories.interfaces.config_repository import ConfigRepository
from app.repositories.interfaces.user_repository import UserRepository
from app.schemas import LoginRequest, TokenResponse, UserRead

_password_hash = PasswordHash.recommended()
_DUMMY_HASH = _password_hash.hash("dummy-password")


def _split_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip().lower() for item in value.split(",") if item.strip()]


class AuthService:
    def __init__(
        self,
        user_repository: UserRepository,
        config_repository: ConfigRepository,
        settings: Settings,
    ) -> None:
        self._user_repository = user_repository
        self._config_repository = config_repository
        self._settings = settings

    @staticmethod
    def hash_password(password: str) -> str:
        return _password_hash.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return _password_hash.verify(plain_password, hashed_password)

    def get_user_by_username(self, username: str) -> User | None:
        normalized_username = username.strip().lower()
        if not normalized_username:
            return None
        return self._user_repository.get_by_username(normalized_username)

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.get_user_by_username(username)
        if not user:
            self.verify_password(password, _DUMMY_HASH)
            return None
        if not user.is_active:
            self.verify_password(password, _DUMMY_HASH)
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        return user

    def create_access_token(self, username: str) -> str:
        expire = datetime.now(UTC) + timedelta(minutes=self._settings.auth.access_token_expire_minutes)
        return jwt.encode(
            {"sub": username, "exp": expire},
            self._settings.auth.secret_key,
            algorithm=self._settings.auth.algorithm,
        )

    def load_auth_config(self) -> dict:
        data = self._config_repository.load_json("auth_config.json", {"allowed_email_domains": []})
        return {
            "allowed_email_domains": [
                domain.strip().lower()
                for domain in data.get("allowed_email_domains", [])
                if str(domain).strip()
            ]
        }

    def allowed_email_domains(self) -> list[str]:
        env_domains = self._settings.auth.allowed_email_domains
        if env_domains is not None:
            return _split_csv(env_domains)
        return self.load_auth_config()["allowed_email_domains"]

    def email_domain_allowed(self, identifier: str) -> bool:
        domains = self.allowed_email_domains()
        if not domains:
            return True
        if "@" not in identifier:
            return False
        domain = identifier.rsplit("@", 1)[1].strip().lower()
        return domain in domains

    @staticmethod
    def user_read(user: User) -> UserRead:
        return UserRead(
            id=user.id,
            username=user.username,
            email=user.username if "@" in user.username else None,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
        )

    def login(self, payload: LoginRequest) -> TokenResponse:
        identifier = payload.identifier
        if not identifier or not payload.password:
            raise ValidationError("Informe e-mail/usuario e senha.")

        user = self.authenticate(identifier, payload.password)
        if not user:
            raise UnauthorizedError("Usuário ou senha inválidos.")

        if user.role != "admin" and not self.email_domain_allowed(user.username):
            raise ForbiddenError("E-mail fora do dominio institucional BP configurado.")

        return TokenResponse(access_token=self.create_access_token(user.username), user=self.user_read(user))
