from __future__ import annotations

from sqlmodel import Session, select

from app.modules.auth.models import User
from app.modules.auth.repositories.interfaces import UserRepository
from app.shared.repository import SqlModelRepository


class SqlModelUserRepository(SqlModelRepository[User], UserRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session, User)

    def get_by_username(self, username: str) -> User | None:
        return self._session.exec(select(User).where(User.username == username)).first()
