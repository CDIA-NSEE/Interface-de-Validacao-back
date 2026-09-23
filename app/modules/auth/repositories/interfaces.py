from __future__ import annotations

from abc import abstractmethod

from app.modules.auth.models import User
from app.shared.repository import Repository


class UserRepository(Repository[User, int]):
    @abstractmethod
    def get_by_username(self, username: str) -> User | None: ...
