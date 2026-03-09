"""Testes unitários do ActionPlanService — Blueprint 08.

Cobre:
    - create_plan(): sucesso, permissão negada (RESPONDENT)
    - get_plan(): sucesso, not found, empresa diferente
    - update_plan(): sucesso, plano concluído/cancelado não pode ser editado
    - update_status(): transições válidas, cancelado → erro, concluído → notificação
    - cancel_plan(): sucesso, plano já cancelado → erro
    - list_plans(): paginação, filtros
"""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.action_plan_service import ActionPlanService
from src.domain.enums.action_plan_status import ActionPlanStatus
from src.domain.enums.nivel_risco import NivelRisco
from src.domain.enums.user_role import UserRole
from src.shared.exceptions import ForbiddenError, NotFoundError, ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
OTHER_COMPANY_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")
CAMPAIGN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
USER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
PLAN_ID = uuid.uuid4()


def _make_fake_plan(
    plan_id: uuid.UUID = None,
    company_id: uuid.UUID = COMPANY_ID,
    campaign_id: uuid.UUID = CAMPAIGN_ID,
    status: ActionPlanStatus = ActionPlanStatus.PENDENTE,
    created_by: uuid.UUID = USER_ID,
    responsavel_id: uuid.UUID = None,
):
    plan = MagicMock()
    plan.id = plan_id or uuid.uuid4()
    plan.company_id = company_id
    plan.campaign_id = campaign_id
    plan.titulo = "Reduzir sobrecarga de trabalho"
    plan.descricao = "Ação para reduzir horas extras excessivas no setor de TI"
    plan.status = status
    plan.nivel_risco = NivelRisco.CRITICO
    plan.prazo = date(2024, 12, 31)
    plan.dimensao = "demandas"
    plan.unidade_id = None
    plan.setor_id = None
    plan.responsavel_id = responsavel_id
    plan.responsavel_externo = None
    plan.concluido_em = None
    plan.created_by = created_by
    plan.created_at = datetime.now(tz=timezone.utc)
    plan.updated_at = datetime.now(tz=timezone.utc)
    return plan


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_action_plan_repo():
    from src.infrastructure.repositories.action_plan_repository import ActionPlanRepository

    repo = AsyncMock(spec=ActionPlanRepository)
    return repo


@pytest.fixture
def mock_notification_service():
    from src.application.services.notification_service import NotificationService

    service = AsyncMock(spec=NotificationService)
    service.notify = AsyncMock()
    service.notify_by_role = AsyncMock()
    return service


@pytest.fixture
def action_plan_service(mock_action_plan_repo, mock_session, mock_notification_service):
    """ActionPlanService com todos os mocks."""
    with MagicMock() as mock_task_service_class:
        service = ActionPlanService(
            action_plan_repo=mock_action_plan_repo,
            db=mock_session,
            notification_service=mock_notification_service,
        )
        # Mock do task_service interno
        service._task_service = AsyncMock()
        service._task_service.enqueue = AsyncMock()
    return service


# ---------------------------------------------------------------------------
# list_plans()
# ---------------------------------------------------------------------------


class TestActionPlanServiceListPlans:
    async def test_list_plans_returns_paginated_result(
        self, action_plan_service, mock_action_plan_repo
    ):
        """list_plans retorna items com resumo e paginação."""
        fake_plans = [_make_fake_plan() for _ in range(3)]
        mock_action_plan_repo.list_by_campaign.return_value = (fake_plans, 3)
        mock_action_plan_repo.get_resumo_por_status.return_value = {
            "total": 3,
            "por_status": {"pendente": 3, "em_andamento": 0, "concluido": 0, "cancelado": 0},
        }

        result = await action_plan_service.list_plans(
            campaign_id=CAMPAIGN_ID, page=1, page_size=20
        )

        assert "items" in result
        assert "resumo" in result
        assert "pagination" in result
        assert len(result["items"]) == 3

    async def test_list_plans_empty_returns_zero_totals(
        self, action_plan_service, mock_action_plan_repo
    ):
        """list_plans sem planos retorna lista vazia."""
        mock_action_plan_repo.list_by_campaign.return_value = ([], 0)
        mock_action_plan_repo.get_resumo_por_status.return_value = {
            "total": 0,
            "por_status": {},
        }

        result = await action_plan_service.list_plans(campaign_id=CAMPAIGN_ID)

        assert result["items"] == []
        assert result["pagination"]["total"] == 0


# ---------------------------------------------------------------------------
# create_plan()
# ---------------------------------------------------------------------------


class TestActionPlanServiceCreatePlan:
    async def test_create_plan_admin_success(
        self, action_plan_service, mock_action_plan_repo
    ):
        """ADMIN pode criar plano de ação."""
        fake_plan = _make_fake_plan()
        mock_action_plan_repo.create.return_value = fake_plan

        result = await action_plan_service.create_plan(
            campaign_id=CAMPAIGN_ID,
            company_id=COMPANY_ID,
            titulo="Reduzir sobrecarga",
            descricao="Ação para reduzir horas extras excessivas",
            nivel_risco=NivelRisco.CRITICO,
            prazo=date(2024, 12, 31),
            created_by=USER_ID,
            user_role=UserRole.ADMIN,
        )

        assert result.id == fake_plan.id
        mock_action_plan_repo.create.assert_called_once()

    async def test_create_plan_manager_success(
        self, action_plan_service, mock_action_plan_repo
    ):
        """MANAGER pode criar plano de ação."""
        fake_plan = _make_fake_plan()
        mock_action_plan_repo.create.return_value = fake_plan

        result = await action_plan_service.create_plan(
            campaign_id=CAMPAIGN_ID,
            company_id=COMPANY_ID,
            titulo="Reduzir sobrecarga",
            descricao="Ação para reduzir horas extras excessivas",
            nivel_risco=NivelRisco.MODERADO,
            prazo=date(2024, 12, 31),
            created_by=USER_ID,
            user_role=UserRole.MANAGER,
        )

        assert result.id == fake_plan.id

    async def test_create_plan_respondent_raises_forbidden(
        self, action_plan_service, mock_action_plan_repo
    ):
        """RESPONDENT não pode criar plano — levanta ForbiddenError."""
        with pytest.raises(ForbiddenError):
            await action_plan_service.create_plan(
                campaign_id=CAMPAIGN_ID,
                company_id=COMPANY_ID,
                titulo="Reduzir sobrecarga",
                descricao="Ação para reduzir horas extras excessivas",
                nivel_risco=NivelRisco.CRITICO,
                prazo=date(2024, 12, 31),
                created_by=USER_ID,
                user_role=UserRole.RESPONDENT,
            )

        mock_action_plan_repo.create.assert_not_called()


# ---------------------------------------------------------------------------
# get_plan()
# ---------------------------------------------------------------------------


class TestActionPlanServiceGetPlan:
    async def test_get_plan_success(self, action_plan_service, mock_action_plan_repo):
        """get_plan retorna tupla (plan, evidencias)."""
        fake_plan = _make_fake_plan()
        mock_action_plan_repo.get_by_id.return_value = fake_plan
        mock_action_plan_repo.get_evidencias.return_value = []

        plan, evidencias = await action_plan_service.get_plan(PLAN_ID, COMPANY_ID)

        assert plan.id == fake_plan.id
        assert evidencias == []

    async def test_get_plan_not_found_raises_not_found(
        self, action_plan_service, mock_action_plan_repo
    ):
        """Plano inexistente levanta NotFoundError."""
        mock_action_plan_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await action_plan_service.get_plan(PLAN_ID, COMPANY_ID)

    async def test_get_plan_other_company_raises_forbidden(
        self, action_plan_service, mock_action_plan_repo
    ):
        """Plano de outra empresa levanta ForbiddenError."""
        fake_plan = _make_fake_plan(company_id=OTHER_COMPANY_ID)
        mock_action_plan_repo.get_by_id.return_value = fake_plan

        with pytest.raises(ForbiddenError):
            await action_plan_service.get_plan(PLAN_ID, COMPANY_ID)


# ---------------------------------------------------------------------------
# update_plan()
# ---------------------------------------------------------------------------


class TestActionPlanServiceUpdatePlan:
    async def test_update_plan_success(self, action_plan_service, mock_action_plan_repo):
        """Atualização parcial de plano pendente retorna plano atualizado."""
        fake_plan = _make_fake_plan(status=ActionPlanStatus.PENDENTE)
        updated_plan = _make_fake_plan(status=ActionPlanStatus.PENDENTE)
        updated_plan.titulo = "Novo Título"
        mock_action_plan_repo.get_by_id.return_value = fake_plan
        mock_action_plan_repo.update.return_value = updated_plan

        result = await action_plan_service.update_plan(
            plan_id=PLAN_ID,
            company_id=COMPANY_ID,
            user_role=UserRole.ADMIN,
            titulo="Novo Título",
        )

        assert result.titulo == "Novo Título"
        mock_action_plan_repo.update.assert_called_once()

    async def test_update_plan_concluido_raises_validation_error(
        self, action_plan_service, mock_action_plan_repo
    ):
        """Plano concluído não pode ser editado — levanta ValidationError."""
        fake_plan = _make_fake_plan(status=ActionPlanStatus.CONCLUIDO)
        mock_action_plan_repo.get_by_id.return_value = fake_plan

        with pytest.raises(ValidationError):
            await action_plan_service.update_plan(
                plan_id=PLAN_ID,
                company_id=COMPANY_ID,
                user_role=UserRole.ADMIN,
                titulo="Não pode editar",
            )

    async def test_update_plan_cancelado_raises_validation_error(
        self, action_plan_service, mock_action_plan_repo
    ):
        """Plano cancelado não pode ser editado — levanta ValidationError."""
        fake_plan = _make_fake_plan(status=ActionPlanStatus.CANCELADO)
        mock_action_plan_repo.get_by_id.return_value = fake_plan

        with pytest.raises(ValidationError):
            await action_plan_service.update_plan(
                plan_id=PLAN_ID,
                company_id=COMPANY_ID,
                user_role=UserRole.ADMIN,
                titulo="Não pode editar",
            )

    async def test_update_plan_respondent_raises_forbidden(
        self, action_plan_service, mock_action_plan_repo
    ):
        """RESPONDENT não pode atualizar plano."""
        with pytest.raises(ForbiddenError):
            await action_plan_service.update_plan(
                plan_id=PLAN_ID,
                company_id=COMPANY_ID,
                user_role=UserRole.RESPONDENT,
            )


# ---------------------------------------------------------------------------
# update_status()
# ---------------------------------------------------------------------------


class TestActionPlanServiceUpdateStatus:
    async def test_update_status_pendente_to_em_andamento(
        self, action_plan_service, mock_action_plan_repo
    ):
        """Transição PENDENTE → EM_ANDAMENTO é válida."""
        fake_plan = _make_fake_plan(status=ActionPlanStatus.PENDENTE)
        updated_plan = _make_fake_plan(status=ActionPlanStatus.EM_ANDAMENTO)
        mock_action_plan_repo.get_by_id.return_value = fake_plan
        mock_action_plan_repo.update_status.return_value = updated_plan

        result = await action_plan_service.update_status(
            plan_id=PLAN_ID,
            company_id=COMPANY_ID,
            user_role=UserRole.ADMIN,
            new_status=ActionPlanStatus.EM_ANDAMENTO,
        )

        assert result.status == ActionPlanStatus.EM_ANDAMENTO

    async def test_update_status_to_concluido_enqueues_notification(
        self, action_plan_service, mock_action_plan_repo
    ):
        """Conclusão de plano enfileira tarefa de notificação."""
        fake_plan = _make_fake_plan(status=ActionPlanStatus.EM_ANDAMENTO)
        completed_plan = _make_fake_plan(status=ActionPlanStatus.CONCLUIDO)
        mock_action_plan_repo.get_by_id.return_value = fake_plan
        mock_action_plan_repo.update_status.return_value = completed_plan

        await action_plan_service.update_status(
            plan_id=PLAN_ID,
            company_id=COMPANY_ID,
            user_role=UserRole.ADMIN,
            new_status=ActionPlanStatus.CONCLUIDO,
        )

        action_plan_service._task_service.enqueue.assert_called_once()

    async def test_update_status_cancelado_raises_validation_error(
        self, action_plan_service, mock_action_plan_repo
    ):
        """Plano cancelado não pode ter status alterado."""
        fake_plan = _make_fake_plan(status=ActionPlanStatus.CANCELADO)
        mock_action_plan_repo.get_by_id.return_value = fake_plan

        with pytest.raises(ValidationError):
            await action_plan_service.update_status(
                plan_id=PLAN_ID,
                company_id=COMPANY_ID,
                user_role=UserRole.ADMIN,
                new_status=ActionPlanStatus.EM_ANDAMENTO,
            )

    async def test_update_status_concluido_only_accepts_cancelado(
        self, action_plan_service, mock_action_plan_repo
    ):
        """Plano concluído só pode ser cancelado — qualquer outro status levanta erro."""
        fake_plan = _make_fake_plan(status=ActionPlanStatus.CONCLUIDO)
        mock_action_plan_repo.get_by_id.return_value = fake_plan

        with pytest.raises(ValidationError):
            await action_plan_service.update_status(
                plan_id=PLAN_ID,
                company_id=COMPANY_ID,
                user_role=UserRole.ADMIN,
                new_status=ActionPlanStatus.PENDENTE,
            )

    async def test_update_status_respondent_raises_forbidden(
        self, action_plan_service, mock_action_plan_repo
    ):
        """RESPONDENT não pode alterar status."""
        with pytest.raises(ForbiddenError):
            await action_plan_service.update_status(
                plan_id=PLAN_ID,
                company_id=COMPANY_ID,
                user_role=UserRole.RESPONDENT,
                new_status=ActionPlanStatus.EM_ANDAMENTO,
            )


# ---------------------------------------------------------------------------
# cancel_plan()
# ---------------------------------------------------------------------------


class TestActionPlanServiceCancelPlan:
    async def test_cancel_plan_success(
        self, action_plan_service, mock_action_plan_repo
    ):
        """Cancelamento de plano ativo chama update_status com CANCELADO."""
        fake_plan = _make_fake_plan(status=ActionPlanStatus.EM_ANDAMENTO)
        mock_action_plan_repo.get_by_id.return_value = fake_plan
        mock_action_plan_repo.update_status.return_value = MagicMock()

        await action_plan_service.cancel_plan(PLAN_ID, COMPANY_ID, UserRole.ADMIN)

        mock_action_plan_repo.update_status.assert_called_once_with(
            plan_id=PLAN_ID,
            status=ActionPlanStatus.CANCELADO,
        )

    async def test_cancel_plan_already_cancelled_raises_validation_error(
        self, action_plan_service, mock_action_plan_repo
    ):
        """Plano já cancelado levanta ValidationError."""
        fake_plan = _make_fake_plan(status=ActionPlanStatus.CANCELADO)
        mock_action_plan_repo.get_by_id.return_value = fake_plan

        with pytest.raises(ValidationError):
            await action_plan_service.cancel_plan(PLAN_ID, COMPANY_ID, UserRole.ADMIN)

    async def test_cancel_plan_not_found_raises_not_found(
        self, action_plan_service, mock_action_plan_repo
    ):
        """Plano inexistente levanta NotFoundError."""
        mock_action_plan_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await action_plan_service.cancel_plan(PLAN_ID, COMPANY_ID, UserRole.ADMIN)
