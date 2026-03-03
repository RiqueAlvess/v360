from enum import Enum


class ActionPlanStatus(str, Enum):
    """Status do ciclo de vida de um Plano de Ação.

    Ordem de progressão: pendente → em_andamento → concluido
    Cancelamento pode ocorrer a partir de qualquer estado ativo.
    """

    PENDENTE = "pendente"
    EM_ANDAMENTO = "em_andamento"
    CONCLUIDO = "concluido"
    CANCELADO = "cancelado"
