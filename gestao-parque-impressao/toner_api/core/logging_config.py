"""Configuração de logs estruturados em JSON para a aplicação."""

import json
import logging
from datetime import datetime, timezone
from typing import override


class JsonFormatter(logging.Formatter):
    """Formata eventos de log com campos estáveis e timestamp UTC."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, str] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, ensure_ascii=False)


def configure_logging() -> None:
    """Instala um handler JSON no logger raiz sem duplicar handlers."""
    root_logger = logging.getLogger()
    if any(isinstance(handler.formatter, JsonFormatter) for handler in root_logger.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)