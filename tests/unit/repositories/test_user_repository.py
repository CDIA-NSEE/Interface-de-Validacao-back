from __future__ import annotations

from app.models import User
from app.repositories.sqlmodel.user_repository import SqlModelUserRepository


def test_get_by_username(session):
    repo = SqlModelUserRepository(session)
    repo.add(User(username="doctor1", full_name="Dr. One", hashed_password="hash"))
    repo.commit()

    user = repo.get_by_username("doctor1")
    assert user is not None
    assert user.full_name == "Dr. One"
    assert repo.get_by_username("missing") is None
