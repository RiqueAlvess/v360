"""Service do módulo de Plano de Ação.

Regra R2: Services orquestram — não acessam Infrastructure diretamente.
Regra R1: Type hints completos em todos os métodos e parâmetros.
Regra R6: Notificações via TaskService (NOTIFY_PLAN_COMPLETED) — nunca diretamente.
"""
import math
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.notification_service import NotificationService
from src.domain.enums.action_plan_status import ActionPlanStatus
from src.domain.enums.nivel_risco import NivelRisco
from src.domain.enums.notification_tipo import NotificationTipo
from src.domain.enums.task_queue_type import TaskQueueType
from src.domain.enums.user_role import UserRole
from src.infrastructure.database.models.action_plan import ActionPlan
from src.infrastructure.database.models.file_asset import FileAsset
from src.infrastructure.queue.task_service import TaskService
from src.infrastructure.repositories.action_plan_repository import ActionPlanRepository
from src.shared.exceptions import ForbiddenError, NotFoundError, ValidationError


class ActionPlanService:
    """Orquestra as operações do módulo de Plano de Ação.

    Responsável por:
    - Listagem paginada de planos com resumo por status (GET /action-plans/{campaign_id})
    - Criação de plano vinculado à campanha e dimensão de risco (POST)
    - Leitura de plano individual com evidências (GET /{plan_id})
    - Atualização parcial de campos (PATCH /{plan_id})
    - Transição de status com regra concluido_em (PATCH /{plan_id}/status)
    - Soft delete via status='cancelado' (DELETE /{plan_id})
    - Registro de evidências (POST /{plan_id}/evidencias)
    - Notificação assíncrona ao criador quando plano é concluído
    """

    def __init__(
        self,
        action_plan_repo: ActionPlanRepository,
        db: AsyncSession,
        notification_service: Optional[NotificationService] = None,
    ) -> None:
        self._repo = action_plan_repo
        self._task_service = TaskService(db)
        self._notification_service = notification_service

    async def list_plans(
        self,
        campaign_id: UUID,
        status: Optional[ActionPlanStatus] = None,
        dimensao: Optional[str] = None,
        unidade_id: Optional[UUID] = None,
        nivel_risco: Optional[NivelRisco] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Retorna os planos da campanha paginados com resumo por status.

        O resumo sempre reflete TODOS os planos da campanha (sem filtros),
        enquanto a listagem respeita os filtros aplicados.

        Args:
            campaign_id: UUID da campanha a consultar.
            status: Filtro opcional por status.
            dimensao: Filtro opcional por dimensão HSE-IT.
            unidade_id: Filtro opcional por unidade organizacional.
            nivel_risco: Filtro opcional por nível de risco.
            page: Número da página (1-indexed, padrão 1).
            page_size: Itens por página (máximo 100, padrão 20).

        Returns:
            Dict com 'items', 'resumo' e 'pagination'.
        """
        items, total = await self._repo.list_by_campaign(
            campaign_id=campaign_id,
            status=status,
            dimensao=dimensao,
            unidade_id=unidade_id,
            nivel_risco=nivel_risco,
            page=page,
            page_size=page_size,
        )

        resumo = await self._repo.get_resumo_por_status(campaign_id)
        pages = math.ceil(total / page_size) if total > 0 else 0

        return {
            "items": items,
            "resumo": resumo,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": pages,
            },
        }

    async def create_plan(
        self,
        campaign_id: UUID,
        company_id: UUID,
        titulo: str,
        descricao: str,
        nivel_risco: NivelRisco,
        prazo: Any,
        created_by: UUID,
        user_role: UserRole,
        dimensao: Optional[str] = None,
        unidade_id: Optional[UUID] = None,
        setor_id: Optional[UUID] = None,
        responsavel_id: Optional[UUID] = None,
        responsavel_externo: Optional[str] = None,
    ) -> ActionPlan:
        """Cria um novo plano de ação vinculado à campanha.

        Apenas usuários com role ADMIN ou MANAGER podem criar planos.

        Args:
            campaign_id: UUID da campanha à qual o plano pertence.
            company_id: UUID da empresa dona da campanha.
            titulo: Título descritivo do plano.
            descricao: Descrição detalhada das ações planejadas.
            nivel_risco: Nível de risco da dimensão alvo.
            prazo: Data limite para conclusão do plano.
            created_by: UUID do usuário criador.
            user_role: Role do usuário criador (validação de permissão).
            dimensao: Dimensão HSE-IT vinculada (opcional).
            unidade_id: Unidade organizacional alvo (opcional).
            setor_id: Setor alvo (opcional).
            responsavel_id: Responsável interno pelo plano (opcional).
            responsavel_externo: Nome do responsável externo (opcional).

        Returns:
            O ActionPlan criado.

        Raises:
            ForbiddenError: Se o usuário não for ADMIN ou MANAGER.
        """
        if user_role not in (UserRole.ADMIN, UserRole.MANAGER):
            raise ForbiddenError(
                "Apenas administradores e gestores podem criar planos de ação."
            )

        return await self._repo.create(
            campaign_id=campaign_id,
            company_id=company_id,
            titulo=titulo,
            descricao=descricao,
            nivel_risco=nivel_risco,
            prazo=prazo,
            created_by=created_by,
            dimensao=dimensao,
            unidade_id=unidade_id,
            setor_id=setor_id,
            responsavel_id=responsavel_id,
            responsavel_externo=responsavel_externo,
        )

    async def get_plan(
        self,
        plan_id: UUID,
        company_id: UUID,
    ) -> tuple[ActionPlan, list[FileAsset]]:
        """Retorna um plano de ação com suas evidências.

        Args:
            plan_id: UUID do plano a buscar.
            company_id: UUID da empresa — validação extra de acesso.

        Returns:
            Tupla (ActionPlan, list[FileAsset]) com o plano e suas evidências.

        Raises:
            NotFoundError: Se o plano não existir.
            ForbiddenError: Se o plano não pertencer à empresa.
        """
        plan = await self._repo.get_by_id(plan_id)
        if plan is None:
            raise NotFoundError("ActionPlan", plan_id)

        if plan.company_id != company_id:
            raise ForbiddenError("Acesso negado ao plano de ação.")

        evidencias = await self._repo.get_evidencias(plan_id)
        return plan, evidencias

    async def update_plan(
        self,
        plan_id: UUID,
        company_id: UUID,
        user_role: UserRole,
        titulo: Optional[str] = None,
        descricao: Optional[str] = None,
        dimensao: Optional[str] = None,
        unidade_id: Optional[UUID] = None,
        setor_id: Optional[UUID] = None,
        responsavel_id: Optional[UUID] = None,
        responsavel_externo: Optional[str] = None,
        nivel_risco: Optional[NivelRisco] = None,
        prazo: Optional[Any] = None,
    ) -> ActionPlan:
        """Atualiza campos parciais de um plano de ação.

        Args:
            plan_id: UUID do plano a atualizar.
            company_id: UUID da empresa — validação de acesso.
            user_role: Role do usuário — apenas ADMIN ou MANAGER podem atualizar.
            Demais args: campos opcionais a atualizar.

        Returns:
            O ActionPlan atualizado.

        Raises:
            NotFoundError: Se o plano não existir.
            ForbiddenError: Se o usuário não tiver permissão ou o plano não pertencer à empresa.
            ValidationError: Se o plano estiver cancelado ou concluído.
        """
        if user_role not in (UserRole.ADMIN, UserRole.MANAGER):
            raise ForbiddenError(
                "Apenas administradores e gestores podem atualizar planos de ação."
            )

        plan = await self._repo.get_by_id(plan_id)
        if plan is None:
            raise NotFoundError("ActionPlan", plan_id)

        if plan.company_id != company_id:
            raise ForbiddenError("Acesso negado ao plano de ação.")

        if plan.status in (ActionPlanStatus.CANCELADO, ActionPlanStatus.CONCLUIDO):
            raise ValidationError(
                f"Não é possível editar um plano com status '{plan.status.value}'."
            )

        return await self._repo.update(
            plan_id=plan_id,
            titulo=titulo,
            descricao=descricao,
            dimensao=dimensao,
            unidade_id=unidade_id,
            setor_id=setor_id,
            responsavel_id=responsavel_id,
            responsavel_externo=responsavel_externo,
            nivel_risco=nivel_risco,
            prazo=prazo,
        )

    async def update_status(
        self,
        plan_id: UUID,
        company_id: UUID,
        user_role: UserRole,
        new_status: ActionPlanStatus,
        observacao: Optional[str] = None,
    ) -> ActionPlan:
        """Transiciona o status de um plano de ação.

        Regra: status='concluido' seta concluido_em automaticamente.
        Ao concluir, enfileira notificação assíncrona para o criador do plano.

        Args:
            plan_id: UUID do plano.
            company_id: UUID da empresa — validação de acesso.
            user_role: Role do usuário — apenas ADMIN ou MANAGER.
            new_status: Novo status a aplicar.
            observacao: Observação opcional (registrada no payload da notificação).

        Returns:
            O ActionPlan com status atualizado.

        Raises:
            NotFoundError: Se o plano não existir.
            ForbiddenError: Se o usuário não tiver permissão.
            ValidationError: Se a transição de status for inválida.
        """
        if user_role not in (UserRole.ADMIN, UserRole.MANAGER):
            raise ForbiddenError(
                "Apenas administradores e gestores podem alterar o status de planos de ação."
            )

        plan = await self._repo.get_by_id(plan_id)
        if plan is None:
            raise NotFoundError("ActionPlan", plan_id)

        if plan.company_id != company_id:
            raise ForbiddenError("Acesso negado ao plano de ação.")

        if plan.status == ActionPlanStatus.CANCELADO:
            raise ValidationError("Não é possível alterar o status de um plano cancelado.")

        if plan.status == ActionPlanStatus.CONCLUIDO and new_status != ActionPlanStatus.CANCELADO:
            raise ValidationError(
                "Um plano concluído só pode ser cancelado. "
                "Para reabrir, use um novo plano."
            )

        concluido_em: Optional[datetime] = None
        if new_status == ActionPlanStatus.CONCLUIDO:
            concluido_em = datetime.now(tz=timezone.utc)

        updated_plan = await self._repo.update_status(
            plan_id=plan_id,
            status=new_status,
            concluido_em=concluido_em,
        )

        # Regra do módulo: ao concluir um plano, enfileirar notificação por email
        if new_status == ActionPlanStatus.CONCLUIDO:
            await self._task_service.enqueue(
                tipo=TaskQueueType.NOTIFY_PLAN_COMPLETED,
                payload={
                    "plan_id": str(plan_id),
                    "campaign_id": str(plan.campaign_id),
                    "company_id": str(company_id),
                    "created_by": str(plan.created_by),
                    "titulo": plan.titulo,
                    "observacao": observacao,
                    "concluido_em": concluido_em.isoformat() if concluido_em else None,
                },
            )

            # Notificação in-app para o criador do plano (Módulo 08)
            if self._notification_service is not None:
                responsavel_id = plan.responsavel_id or plan.created_by
                await self._notification_service.notify(
                    company_id=company_id,
                    user_id=responsavel_id,
                    tipo=NotificationTipo.RELATORIO_PRONTO,
                    titulo="Plano de ação concluído",
                    mensagem=f"O plano '{plan.titulo}' foi marcado como concluído.",
                    link=f"/action-plans/{plan.campaign_id}/{plan_id}",
                    metadata={
                        "plan_id": str(plan_id),
                        "campaign_id": str(plan.campaign_id),
                    },
                )

        return updated_plan

    async def cancel_plan(
        self,
        plan_id: UUID,
        company_id: UUID,
        user_role: UserRole,
    ) -> None:
        """Soft delete de um plano de ação (status='cancelado').

        Args:
            plan_id: UUID do plano a cancelar.
            company_id: UUID da empresa — validação de acesso.
            user_role: Role do usuário — apenas ADMIN ou MANAGER.

        Raises:
            NotFoundError: Se o plano não existir.
            ForbiddenError: Se o usuário não tiver permissão.
            ValidationError: Se o plano já estiver cancelado.
        """
        if user_role not in (UserRole.ADMIN, UserRole.MANAGER):
            raise ForbiddenError(
                "Apenas administradores e gestores podem cancelar planos de ação."
            )

        plan = await self._repo.get_by_id(plan_id)
        if plan is None:
            raise NotFoundError("ActionPlan", plan_id)

        if plan.company_id != company_id:
            raise ForbiddenError("Acesso negado ao plano de ação.")

        if plan.status == ActionPlanStatus.CANCELADO:
            raise ValidationError("O plano já está cancelado.")

        await self._repo.update_status(
            plan_id=plan_id,
            status=ActionPlanStatus.CANCELADO,
        )

    async def add_evidencia(
        self,
        plan_id: UUID,
        company_id: UUID,
        nome_original: str,
        tamanho_bytes: int,
        content_type: str,
        storage_key: str,
        created_by: Optional[UUID] = None,
    ) -> FileAsset:
        """Registra metadados de uma evidência vinculada ao plano.

        O arquivo físico deve ter sido previamente enviado ao Cloudflare R2.

        Args:
            plan_id: UUID do plano ao qual a evidência será vinculada.
            company_id: UUID da empresa.
            nome_original: Nome original do arquivo.
            tamanho_bytes: Tamanho do arquivo em bytes.
            content_type: MIME type do arquivo.
            storage_key: Chave do arquivo no Cloudflare R2.
            created_by: UUID do usuário que fez o upload.

        Returns:
            O FileAsset criado.

        Raises:
            NotFoundError: Se o plano não existir.
            ForbiddenError: Se o plano não pertencer à empresa.
        """
        plan = await self._repo.get_by_id(plan_id)
        if plan is None:
            raise NotFoundError("ActionPlan", plan_id)

        if plan.company_id != company_id:
            raise ForbiddenError("Acesso negado ao plano de ação.")

        return await self._repo.add_evidencia(
            plan_id=plan_id,
            company_id=company_id,
            nome_original=nome_original,
            tamanho_bytes=tamanho_bytes,
            content_type=content_type,
            storage_key=storage_key,
            created_by=created_by,
        )
