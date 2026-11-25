"""Enums persistidos no banco e expostos pelos contratos da API."""

from enum import StrEnum


class Perfil(StrEnum):
    ADMIN = "ADMIN"
    TECNICO = "TECNICO"
    SOLICITANTE = "SOLICITANTE"


class TipoEquipamento(StrEnum):
    IMPRESSORA = "IMPRESSORA"
    COMPUTADOR = "COMPUTADOR"


class StatusOperacional(StrEnum):
    ATIVO = "ATIVO"
    MANUTENCAO = "MANUTENCAO"
    INATIVO = "INATIVO"
    DESCARTADO = "DESCARTADO"


class PapelNoParque(StrEnum):
    EM_USO = "EM_USO"
    BACKUP = "BACKUP"


class TipoOS(StrEnum):
    CORRETIVA = "CORRETIVA"
    PREVENTIVA = "PREVENTIVA"
    INSTALACAO = "INSTALACAO"
    TROCA_TONER = "TROCA_TONER"
    CONFIGURACAO = "CONFIGURACAO"


class Prioridade(StrEnum):
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    CRITICA = "CRITICA"


class StatusOS(StrEnum):
    ABERTA = "ABERTA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    AGUARDANDO_USUARIO = "AGUARDANDO_USUARIO"
    AGUARDANDO_PECA = "AGUARDANDO_PECA"
    RESOLVIDA = "RESOLVIDA"
    CANCELADA = "CANCELADA"


class CorToner(StrEnum):
    PRETO = "PRETO"
    CIANO = "CIANO"
    MAGENTA = "MAGENTA"
    AMARELO = "AMARELO"


class TipoMovimentacao(StrEnum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
    DESCARTE = "DESCARTE"
    AJUSTE = "AJUSTE"


class StatusSLA(StrEnum):
    DENTRO_DO_PRAZO = "DENTRO_DO_PRAZO"
    EM_RISCO = "EM_RISCO"
    EXCEDIDO = "EXCEDIDO"
    PAUSADO = "PAUSADO"