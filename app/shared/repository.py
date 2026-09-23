from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from sqlmodel import Session

ModelT = TypeVar("ModelT")
IdT = TypeVar("IdT")


class Repository(ABC, Generic[ModelT, IdT]):
    @abstractmethod
    def get(self, entity_id: IdT) -> ModelT | None: ...

    @abstractmethod
    def add(self, entity: ModelT) -> ModelT: ...

    @abstractmethod
    def save(self, entity: ModelT) -> ModelT: ...

    @abstractmethod
    def delete(self, entity: ModelT) -> None: ...

    @abstractmethod
    def flush(self) -> None: ...

    @abstractmethod
    def refresh(self, entity: ModelT) -> None: ...

    @abstractmethod
    def commit(self) -> None: ...


class SqlModelRepository(Repository[ModelT, int], Generic[ModelT]):
    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self._session = session
        self._model = model

    def get(self, entity_id: int) -> ModelT | None:
        return self._session.get(self._model, entity_id)

    def add(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        return entity

    def save(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        return entity

    def delete(self, entity: ModelT) -> None:
        self._session.delete(entity)

    def flush(self) -> None:
        self._session.flush()

    def refresh(self, entity: ModelT) -> None:
        self._session.refresh(entity)

    def commit(self) -> None:
        self._session.commit()
