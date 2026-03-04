"""Service do módulo de Análise por IA (Módulo 06).

Regra R2: Services orquestram — não acessam Infrastructure diretamente.
Regra R1: Type hints completos em todos os métodos e parâmetros.

Regra inviolável do módulo:
    Nenhum método deste service chama o OpenRouter/LLM diretamente.
    Toda chamada à IA é enfileirada via task_queue → RunAiAnalysisHandler.
    Este service gerencia apenas:
    - Criação de registros de análise com status 'pending'
    - Consulta de status/resultado via repositório
    - Agregação de análises concluídas para resumo executivo
    - Verificação de rate limit por empresa

Fluxo de análise:
    1. POST /ai-analyses/request → AIAnalysisService.request_analysis()
    2. Service cria registro 'pending' + enfileira RunAiAnalysisTask
    3. Worker consome task → RunAiAnalysisHandler processa
    4. Handler atualiza status para 'completed' ou 'failed'
    5. GET /ai-analyses/{id} → polling do status/resultado
"""
import math
from typing import Any, Optional
from uuid import UUID

from src.domain.enums.task_queue_type import TaskQueueType
from src.infrastructure.queue.task_service import TaskService
from src.infrastructure.repositories.ai_analysis_repository import (
    AiAnalysisRepository,
)
from src.shared.config import settings
from src.shared.exceptions import RateLimitError, ValidationError


class AIAnalysisService:
    """Orquestra o ciclo de vida de análises de IA.

    Responsável por:
    - Solicitar análise (cria registro pending + enfileira tarefa)
    - Consultar status/resultado de uma análise
    - Listar análises de uma campanha com paginação
    - Agregar resultados concluídos em resumo executivo
    - Verificar rate limit por empresa antes de criar análises

    Não chama diretamente o OpenRouter — toda análise passa pelo worker.
    """

    def __init__(
        self,
        analysis_repo: AiAnalysisRepository,
        task_service: TaskService,
    ) -> None:
        self._repo = analysis_repo
        self._task_service = task_service

    async def request_analysis(
        self,
        company_id: UUID,
        campaign_id: UUID,
        tipo: str,
        requested_by: UUID,
        setor_id: Optional[UUID] = None,
        dimensao: Optional[str] = None,
    ) -> dict[str, Any]:
        """Cria registro de análise e enfileira a tarefa de processamento.

        Valida o rate limit antes de criar — máximo OPENROUTER_RATE_LIMIT_PER_HOUR
        análises por empresa por hora.

        Args:
            company_id: UUID da empresa solicitante.
            campaign_id: UUID da campanha a analisar.
            tipo: Tipo de análise ('sentimento', 'diagnostico', 'recomendacoes').
            requested_by: UUID do usuário que solicitou.
            setor_id: UUID do setor (opcional — None = campanha inteira).
            dimensao: Dimensão HSE-IT de foco (opcional).

        Returns:
            Dict com analysis_id e status='pending'.

        Raises:
            ValidationError: Se o tipo de análise for inválido.
            RateLimitError: Se o rate limit por empresa/hora for excedido.
        """
        _VALID_TIPOS: frozenset[str] = frozenset(
            {"sentimento", "diagnostico", "recomendacoes"}
        )
        if tipo not in _VALID_TIPOS:
            raise ValidationError(
                detail=(
                    f"Tipo de análise inválido: {tipo!r}. "
                    f"Aceitos: {sorted(_VALID_TIPOS)}"
                )
            )

        # Verificar rate limit por empresa
        count_last_hour: int = await self._repo.count_by_company_last_hour(company_id)
        if count_last_hour >= settings.OPENROUTER_RATE_LIMIT_PER_HOUR:
            raise RateLimitError(
                detail=(
                    f"Rate limit excedido: máximo {settings.OPENROUTER_RATE_LIMIT_PER_HOUR} "
                    f"análises por empresa por hora. Tente novamente mais tarde."
                )
            )

        # Criar registro com status 'pending'
        analysis = await self._repo.create(
            company_id=company_id,
            campaign_id=campaign_id,
            tipo=tipo,
            setor_id=setor_id,
            dimensao=dimensao,
        )

        # Enfileirar tarefa de processamento assíncrono
        await self._task_service.enqueue(
            tipo=TaskQueueType.RUN_AI_ANALYSIS,
            payload={
                "analysis_id": str(analysis.id),
                "campaign_id": str(campaign_id),
                "company_id": str(company_id),
                "requested_by": str(requested_by),
                "setor_id": str(setor_id) if setor_id else None,
                "dimensao": dimensao,
                "tipo": tipo,
            },
        )

        return {
            "analysis_id": analysis.id,
            "status": "pending",
        }

    async def get_analysis(
        self,
        analysis_id: UUID,
        company_id: UUID,
    ) -> dict[str, Any]:
        """Retorna o status e resultado de uma análise pelo UUID.

        Args:
            analysis_id: UUID da análise.
            company_id: UUID da empresa (validação de ownership).

        Returns:
            Dict com todos os campos da AiAnalysis.

        Raises:
            NotFoundError: Se a análise não existir ou não pertencer à empresa.
        """
        from src.shared.exceptions import NotFoundError

        analysis = await self._repo.get_by_id(analysis_id)
        if analysis is None or analysis.company_id != company_id:
            raise NotFoundError("Análise", analysis_id)
        return analysis

    async def list_analyses(
        self,
        company_id: UUID,
        campaign_id: UUID,
        tipo: Optional[str] = None,
        analysis_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Lista análises de uma campanha com filtros opcionais e paginação.

        Args:
            company_id: UUID da empresa (validação de ownership).
            campaign_id: UUID da campanha.
            tipo: Filtro opcional por tipo ('sentimento', 'diagnostico', 'recomendacoes').
            analysis_status: Filtro opcional por status.
            page: Número da página (1-indexed).
            page_size: Itens por página (máximo 100).

        Returns:
            Dict com 'items', 'pagination' e metadados.
        """
        items, total = await self._repo.get_by_campaign(
            campaign_id=campaign_id,
            page=page,
            page_size=page_size,
            tipo=tipo,
            status=analysis_status,
        )

        pages: int = max(1, math.ceil(total / page_size)) if total > 0 else 1

        return {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": pages,
            },
        }

    async def get_summary(
        self,
        campaign_id: UUID,
        company_id: UUID,
    ) -> dict[str, Any]:
        """Agrega análises concluídas de uma campanha em resumo executivo.

        Args:
            campaign_id: UUID da campanha.
            company_id: UUID da empresa (validação de ownership — não usada diretamente
                        pois o RLS do banco garante o isolamento).

        Returns:
            Dict com totais, por_setor e recomendacoes_priorizadas.
        """
        # Total de análises da campanha (todos os status)
        all_items, total = await self._repo.get_by_campaign(
            campaign_id=campaign_id,
            page=1,
            page_size=100,
        )

        # Apenas as concluídas para agregação de conteúdo
        completed = await self._repo.get_completed_by_campaign(campaign_id=campaign_id)

        total_completed = sum(1 for i in all_items if i.status == "completed")
        total_pending = sum(1 for i in all_items if i.status in {"pending", "processing"})
        total_failed = sum(1 for i in all_items if i.status == "failed")

        tokens_input_total = sum((i.tokens_input or 0) for i in all_items)
        tokens_output_total = sum((i.tokens_output or 0) for i in all_items)

        # Agrupar por setor
        por_setor: list[dict[str, Any]] = []
        por_setor_dict: dict[str, dict[str, Any]] = {}
        for analysis in completed:
            key = str(analysis.setor_id) if analysis.setor_id else "geral"
            if key not in por_setor_dict:
                por_setor_dict[key] = {
                    "setor_id": analysis.setor_id,
                    "total_analyses": 0,
                    "tipos_concluidos": [],
                    "ultimo_resultado": None,
                    "ultimo_modelo": None,
                    "tokens_total": 0,
                }
            entry = por_setor_dict[key]
            entry["total_analyses"] += 1
            if analysis.tipo not in entry["tipos_concluidos"]:
                entry["tipos_concluidos"].append(analysis.tipo)
            entry["ultimo_resultado"] = analysis.resultado
            entry["ultimo_modelo"] = analysis.model_usado
            entry["tokens_total"] += (analysis.tokens_input or 0) + (
                analysis.tokens_output or 0
            )

        por_setor = list(por_setor_dict.values())

        # Extrair e priorizar recomendações
        recomendacoes: list[dict[str, Any]] = []
        prioridade_ordem: dict[str, int] = {"alta": 0, "media": 1, "baixa": 2}
        prazo_ordem: dict[str, int] = {"imediato": 0, "30d": 1, "90d": 2}

        for analysis in completed:
            if analysis.tipo != "diagnostico" or not analysis.resultado:
                continue
            recs: list[dict[str, Any]] = analysis.resultado.get("recomendacoes", [])
            for rec in recs:
                if isinstance(rec, dict) and rec.get("titulo"):
                    recomendacoes.append(
                        {
                            "titulo": rec.get("titulo", ""),
                            "prioridade": rec.get("prioridade", "media"),
                            "prazo": rec.get("prazo", "90d"),
                            "setor_id": analysis.setor_id,
                            "analysis_id": analysis.id,
                        }
                    )

        recomendacoes.sort(
            key=lambda r: (
                prioridade_ordem.get(r["prioridade"], 99),
                prazo_ordem.get(r["prazo"], 99),
            )
        )

        return {
            "campaign_id": campaign_id,
            "total_analyses": total,
            "total_completed": total_completed,
            "total_pending": total_pending,
            "total_failed": total_failed,
            "tokens_input_total": tokens_input_total,
            "tokens_output_total": tokens_output_total,
            "por_setor": por_setor,
            "recomendacoes_priorizadas": recomendacoes,
        }
