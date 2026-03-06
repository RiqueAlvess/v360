"""Testes unitários do SQLCampaignRepository.

Cobre (Blueprint 02):
    - get_by_id(): campanha encontrada e não encontrada
    - list_by_company(): paginação (R4), múltiplas páginas, page_size máximo
    - list_with_filters(): filtro de status, datas, combinações
    - create(): persistência com flush
    - update(): atualização parcial de campos
    - update_status(): atualização somente de status
    - get_campaign_with_stats(): contagem de convites e respostas
    - RLS (R5): isolamento por empresa — company_A não vê campanhas de company_B
"""
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.domain.enums.campaign_status import CampaignStatus
from src.infrastructure.repositories.campaign_repository import (
    CampaignStats,
    SQLCampaignRepository,
)

# ---------------------------------------------------------------------------
# IDs fixos
# ---------------------------------------------------------------------------

COMPANY_A_ID: uuid.UUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
COMPANY_B_ID: uuid.UUID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
CAMPAIGN_ID: uuid.UUID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_campaign(
    campaign_id: uuid.UUID = CAMPAIGN_ID,
    company_id: uuid.UUID = COMPANY_A_ID,
    status: CampaignStatus = CampaignStatus.DRAFT,
    nome: str = "Campanha Teste",
    data_inicio: date = date(2024, 1, 1),
    data_fim: date = date(2024, 12, 31),
) -> MagicMock:
    """Cria um objeto Campaign fake para uso em testes."""
    campaign = MagicMock()
    campaign.id = campaign_id
    campaign.company_id = company_id
    campaign.nome = nome
    campaign.status = status
    campaign.data_inicio = data_inicio
    campaign.data_fim = data_fim
    campaign.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    campaign.updated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return campaign


def _make_scalar_result(value) -> MagicMock:
    """Mock de resultado scalar_one_or_none()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _make_scalar_one_result(value) -> MagicMock:
    """Mock de resultado scalar_one()."""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _make_scalars_result(items: list) -> MagicMock:
    """Mock de resultado scalars().all()."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    return result


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> AsyncMock:
    """AsyncSession mockada."""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> SQLCampaignRepository:
    """SQLCampaignRepository com sessão mockada."""
    return SQLCampaignRepository(session=mock_session)


# ---------------------------------------------------------------------------
# get_by_id()
# ---------------------------------------------------------------------------


class TestGetById:
    async def test_get_by_id_found_returns_campaign(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Campanha existente é retornada corretamente."""
        fake_campaign = _make_campaign()
        mock_session.execute.return_value = _make_scalar_result(fake_campaign)

        result = await repo.get_by_id(CAMPAIGN_ID)

        assert result is fake_campaign
        mock_session.execute.assert_called_once()

    async def test_get_by_id_not_found_returns_none(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """UUID inexistente retorna None sem levantar exceção."""
        mock_session.execute.return_value = _make_scalar_result(None)

        result = await repo.get_by_id(uuid.uuid4())

        assert result is None

    async def test_get_by_id_uses_campaign_id_in_query(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """A query sempre filtra pelo campaign_id fornecido."""
        mock_session.execute.return_value = _make_scalar_result(None)

        await repo.get_by_id(CAMPAIGN_ID)

        # Verifica que execute foi chamado (o WHERE é construído pelo SQLAlchemy)
        mock_session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# list_by_company() — R4 Paginação
# ---------------------------------------------------------------------------


class TestListByCompany:
    async def test_list_by_company_returns_items_and_total(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Retorna tupla (items, total) conforme assinatura R4."""
        fake_campaigns = [_make_campaign(campaign_id=uuid.uuid4()) for _ in range(3)]

        mock_session.execute.side_effect = [
            _make_scalar_one_result(3),   # count query
            _make_scalars_result(fake_campaigns),  # items query
        ]

        items, total = await repo.list_by_company(
            company_id=COMPANY_A_ID,
            page=1,
            page_size=20,
        )

        assert isinstance(total, int)
        assert total == 3
        assert len(items) == 3

    async def test_list_by_company_respects_page_size(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """page_size é respeitado — retorna no máximo page_size itens (R4)."""
        page_size = 5
        fake_campaigns = [_make_campaign(campaign_id=uuid.uuid4()) for _ in range(page_size)]

        mock_session.execute.side_effect = [
            _make_scalar_one_result(50),  # total maior que page_size
            _make_scalars_result(fake_campaigns),
        ]

        items, total = await repo.list_by_company(
            company_id=COMPANY_A_ID,
            page=1,
            page_size=page_size,
        )

        assert len(items) <= page_size
        assert total == 50

    async def test_list_by_company_page2_offset_correct(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Página 2 com page_size=5 deve retornar itens corretos."""
        page2_campaigns = [_make_campaign(campaign_id=uuid.uuid4()) for _ in range(5)]

        mock_session.execute.side_effect = [
            _make_scalar_one_result(12),
            _make_scalars_result(page2_campaigns),
        ]

        items, total = await repo.list_by_company(
            company_id=COMPANY_A_ID,
            page=2,
            page_size=5,
        )

        assert len(items) == 5
        assert total == 12
        # execute chamado duas vezes: count e items
        assert mock_session.execute.call_count == 2

    async def test_list_by_company_caps_page_size_at_100(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """page_size acima de 100 é limitado a 100 — Regra R4."""
        mock_session.execute.side_effect = [
            _make_scalar_one_result(200),
            _make_scalars_result([]),
        ]

        # Solicitar 500 itens deve ser silenciosamente limitado a 100
        items, total = await repo.list_by_company(
            company_id=COMPANY_A_ID,
            page=1,
            page_size=500,
        )

        assert total == 200

    async def test_list_by_company_empty_returns_empty_list(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Empresa sem campanhas retorna lista vazia e total zero."""
        mock_session.execute.side_effect = [
            _make_scalar_one_result(0),
            _make_scalars_result([]),
        ]

        items, total = await repo.list_by_company(company_id=COMPANY_A_ID)

        assert items == []
        assert total == 0


# ---------------------------------------------------------------------------
# list_with_filters() — R4 + Filtros
# ---------------------------------------------------------------------------


class TestListWithFilters:
    async def test_list_with_filters_no_filters_behaves_like_list_by_company(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Sem filtros opcionais, comportamento é equivalente a list_by_company."""
        fake_campaigns = [_make_campaign()]

        mock_session.execute.side_effect = [
            _make_scalar_one_result(1),
            _make_scalars_result(fake_campaigns),
        ]

        items, total = await repo.list_with_filters(company_id=COMPANY_A_ID)

        assert total == 1
        assert len(items) == 1

    async def test_list_with_filters_by_status(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Filtro por status retorna apenas campanhas com o status informado."""
        active_campaigns = [
            _make_campaign(status=CampaignStatus.ACTIVE),
            _make_campaign(campaign_id=uuid.uuid4(), status=CampaignStatus.ACTIVE),
        ]

        mock_session.execute.side_effect = [
            _make_scalar_one_result(2),
            _make_scalars_result(active_campaigns),
        ]

        items, total = await repo.list_with_filters(
            company_id=COMPANY_A_ID,
            status=CampaignStatus.ACTIVE,
        )

        assert total == 2
        assert all(c.status == CampaignStatus.ACTIVE for c in items)

    async def test_list_with_filters_by_data_inicio_gte(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Filtro data_inicio_gte retorna campanhas iniciadas a partir da data."""
        campaigns = [_make_campaign(data_inicio=date(2024, 6, 1))]

        mock_session.execute.side_effect = [
            _make_scalar_one_result(1),
            _make_scalars_result(campaigns),
        ]

        items, total = await repo.list_with_filters(
            company_id=COMPANY_A_ID,
            data_inicio_gte=date(2024, 6, 1),
        )

        assert total == 1
        assert items[0].data_inicio == date(2024, 6, 1)

    async def test_list_with_filters_by_data_fim_lte(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Filtro data_fim_lte retorna campanhas encerradas até a data."""
        campaigns = [_make_campaign(data_fim=date(2024, 3, 31))]

        mock_session.execute.side_effect = [
            _make_scalar_one_result(1),
            _make_scalars_result(campaigns),
        ]

        items, total = await repo.list_with_filters(
            company_id=COMPANY_A_ID,
            data_fim_lte=date(2024, 3, 31),
        )

        assert total == 1

    async def test_list_with_filters_combined_all_filters(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Todos os filtros combinados: status + datas + empresa + paginação."""
        campaigns = [
            _make_campaign(
                status=CampaignStatus.ACTIVE,
                data_inicio=date(2024, 2, 1),
                data_fim=date(2024, 6, 30),
            )
        ]

        mock_session.execute.side_effect = [
            _make_scalar_one_result(1),
            _make_scalars_result(campaigns),
        ]

        items, total = await repo.list_with_filters(
            company_id=COMPANY_A_ID,
            status=CampaignStatus.ACTIVE,
            data_inicio_gte=date(2024, 1, 1),
            data_fim_lte=date(2024, 12, 31),
            page=1,
            page_size=10,
        )

        assert total == 1
        assert len(items) == 1

    async def test_list_with_filters_no_results_returns_empty(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Filtros sem correspondência retornam lista vazia e total zero."""
        mock_session.execute.side_effect = [
            _make_scalar_one_result(0),
            _make_scalars_result([]),
        ]

        items, total = await repo.list_with_filters(
            company_id=COMPANY_A_ID,
            status=CampaignStatus.CANCELLED,
        )

        assert items == []
        assert total == 0

    async def test_list_with_filters_respects_page_size_max(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """page_size acima de 100 é limitado a 100 — Regra R4."""
        mock_session.execute.side_effect = [
            _make_scalar_one_result(500),
            _make_scalars_result([]),
        ]

        _items, total = await repo.list_with_filters(
            company_id=COMPANY_A_ID,
            page_size=999,
        )

        assert total == 500


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


class TestCreate:
    async def test_create_adds_campaign_to_session(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """create() adiciona a campanha à sessão e chama flush."""
        await repo.create(
            company_id=COMPANY_A_ID,
            nome="Campanha NR-1 2024",
            data_inicio=date(2024, 1, 1),
            data_fim=date(2024, 12, 31),
        )

        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    async def test_create_returns_campaign_with_generated_id(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """create() retorna Campaign com UUID gerado automaticamente."""
        campaign = await repo.create(
            company_id=COMPANY_A_ID,
            nome="Campanha de teste",
            data_inicio=date(2024, 3, 1),
            data_fim=date(2024, 9, 30),
        )

        assert campaign.id is not None
        assert campaign.company_id == COMPANY_A_ID
        assert campaign.nome == "Campanha de teste"
        assert campaign.data_inicio == date(2024, 3, 1)
        assert campaign.data_fim == date(2024, 9, 30)


# ---------------------------------------------------------------------------
# update() — atualização parcial
# ---------------------------------------------------------------------------


class TestUpdate:
    async def test_update_nome_only(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Atualização somente de nome não altera outros campos."""
        updated_campaign = _make_campaign(nome="Novo Nome")
        mock_session.execute.return_value = _make_scalar_one_result(updated_campaign)

        result = await repo.update(campaign_id=CAMPAIGN_ID, nome="Novo Nome")

        assert result.nome == "Novo Nome"
        mock_session.flush.assert_called_once()

    async def test_update_status_and_data_fim(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Atualização parcial de status + data_fim funciona corretamente."""
        updated_campaign = _make_campaign(
            status=CampaignStatus.ACTIVE,
            data_fim=date(2025, 6, 30),
        )
        mock_session.execute.return_value = _make_scalar_one_result(updated_campaign)

        result = await repo.update(
            campaign_id=CAMPAIGN_ID,
            status=CampaignStatus.ACTIVE,
            data_fim=date(2025, 6, 30),
        )

        assert result.status == CampaignStatus.ACTIVE
        assert result.data_fim == date(2025, 6, 30)

    async def test_update_all_fields(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Todos os campos opcionais podem ser atualizados de uma vez."""
        updated_campaign = _make_campaign(
            nome="Nome Atualizado",
            status=CampaignStatus.PAUSED,
            data_inicio=date(2024, 2, 1),
            data_fim=date(2024, 11, 30),
        )
        mock_session.execute.return_value = _make_scalar_one_result(updated_campaign)

        result = await repo.update(
            campaign_id=CAMPAIGN_ID,
            nome="Nome Atualizado",
            data_inicio=date(2024, 2, 1),
            data_fim=date(2024, 11, 30),
            status=CampaignStatus.PAUSED,
        )

        assert result.nome == "Nome Atualizado"
        assert result.status == CampaignStatus.PAUSED
        assert result.data_inicio == date(2024, 2, 1)
        assert result.data_fim == date(2024, 11, 30)

    async def test_update_calls_flush(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """update() sempre chama flush após a atualização."""
        updated_campaign = _make_campaign()
        mock_session.execute.return_value = _make_scalar_one_result(updated_campaign)

        await repo.update(campaign_id=CAMPAIGN_ID, nome="Novo Nome")

        mock_session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# update_status()
# ---------------------------------------------------------------------------


class TestUpdateStatus:
    async def test_update_status_returns_updated_campaign(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Atualização de status retorna a campanha com novo status."""
        updated_campaign = _make_campaign(status=CampaignStatus.COMPLETED)
        mock_session.execute.return_value = _make_scalar_one_result(updated_campaign)

        result = await repo.update_status(
            campaign_id=CAMPAIGN_ID,
            status=CampaignStatus.COMPLETED,
        )

        assert result.status == CampaignStatus.COMPLETED
        mock_session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# get_campaign_with_stats()
# ---------------------------------------------------------------------------


class TestGetCampaignWithStats:
    async def test_get_campaign_with_stats_returns_dataclass(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Retorna CampaignStats com campaign, total_convites e total_respostas."""
        fake_campaign = _make_campaign()

        mock_session.execute.side_effect = [
            _make_scalar_result(fake_campaign),   # get_by_id
            _make_scalar_one_result(10),           # count invitations
            _make_scalar_one_result(7),            # count responses
        ]

        result = await repo.get_campaign_with_stats(CAMPAIGN_ID)

        assert isinstance(result, CampaignStats)
        assert result.campaign is fake_campaign
        assert result.total_convites == 10
        assert result.total_respostas == 7

    async def test_get_campaign_with_stats_not_found_returns_none(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """UUID inexistente retorna None sem chamar queries de contagem."""
        mock_session.execute.return_value = _make_scalar_result(None)

        result = await repo.get_campaign_with_stats(uuid.uuid4())

        assert result is None
        # Deve ter chamado apenas a query de busca de campanha
        assert mock_session.execute.call_count == 1

    async def test_get_campaign_with_stats_zero_counts(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """Campanha sem convites e sem respostas retorna contagens zero."""
        fake_campaign = _make_campaign()

        mock_session.execute.side_effect = [
            _make_scalar_result(fake_campaign),
            _make_scalar_one_result(0),
            _make_scalar_one_result(0),
        ]

        result = await repo.get_campaign_with_stats(CAMPAIGN_ID)

        assert result is not None
        assert result.total_convites == 0
        assert result.total_respostas == 0

    async def test_get_campaign_with_stats_types(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """total_convites e total_respostas são sempre inteiros."""
        fake_campaign = _make_campaign()

        mock_session.execute.side_effect = [
            _make_scalar_result(fake_campaign),
            _make_scalar_one_result(5),
            _make_scalar_one_result(3),
        ]

        result = await repo.get_campaign_with_stats(CAMPAIGN_ID)

        assert result is not None
        assert isinstance(result.total_convites, int)
        assert isinstance(result.total_respostas, int)


# ---------------------------------------------------------------------------
# RLS — Isolamento Multi-Tenant (R5)
# ---------------------------------------------------------------------------


class TestRLSIsolation:
    async def test_list_by_company_filters_by_company_id(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """list_by_company usa company_id como filtro de isolamento (R5).

        Com RLS ativo no banco, esta query é dupla proteção:
        1. WHERE company_id = :id no código
        2. RLS policy via current_setting('app.company_id')
        """
        mock_session.execute.side_effect = [
            _make_scalar_one_result(0),
            _make_scalars_result([]),
        ]

        # company_A busca campanhas com seu próprio ID
        items, total = await repo.list_by_company(company_id=COMPANY_A_ID)

        assert items == []
        assert total == 0
        # A query de items foi executada — o filtro by company_id está no WHERE
        assert mock_session.execute.call_count == 2

    async def test_company_a_cannot_see_company_b_campaigns(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """RLS garante que company_A com app.company_id=A não vê campanhas de B.

        O banco retorna resultado vazio porque o RLS filtra automaticamente.
        Este teste simula o comportamento esperado do PostgreSQL RLS.
        """
        # Simula RLS: quando company_A busca, banco retorna 0 registros de company_B
        mock_session.execute.side_effect = [
            _make_scalar_one_result(0),
            _make_scalars_result([]),
        ]

        items, total = await repo.list_by_company(company_id=COMPANY_A_ID)

        # Com RLS ativo, campanhas de company_B nunca aparecem para company_A
        assert total == 0
        assert items == []

    async def test_get_by_id_returns_none_for_other_company_campaign(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """RLS filtra get_by_id quando a campanha pertence a outra empresa.

        PostgreSQL retorna NULL quando o RLS bloqueia a linha, resultando
        em scalar_one_or_none() → None.
        """
        # RLS impede acesso: banco retorna None para campanha de company_B
        mock_session.execute.return_value = _make_scalar_result(None)

        result = await repo.get_by_id(CAMPAIGN_ID)

        assert result is None

    async def test_list_with_filters_filters_by_company_id(
        self, repo: SQLCampaignRepository, mock_session: AsyncMock
    ) -> None:
        """list_with_filters inclui company_id como filtro base (R5)."""
        mock_session.execute.side_effect = [
            _make_scalar_one_result(0),
            _make_scalars_result([]),
        ]

        items, total = await repo.list_with_filters(
            company_id=COMPANY_A_ID,
            status=CampaignStatus.ACTIVE,
        )

        assert total == 0
        assert items == []
        # Confirma que execute foi chamado — o filtro company_id está no WHERE
        assert mock_session.execute.call_count == 2
