"""Exceções de domínio mapeadas posteriormente para respostas HTTP."""


class BusinessRuleError(Exception):
    """Regra de negócio inválida, normalmente respondida como HTTP 422."""


class NotFoundError(Exception):
    """Recurso solicitado não encontrado, normalmente respondido como HTTP 404."""


class ConflictError(Exception):
    """Conflito com o estado atual, normalmente respondido como HTTP 409."""