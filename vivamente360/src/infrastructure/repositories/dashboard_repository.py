"""Repositório expandido de dashboard — Módulo 09: Filtros & Comparativo.

Estende SQLAnalyticsRepository com métodos de leitura avançados:
- get_heatmap()   com filtros opcionais por unidade, setor e dimensão.
- get_top_risks() top 5 combinações setor+dimensão com maior risco por campanha.
- get_compare()   comparativo entre campanhas com delta por dimensão.
- get_trends()    evolução temporal do score geral por empresa.

Regra R3: TODOS os métodos lêem exclusivamente de fact_score_dimensao e da
view materializada campaign_comparison — zero cálculo em runtime.

Regra R4: get_heatmap() mantém paginação obrigatória por dim_estrutura.
"""
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import func, select

from src.application.services.score_service import ScoreService
from src.domain.enums.dimensao_hse import DimensaoHSE
from src.domain.enums.nivel_risco import NivelRisco
from src.infrastructure.database.models.campaign import Campaign
from src.infrastructure.database.models.dim_estrutura import DimEstrutura
from src.infrastructure.database.models.fact_score_dimensao import FactScoreDimensao
from src.infrastructure.repositories.analytics_repository import SQLAnalyticsRepository

# Constante: número máximo de campanhas permitidas no comparativo
_MAX_CAMPANHAS_COMPARE: int = 3


class SQLDashboardRepository(SQLAnalyticsRepository):
    """Implementação do repositório de dashboard com filtros e comparativo.

    Herda todos os métodos de SQLAnalyticsRepository e sobrescreve get_heatmap()
    para suportar filtros adicionais por unidade, setor e dimensão.
    """

    async def get_heatmap(
        self,
        campaign_id: UUID,
        page: int,
        page_size: int,
        unidade_id: Optional[UUID] = None,
        setor_id: Optional[UUID] = None,
        dimensao: Optional[str] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Retorna matriz setor×dimensão paginada com filtros opcionais.

        Sobrescreve o método base adicionando filtros por unidade, setor e
        dimensão. Os filtros são aplicados diretamente em fact_score_dimensao
        usando as colunas desnormalizadas (Módulo 09) — sem JOIN extra.

        Args:
            campaign_id: UUID da campanha.
            page: Página atual (1-indexed).
            page_size: Quantidade de estruturas por página (máximo 100).
            unidade_id: Filtro opcional por unidade organizacional.
            setor_id: Filtro opcional por setor.
            dimensao: Filtro opcional por dimensão HSE-IT (valor do enum).

        Returns:
            Tupla (lista_de_células_heatmap, total_de_estruturas_filtradas).
        """
        # Validar dimensao se fornecida
        dimensao_enum: Optional[DimensaoHSE] = None
        if dimensao is not None:
            try:
                dimensao_enum = DimensaoHSE(dimensao)
            except ValueError:
                return [], 0

        # Construir cláusulas WHERE compartilhadas entre count e dados
        base_filters = [FactScoreDimensao.campaign_id == campaign_id]
        if unidade_id is not None:
            base_filters.append(FactScoreDimensao.unidade_id == unidade_id)
        if setor_id is not None:
            base_filters.append(FactScoreDimensao.setor_id == setor_id)
        if dimensao_enum is not None:
            base_filters.append(FactScoreDimensao.dimensao == dimensao_enum)

        # Contar total de dim_estruturas distintas após filtros
        count_stmt = select(
            func.count(func.distinct(FactScoreDimensao.dim_estrutura_id))
        ).where(*base_filters)
        count_result = await self._session.execute(count_stmt)
        total: int = count_result.scalar_one() or 0

        if total == 0:
            return [], 0

        # Buscar estruturas distintas com paginação
        offset = (page - 1) * page_size
        estruturas_stmt = (
            select(FactScoreDimensao.dim_estrutura_id)
            .where(*base_filters)
            .group_by(FactScoreDimensao.dim_estrutura_id)
            .order_by(FactScoreDimensao.dim_estrutura_id)
            .offset(offset)
            .limit(page_size)
        )
        estruturas_result = await self._session.execute(estruturas_stmt)
        estrutura_ids: list[UUID] = [row[0] for row in estruturas_result.all()]

        if not estrutura_ids:
            return [], total

        # Buscar scores para as estruturas paginadas em uma única query
        scores_filters = [
            FactScoreDimensao.campaign_id == campaign_id,
            FactScoreDimensao.dim_estrutura_id.in_(estrutura_ids),
        ]
        if dimensao_enum is not None:
            scores_filters.append(FactScoreDimensao.dimensao == dimensao_enum)

        scores_stmt = (
            select(
                FactScoreDimensao.dim_estrutura_id,
                FactScoreDimensao.dimensao,
                func.avg(FactScoreDimensao.score_medio).label("score_medio"),
                DimEstrutura.unidade_nome,
                DimEstrutura.setor_nome,
                DimEstrutura.cargo_nome,
            )
            .join(
                DimEstrutura,
                FactScoreDimensao.dim_estrutura_id == DimEstrutura.id,
            )
            .where(*scores_filters)
            .group_by(
                FactScoreDimensao.dim_estrutura_id,
                FactScoreDimensao.dimensao,
                DimEstrutura.unidade_nome,
                DimEstrutura.setor_nome,
                DimEstrutura.cargo_nome,
            )
        )
        scores_result = await self._session.execute(scores_stmt)
        rows = scores_result.all()

        score_service = ScoreService()
        heatmap_cells: list[dict[str, Any]] = []
        for row in rows:
            score = Decimal(str(row.score_medio)).quantize(Decimal("0.01"))
            nivel = score_service.calcular_nivel_risco(score)
            heatmap_cells.append(
                {
                    "dim_estrutura_id": str(row.dim_estrutura_id),
                    "dimensao": row.dimensao.value,
                    "score_medio": float(score),
                    "nivel_risco": nivel.value,
                    "unidade_nome": row.unidade_nome,
                    "setor_nome": row.setor_nome,
                    "cargo_nome": row.cargo_nome,
                }
            )

        return heatmap_cells, total

    async def get_top_risks(
        self, campaign_id: UUID
    ) -> list[dict[str, Any]]:
        """Retorna top 5 combinações setor+dimensão com maior risco da campanha.

        Agrega por (dim_estrutura_id, dimensao) e ordena por score_medio ASC
        (menor score = maior risco). Sem paginação — sempre 5 itens ou menos.

        Args:
            campaign_id: UUID da campanha.

        Returns:
            Lista de até 5 dicionários com dim_estrutura_id, dimensao,
            score_medio, nivel_risco, unidade_nome e setor_nome.
        """
        stmt = (
            select(
                FactScoreDimensao.dim_estrutura_id,
                FactScoreDimensao.dimensao,
                func.avg(FactScoreDimensao.score_medio).label("score_medio"),
                DimEstrutura.unidade_nome,
                DimEstrutura.setor_nome,
                DimEstrutura.cargo_nome,
            )
            .join(
                DimEstrutura,
                FactScoreDimensao.dim_estrutura_id == DimEstrutura.id,
            )
            .where(FactScoreDimensao.campaign_id == campaign_id)
            .group_by(
                FactScoreDimensao.dim_estrutura_id,
                FactScoreDimensao.dimensao,
                DimEstrutura.unidade_nome,
                DimEstrutura.setor_nome,
                DimEstrutura.cargo_nome,
            )
            .order_by(sa.asc("score_medio"))
            .limit(5)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        score_service = ScoreService()
        top_risks: list[dict[str, Any]] = []
        for row in rows:
            score = Decimal(str(row.score_medio)).quantize(Decimal("0.01"))
            nivel = score_service.calcular_nivel_risco(score)
            top_risks.append(
                {
                    "dim_estrutura_id": str(row.dim_estrutura_id),
                    "dimensao": row.dimensao.value,
                    "score_medio": float(score),
                    "nivel_risco": nivel.value,
                    "unidade_nome": row.unidade_nome,
                    "setor_nome": row.setor_nome,
                    "cargo_nome": row.cargo_nome,
                }
            )

        return top_risks

    async def get_compare(
        self,
        campaign_ids: list[UUID],
        dimensao: Optional[str] = None,
        unidade_id: Optional[UUID] = None,
    ) -> dict[str, Any]:
        """Compara até 3 campanhas retornando scores e delta por dimensão.

        Consulta fact_score_dimensao diretamente para suportar filtro por
        unidade_id. O delta_por_dimensao contém a variação percentual entre
        o maior e o menor score para cada dimensão comparada.

        Args:
            campaign_ids: Lista de UUIDs de campanhas (máximo 3).
            dimensao: Filtro opcional por dimensão HSE-IT.
            unidade_id: Filtro opcional por unidade organizacional.

        Returns:
            Dicionário com:
            - campaigns: lista de scores por campanha+dimensão
            - delta_por_dimensao: variação percentual entre campanhas

        Raises:
            ValueError: Se mais de 3 campanhas forem fornecidas.
        """
        if len(campaign_ids) > _MAX_CAMPANHAS_COMPARE:
            raise ValueError(
                f"Comparativo suporta no máximo {_MAX_CAMPANHAS_COMPARE} campanhas. "
                f"Recebido: {len(campaign_ids)}"
            )

        # Validar dimensao se fornecida
        dimensao_enum: Optional[DimensaoHSE] = None
        if dimensao is not None:
            try:
                dimensao_enum = DimensaoHSE(dimensao)
            except ValueError:
                pass

        # Construir filtros
        base_filters = [FactScoreDimensao.campaign_id.in_(campaign_ids)]
        if dimensao_enum is not None:
            base_filters.append(FactScoreDimensao.dimensao == dimensao_enum)
        if unidade_id is not None:
            base_filters.append(FactScoreDimensao.unidade_id == unidade_id)

        # Buscar scores agregados por campanha + dimensão
        stmt = (
            select(
                FactScoreDimensao.campaign_id,
                Campaign.nome.label("campaign_nome"),
                FactScoreDimensao.dimensao,
                func.avg(FactScoreDimensao.score_medio).label("score_campanha"),
                func.count(
                    func.distinct(FactScoreDimensao.setor_id)
                ).label("total_setores"),
            )
            .join(Campaign, FactScoreDimensao.campaign_id == Campaign.id)
            .where(*base_filters)
            .group_by(
                FactScoreDimensao.campaign_id,
                Campaign.nome,
                FactScoreDimensao.dimensao,
            )
            .order_by(FactScoreDimensao.campaign_id, FactScoreDimensao.dimensao)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        score_service = ScoreService()

        # Montar lista campaigns (flat) e calcular delta por dimensão
        campaigns: list[dict[str, Any]] = []
        # Agrupa scores por dimensão para calcular delta: {dimensao: [scores]}
        scores_por_dimensao: dict[str, list[dict[str, Any]]] = {}

        for row in rows:
            score = Decimal(str(row.score_campanha)).quantize(Decimal("0.01"))
            nivel = score_service.calcular_nivel_risco(score)
            item: dict[str, Any] = {
                "campaign_id": str(row.campaign_id),
                "campaign_nome": row.campaign_nome,
                "dimensao": row.dimensao.value,
                "score_campanha": float(score),
                "nivel_risco": nivel.value,
                "total_setores": int(row.total_setores or 0),
            }
            campaigns.append(item)

            dim_key = row.dimensao.value
            if dim_key not in scores_por_dimensao:
                scores_por_dimensao[dim_key] = []
            scores_por_dimensao[dim_key].append(
                {
                    "campaign_id": str(row.campaign_id),
                    "campaign_nome": row.campaign_nome,
                    "score_campanha": float(score),
                    "nivel_risco": nivel.value,
                }
            )

        # Calcular delta percentual por dimensão
        delta_por_dimensao: list[dict[str, Any]] = []
        for dim_key, dim_scores in scores_por_dimensao.items():
            valores = [s["score_campanha"] for s in dim_scores]
            score_max = max(valores)
            score_min = min(valores)
            # Variação percentual relativa ao score mínimo (evita divisão por zero)
            if score_min > 0:
                variacao_percentual = round((score_max - score_min) / score_min * 100, 2)
            else:
                variacao_percentual = 0.0

            delta_por_dimensao.append(
                {
                    "dimensao": dim_key,
                    "scores_por_campanha": dim_scores,
                    "variacao_percentual": variacao_percentual,
                }
            )

        # Ordenar delta por variação descendente (dimensões mais divergentes primeiro)
        delta_por_dimensao.sort(key=lambda d: d["variacao_percentual"], reverse=True)

        return {
            "campaigns": campaigns,
            "delta_por_dimensao": delta_por_dimensao,
        }

    async def get_trends(
        self, company_id: UUID
    ) -> list[dict[str, Any]]:
        """Retorna evolução temporal do score geral por campanha da empresa.

        Cada ponto da tendência representa o score médio geral de uma campanha,
        ordenado por data_inicio. Usado para o gráfico de linha no relatório
        executivo — todos os dados vêm de fact_score_dimensao (Regra R3).

        Args:
            company_id: UUID da empresa.

        Returns:
            Lista de dicionários ordenada por data_inicio ASC com:
            - campaign_id, campaign_nome, data_inicio, score_geral, nivel_geral.
        """
        stmt = (
            select(
                Campaign.id.label("campaign_id"),
                Campaign.nome.label("campaign_nome"),
                Campaign.data_inicio,
                func.avg(FactScoreDimensao.score_medio).label("score_geral"),
            )
            .join(FactScoreDimensao, FactScoreDimensao.campaign_id == Campaign.id)
            .where(Campaign.company_id == company_id)
            .group_by(Campaign.id, Campaign.nome, Campaign.data_inicio)
            .order_by(Campaign.data_inicio.asc())
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        score_service = ScoreService()
        trends: list[dict[str, Any]] = []
        for row in rows:
            score = Decimal(str(row.score_geral)).quantize(Decimal("0.01"))
            nivel = score_service.calcular_nivel_risco(score)
            trends.append(
                {
                    "campaign_id": str(row.campaign_id),
                    "campaign_nome": row.campaign_nome,
                    "data_inicio": row.data_inicio.isoformat(),
                    "score_geral": float(score),
                    "nivel_geral": nivel.value,
                }
            )

        return trends
