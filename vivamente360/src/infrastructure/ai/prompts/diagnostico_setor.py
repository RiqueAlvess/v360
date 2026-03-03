"""Prompt template para diagnóstico psicossocial por setor — versão 1.0.

Versão do prompt: v1.0
Modelo alvo: openai/gpt-4o-mini ou superior

Instrução de uso:
    Substitua as variáveis {total}, {setor_nome}, {depoimentos} e {scores_dimensoes}
    antes de enviar à API. Use PROMPT_DIAGNOSTICO_SYSTEM como system message
    e o conteúdo montado como user message.

Rastreabilidade:
    O campo prompt_versao em AiAnalysis armazena PROMPT_VERSION para que
    futuras mudanças de prompt não invalidem análises históricas.
"""

# Versão deste template — SEMPRE incrementar ao alterar o prompt
PROMPT_VERSION: str = "v1.0"

# Temperatura recomendada para este prompt (baixa = respostas mais consistentes)
TEMPERATURE: float = 0.2

# Limite de tokens para a resposta da IA
MAX_TOKENS: int = 1500

PROMPT_DIAGNOSTICO_SYSTEM: str = (
    "Você é um especialista em saúde psicossocial no trabalho e na NR-1 brasileira. "
    "Analise depoimentos anônimos de colaboradores coletados em avaliação de riscos "
    "psicossociais (framework HSE-IT). "
    "Responda EXCLUSIVAMENTE em JSON válido — sem texto adicional, sem markdown, sem ```json. "
    "O JSON deve ter exatamente a estrutura solicitada, sem campos extras."
)

PROMPT_DIAGNOSTICO_USER: str = (
    "Analise os {total} depoimentos anônimos de colaboradores do setor {setor_nome} "
    "coletados na campanha de avaliação de riscos psicossociais.\n\n"
    "Depoimentos (anonimizados):\n"
    "{depoimentos}\n\n"
    "Scores HSE-IT do setor (escala 1-5, onde 5 = melhor):\n"
    "{scores_dimensoes}\n\n"
    "Responda EXCLUSIVAMENTE em JSON com a estrutura abaixo. "
    "Não inclua explicações fora do JSON:\n"
    "{{\n"
    '  "resumo_executivo": "string (máx 200 palavras, tom profissional)",\n'
    '  "principais_temas": ["tema1", "tema2", "tema3"],\n'
    '  "dimensoes_criticas": ["dimensao1", "dimensao2"],\n'
    '  "recomendacoes": [\n'
    '    {{"titulo": "...", "prioridade": "alta|media|baixa", "prazo": "imediato|30d|90d"}}\n'
    "  ],\n"
    '  "alertas_lgpd": []\n'
    "}}"
)
