"""Repositório do módulo de Análise por IA (Módulo 06).

Regra R2: Repositories só persistem — nenhuma regra de negócio aqui.
Regra R1: Type hints completos em todos os métodos.
Regra R4: get_by_campaign() retorna tupla (items, total) para paginação obrigatória.
"""
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.ai_analysis import AiAnalysis

# Limite máximo de itens por página — Regra R4
_PAGE_SIZE_MAX: int = 100


class AiAnalysisRepository(ABC):
    """Interface abstrata do repositório de Análise por IA."""

    @abstractmethod
    async def create(
        self,
        company_id: UUID,
        campaign_id: UUID,
        tipo: str,
        setor_id: Optional[UUID] = None,
        dimensao: Optional[str] = None,
    ) -> AiAnalysis:
        """Cria e persiste um novo registro de análise com status 'pending'.

        Returns:
            AiAnalysis criada com id gerado e status inicial 'pending'.
        """
        ...

    @abstractmethod
    async def get_by_id(self, analysis_id: UUID) -> Optional[AiAnalysis]:
        """Busca análise pelo UUID.

        Returns:
            AiAnalysis encontrada ou None se não existir.
        """
        ...

    @abstractmethod
    async def update_status(
        self,
        analysis_id: UUID,
        status: str,
        erro: Optional[str] = None,
    ) -> None:
        """Atualiza o status de uma análise (ex: 'processing', 'failed').

        Args:
            analysis_id: UUID da análise a atualizar.
            status: Novo status ('pending'|'processing'|'completed'|'failed').
            erro: Mensagem de erro, preenchida apenas quando status='failed'.
        """
        ...

    @abstractmethod
    async def update_resultado(
        self,
        analysis_id: UUID,
        resultado: dict[str, Any],
        model_usado: str,
        tokens_input: int,
        tokens_output: int,
        prompt_versao: str,
    ) -> None:
        """Persiste o resultado da análise de IA e marca como 'completed'.

        Args:
            analysis_id: UUID da análise.
            resultado: JSONB validado com o output estruturado da IA.
            model_usado: ID do modelo que gerou o resultado.
            tokens_input: Tokens consumidos no prompt.
            tokens_output: Tokens gerados na resposta.
            prompt_versao: Versão do template de prompt utilizado.
        """
        ...

    @abstractmethod
    async def get_by_campaign(
        self,
        campaign_id: UUID,
        page: int = 1,
        page_size: int = 20,
        tipo: Optional[str] = None,
        status: Optional[str] = None,
    ) -> tuple[list[AiAnalysis], int]:
        """Lista análises de uma campanha com paginação.

        Args:
            campaign_id: UUID da campanha.
            page: Número da página (1-indexed).
            page_size: Itens por página (máximo 100).
            tipo: Filtro opcional por tipo de análise.
            status: Filtro opcional por status.

        Returns:
            Tupla (items, total) com análises paginadas e total geral.
        """
        ...

    @abstractmethod
    async def count_by_company_last_hour(self, company_id: UUID) -> int:
        """Conta análises criadas pela empresa na última hora.

        Usado pelo handler para aplicar rate limiting antes de iniciar
        o processamento de IA.

        Args:
            company_id: UUID da empresa.

        Returns:
            Número de análises criadas nos últimos 60 minutos.
        """
        ...

    @abstractmethod
    async def get_completed_by_campaign(
        self,
        campaign_id: UUID,
    ) -> list[AiAnalysis]:
        """Retorna todas as análises concluídas de uma campanha.

        Usado pelo endpoint /summary para agregar resultados.

        Returns:
            Lista de AiAnalysis com status='completed'.
        """
        ...


class SQLAiAnalysisRepository(AiAnalysisRepository):
    """Implementação SQLAlchemy 2.x do repositório de Análise por IA."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        company_id: UUID,
        campaign_id: UUID,
        tipo: str,
        setor_id: Optional[UUID] = None,
        dimensao: Optional[str] = None,
    ) -> AiAnalysis:
        """Cria registro de análise com status inicial 'pending'."""
        analysis = AiAnalysis(
            id=uuid.uuid4(),
            company_id=company_id,
            campaign_id=campaign_id,
            setor_id=setor_id,
            dimensao=dimensao,
            tipo=tipo,
            status="pending",
        )
        self._session.add(analysis)
        await self._session.flush()
        return analysis

    async def get_by_id(self, analysis_id: UUID) -> Optional[AiAnalysis]:
        """Busca análise pelo UUID, retorna None se não existir."""
        result = await self._session.execute(
            select(AiAnalysis).where(AiAnalysis.id == analysis_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        analysis_id: UUID,
        status: str,
        erro: Optional[str] = None,
    ) -> None:
        """Atualiza o status e, opcionalmente, a mensagem de erro."""
        values: dict[str, Any] = {"status": status}
        if erro is not None:
            values["erro"] = erro

        await self._session.execute(
            update(AiAnalysis)
            .where(AiAnalysis.id == analysis_id)
            .values(**values)
        )
        await self._session.flush()

    async def update_resultado(
        self,
        analysis_id: UUID,
        resultado: dict[str, Any],
        model_usado: str,
        tokens_input: int,
        tokens_output: int,
        prompt_versao: str,
    ) -> None:
        """Persiste o resultado e marca a análise como 'completed'."""
        await self._session.execute(
            update(AiAnalysis)
            .where(AiAnalysis.id == analysis_id)
            .values(
                status="completed",
                resultado=resultado,
                model_usado=model_usado,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                prompt_versao=prompt_versao,
                erro=None,
            )
        )
        await self._session.flush()

    async def get_by_campaign(
        self,
        campaign_id: UUID,
        page: int = 1,
        page_size: int = 20,
        tipo: Optional[str] = None,
        status: Optional[str] = None,
    ) -> tuple[list[AiAnalysis], int]:
        """Lista análises paginadas da campanha com filtros opcionais."""
        page_size = min(page_size, _PAGE_SIZE_MAX)
        offset = (page - 1) * page_size

        base_stmt = select(AiAnalysis).where(
            AiAnalysis.campaign_id == campaign_id
        )

        if tipo is not None:
            base_stmt = base_stmt.where(AiAnalysis.tipo == tipo)

        if status is not None:
            base_stmt = base_stmt.where(AiAnalysis.status == status)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        items_stmt = (
            base_stmt
            .order_by(AiAnalysis.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items_result = await self._session.execute(items_stmt)
        items: list[AiAnalysis] = list(items_result.scalars().all())

        return items, total

    async def count_by_company_last_hour(self, company_id: UUID) -> int:
        """Conta análises da empresa criadas nos últimos 60 minutos."""
        one_hour_ago: datetime = datetime.now(tz=timezone.utc) - timedelta(hours=1)

        result = await self._session.execute(
            select(func.count(AiAnalysis.id)).where(
                AiAnalysis.company_id == company_id,
                AiAnalysis.created_at >= one_hour_ago,
            )
        )
        return int(result.scalar_one())

    async def get_completed_by_campaign(
        self,
        campaign_id: UUID,
    ) -> list[AiAnalysis]:
        """Retorna análises concluídas da campanha, ordenadas por data."""
        result = await self._session.execute(
            select(AiAnalysis)
            .where(
                AiAnalysis.campaign_id == campaign_id,
                AiAnalysis.status == "completed",
            )
            .order_by(AiAnalysis.created_at.desc())
        )
        return list(result.scalars().all())
