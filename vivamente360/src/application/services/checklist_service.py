"""Service do módulo de Checklist NR-1.

Regra R2: Services orquestram — não acessam Infrastructure diretamente.
Regra R1: Type hints completos em todos os métodos e parâmetros.
"""
import math
from typing import Any, Optional
from uuid import UUID

from src.infrastructure.database.models.checklist_item import ChecklistItem
from src.infrastructure.database.models.file_asset import FileAsset
from src.infrastructure.repositories.checklist_repository import ChecklistRepository
from src.shared.exceptions import ForbiddenError, NotFoundError


class ChecklistService:
    """Orquestra as operações do módulo de Checklist NR-1.

    Responsável por:
    - Listagem paginada de itens com progresso (GET /checklists/{campaign_id})
    - Toggle de conclusão com registro de auditoria (PATCH /items/{id}/toggle)
    - Gestão de evidências via file_assets (GET/POST/DELETE /items/{id}/evidencias)
    - Criação automática de itens a partir de templates (hook no CampaignService)
    """

    def __init__(self, checklist_repo: ChecklistRepository) -> None:
        self._checklist_repo = checklist_repo

    async def get_checklist(
        self,
        campaign_id: UUID,
        categoria: Optional[str] = None,
        concluido: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Retorna os itens do checklist com progresso e metadados de paginação.

        Args:
            campaign_id: UUID da campanha a consultar.
            categoria: Filtro opcional por categoria NR-1.
            concluido: Filtro opcional por status de conclusão.
            page: Número da página (1-indexed, padrão 1).
            page_size: Itens por página (máximo 100, padrão 50).

        Returns:
            Dict com 'items', 'progresso' e 'pagination'.
        """
        items, total = await self._checklist_repo.get_by_campaign(
            campaign_id=campaign_id,
            categoria=categoria,
            concluido=concluido,
            page=page,
            page_size=page_size,
        )

        # Progresso calculado sobre o total da campanha (sem filtro)
        progresso = await self._checklist_repo.get_progresso(campaign_id)

        pages = math.ceil(total / page_size) if total > 0 else 0

        return {
            "items": items,
            "progresso": progresso,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": pages,
            },
        }

    async def toggle_item(
        self,
        item_id: UUID,
        concluido: bool,
        user_id: UUID,
        company_id: UUID,
        observacao: Optional[str] = None,
    ) -> ChecklistItem:
        """Alterna o estado de conclusão de um item do checklist.

        Valida existência do item antes de persistir a alteração.
        O isolamento multi-tenant é garantido pelo RLS no banco.

        Args:
            item_id: UUID do item a ser alterado.
            concluido: Novo estado de conclusão.
            user_id: UUID do usuário que realiza a ação (registrado em concluido_por).
            company_id: UUID da empresa — usado para validar acesso via item.company_id.
            observacao: Observação opcional registrada junto à alteração.

        Returns:
            O ChecklistItem atualizado.

        Raises:
            NotFoundError: Se o item não existir na campanha da empresa.
        """
        item = await self._checklist_repo.get_item_by_id(item_id)
        if item is None:
            raise NotFoundError("ChecklistItem", item_id)

        # Validação de acesso: company_id do item deve coincidir com o da sessão.
        # O RLS já garante isso, mas a validação explícita melhora a mensagem de erro.
        if item.company_id != company_id:
            raise ForbiddenError("Acesso negado ao item de checklist.")

        return await self._checklist_repo.toggle_item(
            item_id=item_id,
            concluido=concluido,
            user_id=user_id,
            observacao=observacao,
        )

    async def get_evidencias(self, item_id: UUID, company_id: UUID) -> list[FileAsset]:
        """Retorna as evidências ativas vinculadas a um item do checklist.

        Args:
            item_id: UUID do item.
            company_id: UUID da empresa — usado para validar acesso.

        Returns:
            Lista de FileAsset ativos (deletado=False).

        Raises:
            NotFoundError: Se o item não existir.
        """
        item = await self._checklist_repo.get_item_by_id(item_id)
        if item is None:
            raise NotFoundError("ChecklistItem", item_id)

        if item.company_id != company_id:
            raise ForbiddenError("Acesso negado ao item de checklist.")

        return await self._checklist_repo.get_evidencias(item_id)

    async def add_evidencia(
        self,
        item_id: UUID,
        company_id: UUID,
        nome_original: str,
        tamanho_bytes: int,
        content_type: str,
        storage_key: str,
        created_by: Optional[UUID] = None,
    ) -> FileAsset:
        """Registra metadados de uma evidência vinculada ao item do checklist.

        O arquivo físico deve ter sido previamente enviado ao Cloudflare R2
        (responsabilidade do Módulo 01 — File Management). Este método apenas
        cria o registro de metadados no banco.

        Args:
            item_id: UUID do item ao qual a evidência será vinculada.
            company_id: UUID da empresa.
            nome_original: Nome original do arquivo.
            tamanho_bytes: Tamanho do arquivo em bytes.
            content_type: MIME type do arquivo.
            storage_key: Chave do arquivo no Cloudflare R2.
            created_by: UUID do usuário que fez o upload.

        Returns:
            O FileAsset criado com id gerado.

        Raises:
            NotFoundError: Se o item não existir.
        """
        item = await self._checklist_repo.get_item_by_id(item_id)
        if item is None:
            raise NotFoundError("ChecklistItem", item_id)

        if item.company_id != company_id:
            raise ForbiddenError("Acesso negado ao item de checklist.")

        return await self._checklist_repo.add_evidencia(
            item_id=item_id,
            company_id=company_id,
            nome_original=nome_original,
            tamanho_bytes=tamanho_bytes,
            content_type=content_type,
            storage_key=storage_key,
            created_by=created_by,
        )

    async def delete_evidencia(
        self,
        item_id: UUID,
        file_id: UUID,
        company_id: UUID,
    ) -> None:
        """Soft delete de uma evidência vinculada ao item.

        Args:
            item_id: UUID do item (usado para validação de acesso).
            file_id: UUID do file_asset a ser marcado como deletado.
            company_id: UUID da empresa.

        Raises:
            NotFoundError: Se o item ou a evidência não existirem.
            ForbiddenError: Se o item não pertencer à empresa.
        """
        item = await self._checklist_repo.get_item_by_id(item_id)
        if item is None:
            raise NotFoundError("ChecklistItem", item_id)

        if item.company_id != company_id:
            raise ForbiddenError("Acesso negado ao item de checklist.")

        deleted = await self._checklist_repo.delete_evidencia(file_id)
        if not deleted:
            raise NotFoundError("FileAsset", file_id)

    async def create_items_from_templates(
        self,
        campaign_id: UUID,
        company_id: UUID,
    ) -> list[ChecklistItem]:
        """Cria os itens do checklist para uma nova campanha a partir dos templates.

        Chamado pelo CampaignService como hook pós-criação de campanha.
        É idempotente — templates já existentes para a campanha são ignorados
        pela constraint única (campaign_id, template_id).

        Args:
            campaign_id: UUID da campanha recém-criada.
            company_id: UUID da empresa dona da campanha.

        Returns:
            Lista de ChecklistItem criados.
        """
        return await self._checklist_repo.create_items_from_templates(
            campaign_id=campaign_id,
            company_id=company_id,
        )
