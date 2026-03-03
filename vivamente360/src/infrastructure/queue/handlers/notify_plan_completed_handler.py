"""Handler para tarefas do tipo 'notify_plan_completed'.

Payload esperado:
    {
        "plan_id": "<UUID do plano concluído>",
        "campaign_id": "<UUID da campanha>",
        "company_id": "<UUID da empresa>",
        "created_by": "<UUID do criador do plano>",
        "titulo": "<título do plano>",
        "observacao": "<observação opcional>",
        "concluido_em": "<ISO 8601 timestamp>"
    }

Fluxo:
    1. Valida o payload.
    2. Carrega o usuário criador do plano pelo UUID.
    3. Descriptografa o email do criador (AES-256-GCM).
    4. Cria registro em email_logs (status=PENDING).
    5. Enfileira task SEND_EMAIL com o contexto do plano concluído.
       (Adiciona à sessão — o worker comita ao final do handler.)

Regra R6: Email SEMPRE via EmailService / infraestrutura de email — nunca diretamente.
Regra R2: Handler não contém lógica de negócio — apenas orquestra infraestrutura.
"""
import logging
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.email_template_type import EmailTemplateType
from src.domain.enums.task_queue_type import TaskQueueType
from src.infrastructure.database.models.task_queue import TaskQueue
from src.infrastructure.database.models.user import User as UserModel
from src.infrastructure.queue.base_handler import BaseTaskHandler
from src.infrastructure.repositories.email_log_repository import SQLEmailLogRepository
from src.shared.config import settings
from src.shared.security import decrypt_data, hash_token

logger = logging.getLogger(__name__)

# Campos obrigatórios no payload desta tarefa
_REQUIRED_FIELDS: frozenset[str] = frozenset(
    {
        "plan_id",
        "campaign_id",
        "company_id",
        "created_by",
        "titulo",
        "concluido_em",
    }
)


class NotifyPlanCompletedHandler(BaseTaskHandler):
    """Processa notificações de conclusão de Plano de Ação.

    Ao ser disparado, carrega o criador do plano, decifra seu email e
    enfileira um email de notificação via task SEND_EMAIL — nunca envia
    diretamente pelo SDK Resend (Regra R6).

    A tarefa SEND_EMAIL criada neste handler é adicionada à sessão sem
    commit explícito — o worker da fila faz o commit ao final do ciclo.
    """

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        self._email_log_repo = SQLEmailLogRepository(db)

    async def execute(self, payload: dict[str, Any]) -> None:
        """Processa a notificação de conclusão de plano.

        Args:
            payload: Dicionário com os dados do plano concluído.

        Raises:
            ValueError: Se o payload estiver incompleto ou com UUIDs inválidos.
            RuntimeError: Se o usuário criador não for encontrado no banco.
        """
        self._validate_payload(payload)

        plan_id: UUID = self._parse_uuid(payload["plan_id"], "plan_id")
        created_by: UUID = self._parse_uuid(payload["created_by"], "created_by")
        titulo: str = payload["titulo"]
        observacao: str | None = payload.get("observacao")
        concluido_em: str = payload["concluido_em"]

        logger.info(
            "Processando notificação de conclusão: plan_id=%s created_by=%s",
            plan_id,
            created_by,
        )

        # -----------------------------------------------------------------
        # 1. Carregar o usuário criador do plano
        # -----------------------------------------------------------------
        user_result = await self._db.execute(
            select(UserModel).where(UserModel.id == created_by)
        )
        user = user_result.scalar_one_or_none()

        if user is None:
            raise RuntimeError(
                f"Usuário criador não encontrado para notificação: user_id={created_by}"
            )

        # -----------------------------------------------------------------
        # 2. Decifrar email do criador — plaintext apenas em memória
        # -----------------------------------------------------------------
        destinatario_email: str = decrypt_data(
            user.email_criptografado.decode("utf-8"),
            settings.ENCRYPTION_KEY,
        )
        destinatario_hash: str = hash_token(destinatario_email.lower().strip())

        logger.info(
            "Notificando criador: plan_id=%s user_id=%s hash=%.8s…",
            plan_id,
            created_by,
            destinatario_hash,
        )

        # -----------------------------------------------------------------
        # 3. Criar email_log com status PENDING (flush, sem commit)
        # -----------------------------------------------------------------
        email_log = await self._email_log_repo.create(
            tipo=EmailTemplateType.ACTION_PLAN_COMPLETED.value,
            destinatario_hash=destinatario_hash,
        )

        # -----------------------------------------------------------------
        # 4. Preparar contexto do template e criptografar email para o payload
        # -----------------------------------------------------------------
        from src.shared.security import encrypt_data  # local import — evita circular
        destinatario_criptografado: str = encrypt_data(
            destinatario_email,
            settings.ENCRYPTION_KEY,
        )

        template_context: dict[str, Any] = {
            "nome_responsavel": user.nome or "Responsável",
            "titulo_plano": titulo,
            "concluido_em": concluido_em,
            "observacao": observacao or "",
        }

        # -----------------------------------------------------------------
        # 5. Criar task SEND_EMAIL diretamente na sessão (sem commit)
        #    O worker comita ao final do ciclo — mantém atomicidade.
        # -----------------------------------------------------------------
        send_email_task = TaskQueue(
            id=uuid.uuid4(),
            tipo=TaskQueueType.SEND_EMAIL,
            payload={
                "email_log_id": str(email_log.id),
                "destinatario_hash": destinatario_hash,
                "destinatario_criptografado": destinatario_criptografado,
                "template": EmailTemplateType.ACTION_PLAN_COMPLETED.value,
                "context": template_context,
                "tipo_email": EmailTemplateType.ACTION_PLAN_COMPLETED.value,
            },
        )
        self._db.add(send_email_task)

        logger.info(
            "Notificação enfileirada com sucesso: plan_id=%s email_log_id=%s",
            plan_id,
            email_log.id,
        )

    def _validate_payload(self, payload: dict[str, Any]) -> None:
        """Verifica que todos os campos obrigatórios estão presentes.

        Args:
            payload: Payload recebido da tarefa.

        Raises:
            ValueError: Se algum campo obrigatório estiver ausente.
        """
        missing = _REQUIRED_FIELDS - payload.keys()
        if missing:
            raise ValueError(
                f"Payload inválido para notify_plan_completed. "
                f"Campos ausentes: {sorted(missing)}"
            )

    def _parse_uuid(self, value: str, field_name: str) -> UUID:
        """Converte string para UUID com mensagem de erro descritiva.

        Args:
            value: String a converter.
            field_name: Nome do campo para mensagem de erro.

        Returns:
            UUID convertido.

        Raises:
            ValueError: Se o valor não for um UUID válido.
        """
        try:
            return UUID(value)
        except (ValueError, AttributeError) as exc:
            raise ValueError(
                f"Campo '{field_name}' não é um UUID válido: {value!r}"
            ) from exc
