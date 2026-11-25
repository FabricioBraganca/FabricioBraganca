"""Tipos Pydantic compartilhados pelos endpoints."""

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    """Base de schemas que podem ser montados a partir de objetos ORM."""

    model_config = ConfigDict(from_attributes=True)


class Pagina[T](BaseModel):
    """Envelope paginado padrão para listagens da API."""

    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)