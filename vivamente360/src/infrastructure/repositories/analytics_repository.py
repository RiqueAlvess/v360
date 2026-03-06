"""Repositório para persistência e leitura das tabelas do Modelo Estrela.

Responsabilidades:
- Upsert de fact_score_dimensao (idempotente via ON CONFLICT DO UPDATE).
- Buscar ou criar entradas em dim_tempo e dim_estrutura.
- Agregação de dados para o dashboard (summary e heatmap).

Regra R3: Todos os dados lidos aqui vêm de fact_score_dimensao.
Zero cálculos de score — apenas leitura de dados pré-computados.
"""
import uuid
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.dimensao_hse import DimensaoHSE
from src.domain.enums.nivel_risco import NivelRisco
from src.infrastructure.database.models.dim_estrutura import DimEstrutura
from src.infrastructure.database.models.dim_tempo import DimTempo
from src.infrastructure.database.models.fact_score_dimensao import FactScoreDimensao


class AnalyticsRepository(ABC):
    """Interface abstrata do repositório de analytics."""

    @abstractmethod
    async def get_or_create_dim_tempo(self, data: date) -> DimTempo:
        """Busca ou cria o registro dim_tempo para a data informada."""
        ...

    @abstractmethod
    async def get_or_create_dim_estrutura(
        self,
        company_id: UUID,
        unidade_id: Optional[UUID] = None,
        setor_id: Optional[UUID] = None,
        cargo_id: Optional[UUID] = None,
        unidade_nome: Optional[str] = None,
        setor_nome: Optional[str] = None,
        cargo_nome: Optional[str] = None,
    ) -> DimEstrutura:
        """Busca ou cria o registro dim_estrutura para a combinação informada."""
        ...

    @abstractmethod
    async def upsert_fact_score(
        self,
        campaign_id: UUID,
        dim_tempo_id: UUID,
        dim_estrutura_id: UUID,
        dimensao: DimensaoHSE,
        score_medio: Decimal,
        nivel_risco: NivelRisco,
        total_respostas: int,
        sentimento_score_medio: Optional[Decimal] = None,
        unidade_id: Optional[UUID] = None,
        setor_id: Optional[UUID] = None,
        cargo_id: Optional[UUID] = None,
    ) -> None:
        """Insere ou atualiza um registro em fact_score_dimensao (idempotente)."""
        ...

    @abstractmethod
    async def get_dashboard_summary(
        self, campaign_id: UUID
    ) -> dict[str, Any]:
        """Agrega métricas globais da campanha a partir de fact_score_dimensao."""
        ...

    @abstractmethod
    async def get_dimensoes_scores(
        self, campaign_id: UUID
    ) -> list[dict[str, Any]]:
        """Retorna score e nível de risco para cada dimensão HSE-IT da campanha."""
        ...

    @abstractmethod
    async def get_heatmap(
        self,
        campaign_id: UUID,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Retorna matriz setor×dimensão com scores paginada."""
        ...

    @abstractmethod
    async def get_score_by_dimension(
        self,
        campaign_id: UUID,
        dimensao: DimensaoHSE,
    ) -> Optional[dict[str, Any]]:
        """Retorna score e nível de risco de uma dimensão HSE-IT específica.

        Lê exclusivamente de fact_score_dimensao — zero cálculos (Regra R3).

        Args:
            campaign_id: UUID da campanha.
            dimensao: Dimensão HSE-IT a consultar.

        Returns:
            Dicionário com dimensao, score_medio, nivel_risco e total_respostas,
            ou None se não houver dados computados para a dimensão.
        """
        ...

    @abstractmethod
    async def get_historical_scores(
        self,
        campaign_id: UUID,
        data_inicio: date,
        data_fim: date,
    ) -> list[dict[str, Any]]:
        """Retorna séries históricas de scores por dimensão em um período.

        Agrupa os registros fact por data (dim_tempo.data) e dimensão,
        permitindo visualizar a evolução temporal dos scores da campanha.

        Lê exclusivamente de fact_score_dimensao + dim_tempo (Regra R3).

        Args:
            campaign_id: UUID da campanha.
            data_inicio: Data inicial do período (inclusiva).
            data_fim: Data final do período (inclusiva).

        Returns:
            Lista de dicionários com data, dimensao, score_medio e total_respostas,
            ordenados por data e dimensão.
        """
        ...

    @abstractmethod
    async def get_top_risk_sectors(
        self,
        campaign_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retorna os setores com maior nível de risco psicossocial.

        Agrega scores por dim_estrutura e dimensão, ranqueando pelo score
        médio mais baixo (menor score = maior risco).

        Lê exclusivamente de fact_score_dimensao + dim_estrutura (Regra R3).

        Args:
            campaign_id: UUID da campanha.
            limit: Número máximo de setores a retornar (padrão 10).

        Returns:
            Lista de dicionários com setor_nome, score_medio, nivel_risco e
            total_respostas, ordenados por score_medio ascendente (maior risco primeiro).
        """
        ...


class SQLAnalyticsRepository(AnalyticsRepository):
    """Implementação SQLAlchemy do repositório de analytics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_dim_tempo(self, data: date) -> DimTempo:
        """Busca ou cria o registro dim_tempo para a data informada.

        Args:
            data: Data de referência para a dimensão temporal.

        Returns:
            Registro DimTempo existente ou recém-criado.
        """
        result = await self._session.execute(
            select(DimTempo).where(DimTempo.data == data)
        )
        dim = result.scalar_one_or_none()
        if dim:
            return dim

        # Calcular componentes temporais para a nova entrada
        trimestre = (data.month - 1) // 3 + 1
        # isoweekday(): 1=Segunda, 7=Domingo — isocalendar()[2] retorna igual
        dia_semana = data.isoweekday()
        semana_ano = data.isocalendar()[1]

        dim = DimTempo(
            id=uuid.uuid4(),
            data=data,
            ano=data.year,
            mes=data.month,
            dia=data.day,
            trimestre=trimestre,
            dia_semana=dia_semana,
            semana_ano=semana_ano,
        )
        self._session.add(dim)
        await self._session.flush()
        return dim

    async def get_or_create_dim_estrutura(
        self,
        company_id: UUID,
        unidade_id: Optional[UUID] = None,
        setor_id: Optional[UUID] = None,
        cargo_id: Optional[UUID] = None,
        unidade_nome: Optional[str] = None,
        setor_nome: Optional[str] = None,
        cargo_nome: Optional[str] = None,
    ) -> DimEstrutura:
        """Busca ou cria dim_estrutura para a combinação exata de chaves.

        Args:
            company_id: UUID da empresa (obrigatório).
            unidade_id: UUID da unidade organizacional (opcional).
            setor_id: UUID do setor (opcional).
            cargo_id: UUID do cargo (opcional).
            unidade_nome: Snapshot do nome da unidade.
            setor_nome: Snapshot do nome do setor.
            cargo_nome: Snapshot do nome do cargo.

        Returns:
            Registro DimEstrutura existente ou recém-criado.
        """
        stmt = select(DimEstrutura).where(DimEstrutura.company_id == company_id)

        if unidade_id is not None:
            stmt = stmt.where(DimEstrutura.unidade_id == unidade_id)
        else:
            stmt = stmt.where(DimEstrutura.unidade_id.is_(None))

        if setor_id is not None:
            stmt = stmt.where(DimEstrutura.setor_id == setor_id)
        else:
            stmt = stmt.where(DimEstrutura.setor_id.is_(None))

        if cargo_id is not None:
            stmt = stmt.where(DimEstrutura.cargo_id == cargo_id)
        else:
            stmt = stmt.where(DimEstrutura.cargo_id.is_(None))

        result = await self._session.execute(stmt)
        dim = result.scalar_one_or_none()
        if dim:
            return dim

        dim = DimEstrutura(
            id=uuid.uuid4(),
            company_id=company_id,
            unidade_id=unidade_id,
            setor_id=setor_id,
            cargo_id=cargo_id,
            unidade_nome=unidade_nome,
            setor_nome=setor_nome,
            cargo_nome=cargo_nome,
        )
        self._session.add(dim)
        await self._session.flush()
        return dim

    async def upsert_fact_score(
        self,
        campaign_id: UUID,
        dim_tempo_id: UUID,
        dim_estrutura_id: UUID,
        dimensao: DimensaoHSE,
        score_medio: Decimal,
        nivel_risco: NivelRisco,
        total_respostas: int,
        sentimento_score_medio: Optional[Decimal] = None,
        unidade_id: Optional[UUID] = None,
        setor_id: Optional[UUID] = None,
        cargo_id: Optional[UUID] = None,
    ) -> None:
        """Insere ou atualiza fact_score_dimensao usando INSERT ... ON CONFLICT DO UPDATE.

        Idempotente: pode ser executado múltiplas vezes para a mesma combinação de
        (campaign_id, dim_tempo_id, dim_estrutura_id, dimensao) sem duplicar dados.

        Args:
            campaign_id: UUID da campanha.
            dim_tempo_id: UUID da dimensão temporal.
            dim_estrutura_id: UUID da dimensão estrutural.
            dimensao: Dimensão HSE-IT calculada.
            score_medio: Score médio calculado para a dimensão.
            nivel_risco: Nível de risco classificado pelo ScoreService.
            total_respostas: Número de respostas que compõem o cálculo.
            sentimento_score_medio: Média dos scores de sentimento das respostas
                com texto livre analisado. NULL quando nenhuma resposta tem sentimento.
            unidade_id: UUID da unidade organizacional (desnormalizado de dim_estrutura).
            setor_id: UUID do setor (desnormalizado de dim_estrutura).
            cargo_id: UUID do cargo (desnormalizado de dim_estrutura).
        """
        stmt = pg_insert(FactScoreDimensao).values(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            dim_tempo_id=dim_tempo_id,
            dim_estrutura_id=dim_estrutura_id,
            dimensao=dimensao,
            score_medio=score_medio,
            nivel_risco=nivel_risco,
            total_respostas=total_respostas,
            sentimento_score_medio=sentimento_score_medio,
            computed_at=sa.func.now(),
            unidade_id=unidade_id,
            setor_id=setor_id,
            cargo_id=cargo_id,
        )
        # ON CONFLICT: atualiza score, risco, total, sentimento, campos de filtro e computed_at
        stmt = stmt.on_conflict_do_update(
            constraint="uq_fact_score_dimensao",
            set_={
                "score_medio": stmt.excluded.score_medio,
                "nivel_risco": stmt.excluded.nivel_risco,
                "total_respostas": stmt.excluded.total_respostas,
                "sentimento_score_medio": stmt.excluded.sentimento_score_medio,
                "unidade_id": stmt.excluded.unidade_id,
                "setor_id": stmt.excluded.setor_id,
                "cargo_id": stmt.excluded.cargo_id,
                "computed_at": sa.func.now(),
            },
        )
        await self._session.execute(stmt)

    async def get_dashboard_summary(
        self, campaign_id: UUID
    ) -> dict[str, Any]:
        """Agrega métricas globais da campanha diretamente de fact_score_dimensao.

        Retorna total de respostas, índice geral e nível geral. Zero cálculos
        de score — apenas agregação de dados pré-computados.

        Args:
            campaign_id: UUID da campanha.

        Returns:
            Dicionário com total_respostas, indice_geral e nivel_geral.
        """
        stmt = (
            select(
                func.sum(FactScoreDimensao.total_respostas).label("total_respostas"),
                func.avg(FactScoreDimensao.score_medio).label("indice_geral"),
            )
            .where(FactScoreDimensao.campaign_id == campaign_id)
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()

        total_respostas: int = int(row.total_respostas or 0) if row else 0
        indice_geral: Decimal = (
            Decimal(str(row.indice_geral)).quantize(Decimal("0.01"))
            if row and row.indice_geral
            else Decimal("0.00")
        )

        # Classificar nível geral usando os mesmos thresholds do ScoreService
        from src.application.services.score_service import (
            THRESHOLD_ACEITAVEL,
            THRESHOLD_IMPORTANTE,
            THRESHOLD_MODERADO,
        )

        if indice_geral >= THRESHOLD_ACEITAVEL:
            nivel_geral = NivelRisco.ACEITAVEL.value
        elif indice_geral >= THRESHOLD_MODERADO:
            nivel_geral = NivelRisco.MODERADO.value
        elif indice_geral >= THRESHOLD_IMPORTANTE:
            nivel_geral = NivelRisco.IMPORTANTE.value
        else:
            nivel_geral = NivelRisco.CRITICO.value

        return {
            "total_respostas": total_respostas,
            "indice_geral": float(indice_geral),
            "nivel_geral": nivel_geral,
        }

    async def get_dimensoes_scores(
        self, campaign_id: UUID
    ) -> list[dict[str, Any]]:
        """Retorna score e nível de risco para cada dimensão HSE-IT da campanha.

        Agrega múltiplos registros fact (de diferentes estruturas e datas) em
        um score médio por dimensão.

        Args:
            campaign_id: UUID da campanha.

        Returns:
            Lista de dicionários com dimensao, score_medio, nivel_risco e total_respostas.
        """
        stmt = (
            select(
                FactScoreDimensao.dimensao,
                func.avg(FactScoreDimensao.score_medio).label("score_medio"),
                func.sum(FactScoreDimensao.total_respostas).label("total_respostas"),
            )
            .where(FactScoreDimensao.campaign_id == campaign_id)
            .group_by(FactScoreDimensao.dimensao)
            .order_by(FactScoreDimensao.dimensao)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        from src.application.services.score_service import ScoreService
        score_service = ScoreService()

        dimensoes: list[dict[str, Any]] = []
        for row in rows:
            score = Decimal(str(row.score_medio)).quantize(Decimal("0.01"))
            nivel = score_service.calcular_nivel_risco(score)
            dimensoes.append(
                {
                    "dimensao": row.dimensao.value,
                    "score_medio": float(score),
                    "nivel_risco": nivel.value,
                    "total_respostas": int(row.total_respostas or 0),
                }
            )

        return dimensoes

    async def get_heatmap(
        self,
        campaign_id: UUID,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Retorna matriz setor×dimensão com scores paginados por dim_estrutura.

        Cada célula representa o score médio de uma dimensão para uma estrutura
        organizacional específica (empresa/unidade/setor).

        Args:
            campaign_id: UUID da campanha.
            page: Página atual (1-indexed).
            page_size: Quantidade de estruturas por página.

        Returns:
            Tupla (lista_de_células_heatmap, total_de_estruturas).
        """
        # Contar total de dim_estruturas distintas com dados para esta campanha
        count_stmt = (
            select(func.count(func.distinct(FactScoreDimensao.dim_estrutura_id)))
            .where(FactScoreDimensao.campaign_id == campaign_id)
        )
        count_result = await self._session.execute(count_stmt)
        total: int = count_result.scalar_one() or 0

        if total == 0:
            return [], 0

        # Buscar estruturas distintas com paginação
        offset = (page - 1) * page_size
        estruturas_stmt = (
            select(FactScoreDimensao.dim_estrutura_id)
            .where(FactScoreDimensao.campaign_id == campaign_id)
            .group_by(FactScoreDimensao.dim_estrutura_id)
            .order_by(FactScoreDimensao.dim_estrutura_id)
            .offset(offset)
            .limit(page_size)
        )
        estruturas_result = await self._session.execute(estruturas_stmt)
        estrutura_ids: list[UUID] = [row[0] for row in estruturas_result.all()]

        if not estrutura_ids:
            return [], total

        # Buscar todos os scores para as estruturas paginadas em uma única query
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
            .where(FactScoreDimensao.campaign_id == campaign_id)
            .where(FactScoreDimensao.dim_estrutura_id.in_(estrutura_ids))
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

        from src.application.services.score_service import ScoreService
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

    async def get_score_by_dimension(
        self,
        campaign_id: UUID,
        dimensao: DimensaoHSE,
    ) -> Optional[dict[str, Any]]:
        """Retorna score e nível de risco de uma dimensão HSE-IT específica.

        Agrega múltiplos registros fact (de diferentes estruturas e datas)
        em um único score médio para a dimensão solicitada. Lê exclusivamente
        de fact_score_dimensao — zero cálculos em runtime (Regra R3).

        Args:
            campaign_id: UUID da campanha.
            dimensao: Dimensão HSE-IT a consultar.

        Returns:
            Dicionário com dimensao, score_medio, nivel_risco e total_respostas,
            ou None se não houver dados computados para a dimensão.
        """
        stmt = (
            select(
                FactScoreDimensao.dimensao,
                func.avg(FactScoreDimensao.score_medio).label("score_medio"),
                func.sum(FactScoreDimensao.total_respostas).label("total_respostas"),
            )
            .where(FactScoreDimensao.campaign_id == campaign_id)
            .where(FactScoreDimensao.dimensao == dimensao)
            .group_by(FactScoreDimensao.dimensao)
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()

        if row is None or row.score_medio is None:
            return None

        from src.application.services.score_service import ScoreService

        score = Decimal(str(row.score_medio)).quantize(Decimal("0.01"))
        nivel = ScoreService().calcular_nivel_risco(score)

        return {
            "dimensao": dimensao.value,
            "score_medio": float(score),
            "nivel_risco": nivel.value,
            "total_respostas": int(row.total_respostas or 0),
        }

    async def get_historical_scores(
        self,
        campaign_id: UUID,
        data_inicio: date,
        data_fim: date,
    ) -> list[dict[str, Any]]:
        """Retorna séries históricas de scores por dimensão em um período.

        Agrupa os registros fact por data (dim_tempo.data) e dimensão,
        permitindo visualizar a evolução temporal dos scores. Lê exclusivamente
        de fact_score_dimensao + dim_tempo (Regra R3).

        Args:
            campaign_id: UUID da campanha.
            data_inicio: Data inicial do período (inclusiva).
            data_fim: Data final do período (inclusiva).

        Returns:
            Lista de dicionários com data, dimensao, score_medio e total_respostas,
            ordenados por data ascendente e dimensão.
        """
        stmt = (
            select(
                DimTempo.data,
                FactScoreDimensao.dimensao,
                func.avg(FactScoreDimensao.score_medio).label("score_medio"),
                func.sum(FactScoreDimensao.total_respostas).label("total_respostas"),
            )
            .join(DimTempo, FactScoreDimensao.dim_tempo_id == DimTempo.id)
            .where(FactScoreDimensao.campaign_id == campaign_id)
            .where(DimTempo.data >= data_inicio)
            .where(DimTempo.data <= data_fim)
            .group_by(DimTempo.data, FactScoreDimensao.dimensao)
            .order_by(DimTempo.data, FactScoreDimensao.dimensao)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        historico: list[dict[str, Any]] = []
        for row in rows:
            score = Decimal(str(row.score_medio)).quantize(Decimal("0.01"))
            historico.append(
                {
                    "data": row.data.isoformat(),
                    "dimensao": row.dimensao.value,
                    "score_medio": float(score),
                    "total_respostas": int(row.total_respostas or 0),
                }
            )

        return historico

    async def get_top_risk_sectors(
        self,
        campaign_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Retorna os setores com maior nível de risco psicossocial.

        Agrega scores por dim_estrutura (setor_nome), ranqueando pelo score
        médio mais baixo (menor score = maior risco). Lê exclusivamente de
        fact_score_dimensao + dim_estrutura (Regra R3).

        Args:
            campaign_id: UUID da campanha.
            limit: Número máximo de setores a retornar (padrão 10).

        Returns:
            Lista de dicionários com setor_nome, score_medio, nivel_risco e
            total_respostas, ordenados por score_medio ascendente (maior risco primeiro).
        """
        stmt = (
            select(
                DimEstrutura.setor_nome,
                DimEstrutura.unidade_nome,
                func.avg(FactScoreDimensao.score_medio).label("score_medio"),
                func.sum(FactScoreDimensao.total_respostas).label("total_respostas"),
            )
            .join(DimEstrutura, FactScoreDimensao.dim_estrutura_id == DimEstrutura.id)
            .where(FactScoreDimensao.campaign_id == campaign_id)
            .group_by(DimEstrutura.setor_nome, DimEstrutura.unidade_nome)
            .order_by(sa.asc("score_medio"))
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        from src.application.services.score_service import ScoreService

        score_service = ScoreService()
        setores: list[dict[str, Any]] = []
        for row in rows:
            score = Decimal(str(row.score_medio)).quantize(Decimal("0.01"))
            nivel = score_service.calcular_nivel_risco(score)
            setores.append(
                {
                    "setor_nome": row.setor_nome,
                    "unidade_nome": row.unidade_nome,
                    "score_medio": float(score),
                    "nivel_risco": nivel.value,
                    "total_respostas": int(row.total_respostas or 0),
                }
            )

        return setores
