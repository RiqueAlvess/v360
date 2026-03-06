"""Testes de integração do survey_response_router.

Testa os endpoints de survey responses:
    - POST /api/v1/survey-responses/campaigns/{campaign_id}
    - GET  /api/v1/survey-responses/

Cobre as correções obrigatórias do Blueprint 03:
    - POST com token de convite válido → 201 + tasks enfileiradas (R3).
    - POST com token de convite já utilizado → 409.
    - POST com payload inválido → 422.
    - GET com paginação → 200 com page e page_size (R4).
    - Verificar que NENHUM cálculo de score ocorre no response cycle (R3).
"""
import hashlib
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

COMPANY_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CAMPAIGN_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")

# Payload válido com scores Likert dentro do intervalo [1, 5]
VALID_RESPOSTAS: dict = {
    "demandas": 4,
    "controle": 3,
    "suporte_gestao": 4,
    "relacionamentos": 5,
    "papel_funcao": 3,
    "mudancas": 2,
    "suporte_colegas": 4,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def survey_test_app(mock_session):
    """App sem autenticação (submit é público) com sessão mockada.

    O rate limiter do router é desabilitado para evitar que testes POST
    consecutivos sejam rejeitados com 429 (limite de 5/minute).
    O @_limiter.limit usa _limiter (router-local), não app.state.limiter.
    """
    from src.infrastructure.database.session import get_db
    from src.main import app
    from src.presentation.routers.survey_response_router import _limiter

    app.dependency_overrides[get_db] = lambda: mock_session

    # Desabilitar rate limiting no limiter do router (não no app.state.limiter)
    _limiter.enabled = False

    yield app

    _limiter.enabled = True
    app.dependency_overrides.clear()


@pytest.fixture
def survey_auth_app(fake_current_user, mock_session):
    """App com autenticação e sessão mockadas para endpoints autenticados."""
    from src.infrastructure.database.session import get_db
    from src.main import app
    from src.presentation.dependencies.auth import get_current_user

    app.dependency_overrides[get_current_user] = lambda: fake_current_user
    app.dependency_overrides[get_db] = lambda: mock_session

    yield app

    app.dependency_overrides.clear()


@pytest.fixture
async def survey_client(survey_test_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=survey_test_app),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.fixture
async def survey_auth_client(survey_auth_app):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=survey_auth_app),
        base_url="http://testserver",
    ) as client:
        yield client


def _make_fake_invitation(respondido: bool = False) -> MagicMock:
    """Cria um mock de Invitation para testes."""
    invitation = MagicMock()
    invitation.id = uuid.uuid4()
    invitation.campaign_id = CAMPAIGN_ID
    invitation.respondido = respondido
    invitation.token_hash = hashlib.sha256(b"valid_token_123").hexdigest()
    return invitation


def _make_scalar_result(value) -> MagicMock:
    """Cria um mock de ScalarResult para db.execute()."""
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=value)
    result.scalar_one = MagicMock(return_value=value)
    result.all = MagicMock(return_value=[])
    return result


# ---------------------------------------------------------------------------
# POST /api/v1/survey-responses/campaigns/{campaign_id}
# ---------------------------------------------------------------------------


class TestSubmitSurveyResponse:
    async def test_submit_without_token_returns_201(
        self, survey_client, mock_session
    ):
        """Submissão sem invite_token retorna HTTP 201."""
        # db.execute retorna None para a busca de invitation (token não fornecido)
        mock_session.execute = AsyncMock(return_value=_make_scalar_result(None))
        mock_session.commit = AsyncMock()

        response = await survey_client.post(
            f"/api/v1/survey-responses/campaigns/{CAMPAIGN_ID}",
            json={"respostas": VALID_RESPOSTAS},
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["campaign_id"] == str(CAMPAIGN_ID)
        assert "mensagem" in data

    async def test_submit_with_valid_token_returns_201(
        self, survey_client, mock_session
    ):
        """Submissão com token de convite válido (não utilizado) retorna 201."""
        fake_invitation = _make_fake_invitation(respondido=False)
        mock_session.execute = AsyncMock(
            return_value=_make_scalar_result(fake_invitation)
        )
        mock_session.commit = AsyncMock()

        response = await survey_client.post(
            f"/api/v1/survey-responses/campaigns/{CAMPAIGN_ID}",
            json={
                "respostas": VALID_RESPOSTAS,
                "invite_token": "valid_token_123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["campaign_id"] == str(CAMPAIGN_ID)

    async def test_submit_with_already_used_token_returns_409(
        self, survey_client, mock_session
    ):
        """Submissão com token já utilizado retorna HTTP 409 (ConflictError)."""
        fake_invitation = _make_fake_invitation(respondido=True)
        mock_session.execute = AsyncMock(
            return_value=_make_scalar_result(fake_invitation)
        )

        response = await survey_client.post(
            f"/api/v1/survey-responses/campaigns/{CAMPAIGN_ID}",
            json={
                "respostas": VALID_RESPOSTAS,
                "invite_token": "already_used_token",
            },
        )

        assert response.status_code == 409
        data = response.json()
        assert "detail" in data

    async def test_submit_missing_respostas_returns_422(self, survey_client):
        """Submissão sem o campo obrigatório 'respostas' retorna HTTP 422."""
        response = await survey_client.post(
            f"/api/v1/survey-responses/campaigns/{CAMPAIGN_ID}",
            json={},
        )
        assert response.status_code == 422

    async def test_submit_score_out_of_range_returns_422(self, survey_client):
        """Submissão com score fora da escala Likert [1,5] retorna HTTP 422."""
        response = await survey_client.post(
            f"/api/v1/survey-responses/campaigns/{CAMPAIGN_ID}",
            json={"respostas": {"demandas": 6}},
        )
        assert response.status_code == 422

    async def test_submit_texto_livre_without_consent_returns_422(
        self, survey_client
    ):
        """texto_livre sem consentimento_texto_livre=True retorna HTTP 422."""
        response = await survey_client.post(
            f"/api/v1/survey-responses/campaigns/{CAMPAIGN_ID}",
            json={
                "respostas": VALID_RESPOSTAS,
                "texto_livre": "Estou me sentindo sobrecarregado",
                "consentimento_texto_livre": False,
            },
        )
        assert response.status_code == 422

    async def test_submit_enqueues_compute_scores_task(
        self, survey_client, mock_session
    ):
        """Verifica que a task compute_scores é enfileirada após submissão (Regra R3).

        O cálculo de score NUNCA ocorre no request/response cycle — apenas
        uma entrada é criada na task_queue para processamento assíncrono.
        """
        mock_session.execute = AsyncMock(return_value=_make_scalar_result(None))
        mock_session.commit = AsyncMock()

        # Capturar objetos adicionados ao db.add()
        added_objects: list = []
        mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        response = await survey_client.post(
            f"/api/v1/survey-responses/campaigns/{CAMPAIGN_ID}",
            json={"respostas": VALID_RESPOSTAS},
        )

        assert response.status_code == 201

        # Verificar que uma task COMPUTE_SCORES foi enfileirada
        from src.domain.enums.task_queue_type import TaskQueueType
        from src.infrastructure.database.models.task_queue import TaskQueue

        tasks = [obj for obj in added_objects if isinstance(obj, TaskQueue)]
        compute_tasks = [
            t for t in tasks if t.tipo == TaskQueueType.COMPUTE_SCORES
        ]
        assert len(compute_tasks) == 1
        assert compute_tasks[0].payload["campaign_id"] == str(CAMPAIGN_ID)

    async def test_submit_with_texto_livre_enqueues_sentiment_task(
        self, survey_client, mock_session
    ):
        """Submissão com texto_livre enfileira task analyze_sentiment (Regra R3)."""
        mock_session.execute = AsyncMock(return_value=_make_scalar_result(None))
        mock_session.commit = AsyncMock()

        added_objects: list = []
        mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        response = await survey_client.post(
            f"/api/v1/survey-responses/campaigns/{CAMPAIGN_ID}",
            json={
                "respostas": VALID_RESPOSTAS,
                "texto_livre": "Ambiente colaborativo e produtivo.",
                "consentimento_texto_livre": True,
            },
        )

        assert response.status_code == 201

        from src.domain.enums.task_queue_type import TaskQueueType
        from src.infrastructure.database.models.task_queue import TaskQueue

        tasks = [obj for obj in added_objects if isinstance(obj, TaskQueue)]
        sentiment_tasks = [
            t for t in tasks if t.tipo == TaskQueueType.ANALYZE_SENTIMENT
        ]
        assert len(sentiment_tasks) == 1

    async def test_submit_marks_invitation_as_respondido(
        self, survey_client, mock_session
    ):
        """Após submissão com token válido, invitation.respondido é True."""
        fake_invitation = _make_fake_invitation(respondido=False)
        mock_session.execute = AsyncMock(
            return_value=_make_scalar_result(fake_invitation)
        )
        mock_session.commit = AsyncMock()

        response = await survey_client.post(
            f"/api/v1/survey-responses/campaigns/{CAMPAIGN_ID}",
            json={
                "respostas": VALID_RESPOSTAS,
                "invite_token": "valid_token_123",
            },
        )

        assert response.status_code == 201
        # Verifica que o atributo respondido foi modificado para True (Blind Drop)
        assert fake_invitation.respondido is True

    async def test_submit_does_not_call_score_service(
        self, survey_client, mock_session
    ):
        """Verifica que ScoreService NÃO é chamado durante a submissão (Regra R3).

        O score NUNCA é calculado no request/response cycle. Apenas tasks
        são enfileiradas para processamento assíncrono pelo worker.
        """
        mock_session.execute = AsyncMock(return_value=_make_scalar_result(None))
        mock_session.commit = AsyncMock()

        with patch(
            "src.application.services.score_service.ScoreService.calcular_score_dimensao"
        ) as mock_calcular:
            response = await survey_client.post(
                f"/api/v1/survey-responses/campaigns/{CAMPAIGN_ID}",
                json={"respostas": VALID_RESPOSTAS},
            )

        assert response.status_code == 201
        # ScoreService NUNCA deve ser chamado no ciclo request/response
        mock_calcular.assert_not_called()


# ---------------------------------------------------------------------------
# GET /api/v1/survey-responses/
# ---------------------------------------------------------------------------


class TestListSurveyResponses:
    async def test_list_returns_200_with_pagination(
        self, survey_auth_client, mock_session
    ):
        """Listagem autenticada retorna HTTP 200 com estrutura paginada."""
        # Mock para count e para items
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=0)

        items_result = MagicMock()
        items_result.all = MagicMock(return_value=[])

        mock_session.execute = AsyncMock(
            side_effect=[count_result, items_result]
        )

        response = await survey_auth_client.get(
            f"/api/v1/survey-responses/?campaign_id={CAMPAIGN_ID}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 20

    async def test_list_returns_items_without_pii(
        self, survey_auth_client, mock_session
    ):
        """Listagem não expõe texto_livre, email ou dados identificáveis."""
        fake_row = MagicMock()
        fake_row.id = uuid.uuid4()
        fake_row.campaign_id = CAMPAIGN_ID
        fake_row.anonimizado = True
        fake_row.sentimento = None
        fake_row.created_at = datetime.now(tz=timezone.utc)

        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=1)

        items_result = MagicMock()
        items_result.all = MagicMock(return_value=[fake_row])

        mock_session.execute = AsyncMock(
            side_effect=[count_result, items_result]
        )

        response = await survey_auth_client.get(
            f"/api/v1/survey-responses/?campaign_id={CAMPAIGN_ID}"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

        item = data["items"][0]
        # Verificar que campos sensíveis NÃO estão na resposta
        assert "texto_livre" not in item
        assert "email" not in item
        assert "respostas" not in item
        # Verificar que apenas campos anonimizados estão presentes
        assert "id" in item
        assert "campaign_id" in item
        assert "anonimizado" in item
        assert "created_at" in item

    async def test_list_pagination_parameters(
        self, survey_auth_client, mock_session
    ):
        """Parâmetros de paginação page e page_size são respeitados (Regra R4)."""
        count_result = MagicMock()
        count_result.scalar_one = MagicMock(return_value=50)

        items_result = MagicMock()
        items_result.all = MagicMock(return_value=[])

        mock_session.execute = AsyncMock(
            side_effect=[count_result, items_result]
        )

        response = await survey_auth_client.get(
            f"/api/v1/survey-responses/?campaign_id={CAMPAIGN_ID}&page=2&page_size=10"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["page_size"] == 10
        assert data["pagination"]["total"] == 50
        assert data["pagination"]["pages"] == 5

    async def test_list_page_size_exceeds_max_returns_422(
        self, survey_auth_client
    ):
        """page_size acima de 100 retorna HTTP 422 (Regra R4 — máximo 100)."""
        response = await survey_auth_client.get(
            f"/api/v1/survey-responses/?campaign_id={CAMPAIGN_ID}&page_size=101"
        )
        assert response.status_code == 422

    async def test_list_without_auth_returns_401(self, mock_session):
        """Listagem sem autenticação retorna HTTP 401."""
        from httpx import ASGITransport, AsyncClient
        from src.infrastructure.database.session import get_db
        from src.main import app

        app.dependency_overrides[get_db] = lambda: mock_session

        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                response = await client.get(
                    f"/api/v1/survey-responses/?campaign_id={CAMPAIGN_ID}"
                )
            assert response.status_code == 401
        finally:
            app.dependency_overrides.clear()

    async def test_list_missing_campaign_id_returns_422(
        self, survey_auth_client
    ):
        """Listagem sem campaign_id retorna HTTP 422 (parâmetro obrigatório)."""
        response = await survey_auth_client.get("/api/v1/survey-responses/")
        assert response.status_code == 422
