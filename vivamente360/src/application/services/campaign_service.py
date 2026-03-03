"""Service de campanhas de avaliação psicossocial.

Regra R2: Services orquestram — não acessam Infrastructure diretamente.
Regra R1: Type hints completos em todos os métodos e parâmetros.

Hook principal: create_campaign() cria automaticamente os checklist_items
a partir dos templates ao criar uma nova campanha (Tarefa 07 do Módulo 02).
"""
import math
from datetime import date
from typing import Any
from uuid import UUID

from src.application.services.checklist_service import ChecklistService
from src.infrastructure.database.models.campaign import Campaign
from src.infrastructure.repositories.campaign_repository import CampaignRepository
from src.shared.exceptions import NotFoundError, ValidationError


class CampaignService:
    """Gerencia o ciclo de vida de campanhas de avaliação psicossocial.

    Ao criar uma campanha, dispara automaticamente a geração dos checklist_items
    via ChecklistService (hook Módulo 02 — NR-1 Checklist).
    """

    def __init__(
        self,
        campaign_repo: CampaignRepository,
        checklist_service: ChecklistService,
    ) -> None:
        self._campaign_repo = campaign_repo
        self._checklist_service = checklist_service

    async def create_campaign(
        self,
        company_id: UUID,
        nome: str,
        data_inicio: date,
        data_fim: date,
    ) -> Campaign:
        """Cria uma nova campanha e inicializa seu checklist NR-1.

        Fluxo:
            1. Valida datas (data_fim > data_inicio).
            2. Persiste a campanha com status DRAFT.
            3. Hook: cria todos os checklist_items a partir dos templates ativos.

        Args:
            company_id: UUID da empresa proprietária da campanha.
            nome: Nome descritivo da campanha.
            data_inicio: Data de início do período de avaliação.
            data_fim: Data de encerramento do período de avaliação.

        Returns:
            A Campaign recém-criada (com status DRAFT).

        Raises:
            ValidationError: Se data_fim for anterior ou igual a data_inicio.
        """
        if data_fim <= data_inicio:
            raise ValidationError(
                "A data de encerramento deve ser posterior à data de início.",
                field="data_fim",
            )

        # 1. Cria a campanha
        campaign: Campaign = await self._campaign_repo.create(
            company_id=company_id,
            nome=nome,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

        # 2. Hook: gera automaticamente o checklist NR-1 para a campanha
        await self._checklist_service.create_items_from_templates(
            campaign_id=campaign.id,
            company_id=company_id,
        )

        return campaign

    async def get_campaign(
        self,
        campaign_id: UUID,
        company_id: UUID,
    ) -> Campaign:
        """Retorna uma campanha pelo UUID, validando que pertence à empresa.

        Args:
            campaign_id: UUID da campanha.
            company_id: UUID da empresa autenticada (validação de acesso).

        Returns:
            A Campaign encontrada.

        Raises:
            NotFoundError: Se a campanha não existir ou não pertencer à empresa.
        """
        campaign = await self._campaign_repo.get_by_id(campaign_id)
        if campaign is None or campaign.company_id != company_id:
            raise NotFoundError("Campaign", campaign_id)
        return campaign

    async def list_campaigns(
        self,
        company_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Lista campanhas da empresa com paginação.

        Args:
            company_id: UUID da empresa autenticada.
            page: Número da página (1-indexed, padrão 1).
            page_size: Itens por página (máximo 100, padrão 20).

        Returns:
            Dict com 'items' e 'pagination'.
        """
        campaigns, total = await self._campaign_repo.list_by_company(
            company_id=company_id,
            page=page,
            page_size=page_size,
        )

        pages = math.ceil(total / page_size) if total > 0 else 0

        return {
            "items": campaigns,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": pages,
            },
        }
