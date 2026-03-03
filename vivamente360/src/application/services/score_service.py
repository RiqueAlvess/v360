"""Service de cálculo de scores para as dimensões HSE-IT.

Regra R3: Todo cálculo ocorre aqui, invocado pelo worker assíncrono.
O dashboard NUNCA chama este service diretamente — apenas lê fact_score_dimensao.

Regra R7 (Blueprint 07): Sem magic numbers — todos os thresholds são constantes nomeadas.
"""
from decimal import Decimal
from typing import Any

from src.domain.enums.dimensao_hse import DimensaoHSE
from src.domain.enums.nivel_risco import NivelRisco

# ---------------------------------------------------------------------------
# Constantes de threshold para classificação de risco (escala Likert 1-5)
# Baseadas no instrumento HSE-IT adaptado para o contexto brasileiro.
#
# Interpretação (score médio das respostas por dimensão):
#   >= THRESHOLD_ACEITAVEL  → risco aceitável (situação favorável)
#   >= THRESHOLD_MODERADO   → risco moderado  (atenção recomendada)
#   >= THRESHOLD_IMPORTANTE → risco importante (intervenção necessária)
#   <  THRESHOLD_IMPORTANTE → risco crítico   (intervenção urgente)
# ---------------------------------------------------------------------------
THRESHOLD_ACEITAVEL: Decimal = Decimal("4.00")
THRESHOLD_MODERADO: Decimal = Decimal("3.00")
THRESHOLD_IMPORTANTE: Decimal = Decimal("2.00")

# Score mínimo e máximo da escala Likert utilizada
SCORE_MINIMO: Decimal = Decimal("1.00")
SCORE_MAXIMO: Decimal = Decimal("5.00")

# Dicionário de thresholds para serialização e uso em relatórios
RISK_THRESHOLDS: dict[NivelRisco, Decimal] = {
    NivelRisco.ACEITAVEL: THRESHOLD_ACEITAVEL,
    NivelRisco.MODERADO: THRESHOLD_MODERADO,
    NivelRisco.IMPORTANTE: THRESHOLD_IMPORTANTE,
}

# Chaves esperadas no JSONB de respostas para cada dimensão
DIMENSAO_KEYS: dict[DimensaoHSE, str] = {
    DimensaoHSE.DEMANDAS: "demandas",
    DimensaoHSE.CONTROLE: "controle",
    DimensaoHSE.SUPORTE_GESTAO: "suporte_gestao",
    DimensaoHSE.RELACIONAMENTOS: "relacionamentos",
    DimensaoHSE.PAPEL_FUNCAO: "papel_funcao",
    DimensaoHSE.MUDANCAS: "mudancas",
    DimensaoHSE.SUPORTE_COLEGAS: "suporte_colegas",
}


class ScoreService:
    """Calcula e classifica scores das dimensões HSE-IT a partir de respostas brutas.

    Responsabilidades:
    - Extrair scores por dimensão do JSONB de respostas.
    - Calcular score médio para uma coleção de respostas.
    - Classificar o nível de risco usando RISK_THRESHOLDS nomeados.

    Não acessa banco de dados — trabalha apenas com dados em memória.
    """

    def calcular_nivel_risco(self, score_medio: Decimal) -> NivelRisco:
        """Classifica o nível de risco com base no score médio da dimensão.

        Utiliza exclusivamente constantes nomeadas — zero magic numbers.

        Args:
            score_medio: Score médio calculado para a dimensão (1.0 a 5.0).

        Returns:
            NivelRisco correspondente ao score fornecido.
        """
        if score_medio >= THRESHOLD_ACEITAVEL:
            return NivelRisco.ACEITAVEL
        if score_medio >= THRESHOLD_MODERADO:
            return NivelRisco.MODERADO
        if score_medio >= THRESHOLD_IMPORTANTE:
            return NivelRisco.IMPORTANTE
        return NivelRisco.CRITICO

    def extrair_score_dimensao(
        self,
        respostas: dict[str, Any],
        dimensao: DimensaoHSE,
    ) -> Decimal | None:
        """Extrai o score de uma dimensão específica do JSONB de respostas.

        O JSONB pode conter o score como:
        - Um número direto (float/int): valor único já agregado.
        - Uma lista de números: média será calculada pelo caller.

        Args:
            respostas: Dicionário JSONB da survey_response.
            dimensao: Dimensão HSE-IT a extrair.

        Returns:
            Score como Decimal, ou None se a dimensão não está presente.
        """
        chave = DIMENSAO_KEYS[dimensao]
        valor = respostas.get(chave)
        if valor is None:
            return None

        if isinstance(valor, (int, float)):
            return Decimal(str(valor))

        if isinstance(valor, list) and valor:
            numericos = [v for v in valor if isinstance(v, (int, float))]
            if not numericos:
                return None
            return Decimal(str(sum(numericos) / len(numericos)))

        return None

    def calcular_score_dimensao(
        self,
        respostas_lista: list[dict[str, Any]],
        dimensao: DimensaoHSE,
    ) -> tuple[Decimal, NivelRisco, int] | None:
        """Calcula score médio e nível de risco para uma dimensão a partir de múltiplas respostas.

        Args:
            respostas_lista: Lista de dicionários JSONB de survey_responses.
            dimensao: Dimensão HSE-IT a calcular.

        Returns:
            Tupla (score_medio, nivel_risco, total_respostas) ou None se não
            houver respostas válidas para a dimensão.
        """
        scores_validos: list[Decimal] = []

        for respostas in respostas_lista:
            score = self.extrair_score_dimensao(respostas, dimensao)
            if score is not None:
                scores_validos.append(score)

        if not scores_validos:
            return None

        score_medio = Decimal(
            str(sum(scores_validos) / len(scores_validos))
        ).quantize(Decimal("0.01"))

        nivel_risco = self.calcular_nivel_risco(score_medio)
        total_respostas = len(scores_validos)

        return score_medio, nivel_risco, total_respostas

    def calcular_indice_geral(
        self,
        scores_por_dimensao: dict[DimensaoHSE, Decimal],
    ) -> tuple[Decimal, NivelRisco]:
        """Calcula o índice geral de risco como média das dimensões presentes.

        Args:
            scores_por_dimensao: Mapeamento de dimensão para score médio.

        Returns:
            Tupla (indice_geral, nivel_risco_geral). Retorna (SCORE_MAXIMO, ACEITAVEL)
            se não houver scores disponíveis.
        """
        if not scores_por_dimensao:
            return SCORE_MAXIMO, NivelRisco.ACEITAVEL

        indice = Decimal(
            str(sum(scores_por_dimensao.values()) / len(scores_por_dimensao))
        ).quantize(Decimal("0.01"))

        return indice, self.calcular_nivel_risco(indice)
