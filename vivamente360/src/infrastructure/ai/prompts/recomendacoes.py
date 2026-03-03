"""Prompt template para geração de recomendações de ação — versão 1.0.

Versão do prompt: v1.0
Modelo alvo: openai/gpt-4o-mini ou superior

Focado em gerar um plano de ações priorizadas para uma dimensão específica
do HSE-IT com base nos scores e diagnóstico existente.
"""

PROMPT_VERSION: str = "v1.0"
TEMPERATURE: float = 0.3
MAX_TOKENS: int = 1200

PROMPT_RECOMENDACOES_SYSTEM: str = (
    "Você é um consultor especialista em saúde e segurança do trabalho, "
    "com foco em riscos psicossociais e conformidade com a NR-1 brasileira. "
    "Gere recomendações práticas, priorizadas e acionáveis para reduzir riscos "
    "psicossociais identificados. "
    "Responda EXCLUSIVAMENTE em JSON válido — sem texto adicional, sem markdown, sem ```json."
)

PROMPT_RECOMENDACOES_USER: str = (
    "Com base nos dados abaixo do setor {setor_nome}, gere recomendações de ação "
    "para melhorar os indicadores de saúde psicossocial.\n\n"
    "Scores HSE-IT por dimensão (escala 1-5, onde 5 = melhor):\n"
    "{scores_dimensoes}\n\n"
    "Resumo do diagnóstico:\n"
    "{resumo_diagnostico}\n\n"
    "Dimensão foco (se aplicável): {dimensao_foco}\n\n"
    "Gere recomendações práticas no seguinte formato JSON:\n"
    "{{\n"
    '  "recomendacoes": [\n'
    "    {{\n"
    '      "titulo": "Título conciso da ação",\n'
    '      "descricao": "Descrição detalhada (2-4 frases)",\n'
    '      "prioridade": "alta|media|baixa",\n'
    '      "prazo": "imediato|30d|90d",\n'
    '      "dimensao_alvo": "nome_da_dimensao_hse",\n'
    '      "responsavel_sugerido": "RH|Liderança|Diretoria|Equipe"\n'
    "    }}\n"
    "  ],\n"
    '  "alertas_lgpd": []\n'
    "}}"
)
