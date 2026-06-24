from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.domain.models import Base


ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Small synchronous repository wrapper over SQLAlchemy sessions."""

    model: type[ModelT]

    def __init__(self, session: Session, model: type[ModelT] | None = None) -> None:
        self.session = session
        if model is not None:
            self.model = model
        if not hasattr(self, "model"):
            raise TypeError("Repository model must be provided by class attribute or constructor.")

    def add(self, entity: ModelT, *, flush: bool = True) -> ModelT:
        self.session.add(entity)
        if flush:
            self.session.flush()
        return entity

    def get(self, entity_id: Any) -> ModelT | None:
        return self.session.get(self.model, entity_id)

    def require(self, entity_id: Any) -> ModelT:
        entity = self.get(entity_id)
        if entity is None:
            raise NotFoundError(f"{self.model.__name__} was not found.", metadata={"id": str(entity_id)})
        return entity

    def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        statement = select(self.model).limit(limit).offset(offset)
        return self.session.scalars(statement).all()

    def delete(self, entity: ModelT, *, flush: bool = True) -> None:
        self.session.delete(entity)
        if flush:
            self.session.flush()

    def execute(self, statement: Select[tuple[ModelT]]) -> Sequence[ModelT]:
        return self.session.scalars(statement).all()
