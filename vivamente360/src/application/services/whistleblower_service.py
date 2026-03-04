"""Service do Canal de Denúncias Anônimo — Módulo 07.

Regra R2: Services orquestram — não acessam Infrastructure diretamente.
Regra R1: Type hints completos em todos os métodos e parâmetros.

MODELO DE ANONIMATO (Blind Report):
    1. submit() gera report_token via secrets.token_urlsafe(32).
    2. Salva APENAS o SHA-256 (token_hash) no banco — token raw nunca persiste.
    3. Retorna o token raw UMA ÚNICA VEZ ao denunciante.
    4. respond() registra a resposta institucional sem acesso a dados do denunciante.

NOTIFICAÇÃO DE ADMINS (Tarefa 46):
    Ao receber novo relato, o service enfileira uma task NOTIFY_WHISTLEBLOWER_ADMIN
    com o company_id para que o worker (Módulo 08) notifique os admins.
    Os emails dos admins são decifrados APENAS no worker — nunca no ciclo request/response.
"""
import logging
import math
import secrets
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.notification_service import NotificationService
from src.domain.enums.notification_tipo import NotificationTipo
from src.domain.enums.task_queue_type import TaskQueueType
from src.domain.enums.user_role import UserRole
from src.domain.enums.whistleblower_categoria import WhistleblowerCategoria
from src.domain.enums.whistleblower_status import WhistleblowerStatus
from src.infrastructure.queue.task_service import TaskService
from src.infrastructure.repositories.whistleblower_repository import (
    WhistleblowerRepository,
)
from src.shared.exceptions import NotFoundError, ValidationError
from src.shared.security import hash_token

logger = logging.getLogger(__name__)

# Comprimento do token de acompanhamento — 32 bytes → 43 chars URL-safe base64
_TOKEN_BYTE_LENGTH: int = 32

# Status que permitem transições via respond()
_STATUS_VALIDOS_RESPOSTA: frozenset[WhistleblowerStatus] = frozenset(
    {
        WhistleblowerStatus.EM_ANALISE,
        WhistleblowerStatus.CONCLUIDO,
        WhistleblowerStatus.ARQUIVADO,
    }
)


class WhistleblowerService:
    """Gerencia o ciclo de vida do canal de denúncias anônimo.

    Responsabilidades:
    - submit(): recebe relato público sem autenticação; garante anonimato total.
    - consulta(): permite ao denunciante verificar a resposta via token.
    - list_reports(): lista relatos para admin com paginação.
    - get_report(): detalha um relato específico para admin.
    - respond(): registra a resposta institucional e notifica o denunciante via task.
    """

    def __init__(
        self,
        repo: WhistleblowerRepository,
        task_service: TaskService,
        notification_service: NotificationService | None = None,
    ) -> None:
        self._repo = repo
        self._task_service = task_service
        self._notification_service = notification_service

    async def resolve_company_slug(self, slug: str) -> UUID:
        """Resolve o slug público da empresa para seu UUID.

        Args:
            slug: Identificador público da empresa na URL (/denuncia/{slug}/...).

        Returns:
            UUID da empresa correspondente ao slug.

        Raises:
            NotFoundError: Se o slug não existir ou a empresa estiver inativa.
        """
        company_id = await self._repo.get_company_id_by_slug(slug)
        if company_id is None:
            raise NotFoundError("Canal de denúncias", slug)
        return company_id

    async def submit(
        self,
        company_id: UUID,
        categoria: WhistleblowerCategoria,
        descricao: str,
        nome_opcional: str | None,
    ) -> dict[str, str]:
        """Recebe e persiste um novo relato anônimo.

        Fluxo de anonimato:
            1. Gera report_token (secrets.token_urlsafe(32)).
            2. Calcula SHA-256 do token → token_hash.
            3. Persiste o relato COM token_hash, SEM token raw.
            4. Enfileira NOTIFY_WHISTLEBLOWER_ADMIN para o worker.
            5. Retorna o token raw UMA ÚNICA VEZ — nunca mais acessível.

        Args:
            company_id: UUID da empresa (resolvido via slug — sem JWT).
            categoria: Categoria da denúncia.
            descricao: Conteúdo do relato.
            nome_opcional: Nome do denunciante (somente se anonimo=False).

        Returns:
            Dict com 'report_token' (exibir UMA VEZ ao denunciante).

        Raises:
            ValidationError: Se a descrição for muito curta.
        """
        if len(descricao.strip()) < 20:
            raise ValidationError(
                "A descrição deve ter ao menos 20 caracteres.", field="descricao"
            )

        # Gera token criptograficamente seguro — NUNCA persiste no banco
        report_token: str = secrets.token_urlsafe(_TOKEN_BYTE_LENGTH)
        token_hash: str = hash_token(report_token)

        anonimo: bool = nome_opcional is None

        await self._repo.create(
            company_id=company_id,
            token_hash=token_hash,
            categoria=categoria.value,
            descricao=descricao.strip(),
            anonimo=anonimo,
            nome_opcional=nome_opcional,
        )

        # Enfileira notificação por email para admins — processada pelo worker
        # Nenhum dado do denunciante está no payload da task
        await self._task_service.enqueue(
            tipo=TaskQueueType.NOTIFY_WHISTLEBLOWER_ADMIN,
            payload={"company_id": str(company_id)},
        )

        # Notificação in-app para admins e gestores (Módulo 08)
        if self._notification_service is not None:
            await self._notification_service.notify_by_role(
                company_id=company_id,
                role=UserRole.ADMIN,
                tipo=NotificationTipo.NOVA_DENUNCIA,
                titulo="Nova denúncia recebida",
                mensagem="Um novo relato foi recebido no canal de denúncias.",
                link="/admin/whistleblower",
                metadata={"company_id": str(company_id)},
            )
            await self._notification_service.notify_by_role(
                company_id=company_id,
                role=UserRole.MANAGER,
                tipo=NotificationTipo.NOVA_DENUNCIA,
                titulo="Nova denúncia recebida",
                mensagem="Um novo relato foi recebido no canal de denúncias.",
                link="/admin/whistleblower",
                metadata={"company_id": str(company_id)},
            )

        logger.info(
            "Novo relato recebido: company_id=%s categoria=%s anonimo=%s",
            company_id,
            categoria.value,
            anonimo,
        )

        return {"report_token": report_token}

    async def consulta(
        self,
        company_id: UUID,
        report_token: str,
    ) -> dict[str, Any]:
        """Permite ao denunciante consultar a resposta institucional via token.

        Args:
            company_id: UUID da empresa (para contexto RLS).
            report_token: Token raw fornecido pelo denunciante.

        Returns:
            Dict com 'status', 'resposta_institucional' e 'respondido_em'.

        Raises:
            NotFoundError: Se o token não corresponder a nenhum relato da empresa.
        """
        token_hash: str = hash_token(report_token)
        report = await self._repo.get_by_token_hash(token_hash)

        if report is None or report.company_id != company_id:
            raise NotFoundError(
                "Relato não encontrado. Verifique o token informado."
            )

        return {
            "status": report.status,
            "resposta_institucional": report.resposta_institucional,
            "respondido_em": report.respondido_em,
        }

    async def list_reports(
        self,
        company_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Lista relatos da empresa com paginação — acesso exclusivo de admins/compliance.

        Args:
            company_id: UUID da empresa autenticada.
            page: Página (1-indexed, padrão 1).
            page_size: Itens por página (máximo 100, padrão 20).
            status: Filtro opcional por status do relato.

        Returns:
            Dict com 'items' e 'pagination'.
        """
        reports, total = await self._repo.list_by_company(
            company_id=company_id,
            page=page,
            page_size=page_size,
            status=status,
        )

        pages = math.ceil(total / page_size) if total > 0 else 0

        return {
            "items": reports,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": pages,
            },
        }

    async def get_report(
        self,
        report_id: UUID,
        company_id: UUID,
    ) -> Any:
        """Retorna um relato específico pelo UUID — acesso exclusivo de admins.

        O RLS garante que apenas relatos da empresa autenticada são retornados.
        A validação de company_id é dupla: via RLS no banco e via comparação no service.

        Args:
            report_id: UUID do relato.
            company_id: UUID da empresa autenticada (validação de tenant).

        Returns:
            O WhistleblowerReport encontrado.

        Raises:
            NotFoundError: Se o relato não existir ou não pertencer à empresa.
        """
        report = await self._repo.get_by_id(report_id)
        if report is None or report.company_id != company_id:
            raise NotFoundError("Relato", report_id)
        return report

    async def respond(
        self,
        report_id: UUID,
        company_id: UUID,
        resposta_institucional: str,
        status: WhistleblowerStatus,
        respondido_por: UUID,
    ) -> Any:
        """Registra a resposta institucional ao relato.

        Apenas os status em_analise, concluido e arquivado são válidos
        para a resposta — 'recebido' não é uma transição válida neste método.

        Args:
            report_id: UUID do relato a responder.
            company_id: UUID da empresa autenticada (validação de tenant).
            resposta_institucional: Texto da resposta oficial.
            status: Novo status do relato.
            respondido_por: UUID do usuário que registra a resposta.

        Returns:
            O WhistleblowerReport atualizado.

        Raises:
            ValidationError: Se o status não for válido para uma resposta.
            NotFoundError: Se o relato não existir ou não pertencer à empresa.
        """
        if status not in _STATUS_VALIDOS_RESPOSTA:
            raise ValidationError(
                f"Status inválido para resposta. Use: "
                f"{', '.join(s.value for s in _STATUS_VALIDOS_RESPOSTA)}.",
                field="status",
            )

        report = await self._repo.update_resposta(
            report_id=report_id,
            resposta_institucional=resposta_institucional,
            status=status,
            respondido_por=respondido_por,
        )

        if report is None or report.company_id != company_id:
            raise NotFoundError("Relato", report_id)

        logger.info(
            "Resposta institucional registrada: report_id=%s status=%s respondido_por=%s",
            report_id,
            status.value,
            respondido_por,
        )

        return report
