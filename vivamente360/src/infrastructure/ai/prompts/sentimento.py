"""Prompt template para análise de sentimento agregado de um setor — versão 1.0.

Versão do prompt: v1.0
Modelo alvo: openai/gpt-4o-mini ou superior

Diferencia-se do AnalyzeSentimentHandler (que analisa respostas individuais):
este prompt analisa o sentimento coletivo de um setor inteiro, retornando
um diagnóstico agregado em vez de uma classificação por resposta.
"""

PROMPT_VERSION: str = "v1.0"
TEMPERATURE: float = 0.1
MAX_TOKENS: int = 800

PROMPT_SENTIMENTO_SYSTEM: str = (
    "Você é um especialista em análise de sentimento organizacional e bem-estar no trabalho. "
    "Analise o conjunto de depoimentos anônimos e retorne uma avaliação agregada do clima "
    "psicossocial do setor. "
    "Responda EXCLUSIVAMENTE em JSON válido — sem texto adicional, sem markdown, sem ```json."
)

PROMPT_SENTIMENTO_USER: str = (
    "Analise os {total} depoimentos anônimos do setor {setor_nome} "
    "e retorne uma avaliação agregada do sentimento coletivo.\n\n"
    "Depoimentos (anonimizados):\n"
    "{depoimentos}\n\n"
    "Retorne o seguinte JSON:\n"
    "{{\n"
    '  "sentimento_geral": "positivo|neutro|negativo|critico",\n'
    '  "score_medio": 0.0,\n'
    '  "distribuicao": {{\n'
    '    "positivo": 0,\n'
    '    "neutro": 0,\n'
    '    "negativo": 0,\n'
    '    "critico": 0\n'
    "  }},\n"
    '  "temas_negativos_recorrentes": ["tema1", "tema2"],\n'
    '  "temas_positivos_recorrentes": ["tema1", "tema2"],\n'
    '  "alertas_lgpd": []\n'
    "}}\n\n"
    "Regras:\n"
    "- score_medio: decimal entre -1.0 (muito negativo) e +1.0 (muito positivo)\n"
    "- distribuicao: contagem de depoimentos por classificação\n"
    "- alertas_lgpd: SEMPRE array vazio — confirma que nenhum dado identificável foi detectado"
)
