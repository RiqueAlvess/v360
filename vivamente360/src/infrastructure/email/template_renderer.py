"""Renderizador de templates HTML para emails.

Usa string.Template (stdlib) para substituição de variáveis com sintaxe ${variable}.
Lê templates do diretório src/infrastructure/email/templates/.
"""
import logging
from pathlib import Path
from string import Template
from typing import Any

logger = logging.getLogger(__name__)

# Assuntos padrão por template
_SUBJECTS: dict[str, str] = {
    "invitation_email": "Você foi convidado para participar de uma pesquisa — VIVAMENTE 360°",
    "reminder_email": "Lembrete: sua pesquisa ainda está aberta — VIVAMENTE 360°",
    "results_ready_email": "Resultados da campanha disponíveis — VIVAMENTE 360°",
    "campaign_closed_email": "Campanha encerrada com sucesso — VIVAMENTE 360°",
    "action_plan_completed": "Plano de ação concluído com sucesso — VIVAMENTE 360°",
}

_TEMPLATES_DIR: Path = Path(__file__).parent / "templates"


class TemplateRenderer:
    """Carrega e renderiza templates HTML para envio via EmailService.

    Responsabilidades:
    - Ler o arquivo HTML do template pelo nome.
    - Substituir variáveis usando string.Template (${variable}).
    - Retornar o par (subject, html_body) pronto para o ResendAdapter.
    """

    def render(
        self,
        template_name: str,
        context: dict[str, Any],
    ) -> tuple[str, str]:
        """Renderiza um template HTML com as variáveis do contexto.

        Args:
            template_name: Nome do template sem extensão (ex: 'invitation_email').
            context: Dicionário com as variáveis a substituir no template.

        Returns:
            Tupla (subject, html_body) com os valores renderizados.

        Raises:
            FileNotFoundError: Se o template não existir no diretório de templates.
            KeyError: Se uma variável obrigatória estiver ausente no contexto.
        """
        html_body = self._load_and_render(template_name, context)
        subject = _SUBJECTS.get(template_name, "Notificação — VIVAMENTE 360°")
        return subject, html_body

    def _load_and_render(self, template_name: str, context: dict[str, Any]) -> str:
        """Carrega o arquivo HTML e realiza a substituição de variáveis."""
        template_path = _TEMPLATES_DIR / f"{template_name}.html"
        if not template_path.exists():
            raise FileNotFoundError(
                f"Template '{template_name}' não encontrado em {_TEMPLATES_DIR}"
            )
        raw_html = template_path.read_text(encoding="utf-8")
        tmpl = Template(raw_html)
        # safe_substitute deixa variáveis não substituídas intactas (evita KeyError em CSS)
        rendered = tmpl.safe_substitute(context)
        logger.debug("Template '%s' renderizado com %d variáveis.", template_name, len(context))
        return rendered
