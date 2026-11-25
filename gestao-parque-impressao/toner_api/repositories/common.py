"""Operações compartilhadas de paginação para consultas SQLAlchemy."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select


def paginar[T](db: Session, statement: Select[tuple[T]], limit: int, offset: int) -> tuple[list[T], int]:
    """Retorna itens e total antes da paginação, mantendo ordenação da consulta."""
    total_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = db.scalar(total_statement) or 0
    items = list(db.scalars(statement.limit(limit).offset(offset)).all())
    return items, total