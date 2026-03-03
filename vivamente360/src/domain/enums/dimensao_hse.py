from enum import Enum


class DimensaoHSE(str, Enum):
    """As 7 dimensões do modelo HSE-IT (Health and Safety Executive - Indicators Tool).

    Adaptação brasileira do instrumento de avaliação de riscos psicossociais.
    """

    DEMANDAS = "demandas"
    CONTROLE = "controle"
    SUPORTE_GESTAO = "suporte_gestao"
    RELACIONAMENTOS = "relacionamentos"
    PAPEL_FUNCAO = "papel_funcao"
    MUDANCAS = "mudancas"
    SUPORTE_COLEGAS = "suporte_colegas"
