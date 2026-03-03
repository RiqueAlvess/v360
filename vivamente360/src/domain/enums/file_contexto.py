from enum import Enum


class FileContexto(str, Enum):
    """Contexto de uso do arquivo dentro do sistema."""

    CHECKLIST_EVIDENCIA = "checklist_evidencia"
    PLANO_ACAO = "plano_acao"
    DENUNCIA = "denuncia"
