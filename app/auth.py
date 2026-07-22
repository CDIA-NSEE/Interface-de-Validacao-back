from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError
from sqlmodel import Session, select

from app.config_source import email_domain_allowed
from app.database import get_session
from app.models import User


COGNITO_REGION = os.getenv("COGNITO_REGION", "us-east-1")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

_jwks_client: Optional[PyJWKClient] = None
_jwks_last_fetched: float = 0
_JWKS_TTL = 3600


def _get_jwks_url() -> str:
    if not COGNITO_USER_POOL_ID:
        raise RuntimeError("COGNITO_USER_POOL_ID not configured")
    return f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client, _jwks_last_fetched
    now = time.time()
    if _jwks_client is None or (now - _jwks_last_fetched) > _JWKS_TTL:
        _jwks_client = PyJWKClient(_get_jwks_url())
        _jwks_last_fetched = now
    return _jwks_client


def _decode_cognito_token(token: str) -> dict:
    if not COGNITO_USER_POOL_ID:
        raise RuntimeError("COGNITO_USER_POOL_ID not configured")

    jwks_client = _get_jwks_client()
    signing_key = jwks_client.get_signing_key_from_jwt(token)

    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=COGNITO_CLIENT_ID,
        issuer=f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}",
        options={"verify_exp": True},
    )
    return payload


def get_user_by_cognito_sub(session: Session, sub: str) -> User | None:
    return session.exec(select(User).where(User.username == sub)).first()


def get_or_create_user_from_token(session: Session, payload: dict) -> User:
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = payload.get("email", "")
    if email and not email_domain_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email domain not allowed",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_cognito_sub(session, sub)
    if not user:
        user = User(
            username=sub,
            full_name=payload.get("name") or payload.get("cognito:username") or "Cognito User",
            role="doctor",
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = _decode_cognito_token(token)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("token_use") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return get_or_create_user_from_token(session, payload)


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def create_access_token(username: str) -> str:
    """Legacy function - kept for backward compatibility but not used with Cognito."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "exp": expire}, "legacy-secret", algorithm="HS256")
