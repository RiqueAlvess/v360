"""Seed dos templates canônicos NR-1 (Portaria MTE 1.419/2024).

Popula a tabela checklist_templates com os 15 itens obrigatórios da NR-1
revisada. O script é idempotente — verifica a existência por `codigo` antes
de inserir, evitando duplicatas em execuções repetidas.

Uso:
    # A partir do diretório vivamente360/
    python -m seeds.checklist_nr1

    # Com DATABASE_URL explícita
    DATABASE_URL=postgresql+asyncpg://... python -m seeds.checklist_nr1
"""
import asyncio
import sys
import uuid
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Importar models — garante que o metadata do Base está populado
# ---------------------------------------------------------------------------
# Adiciona o diretório pai ao path para importar `src`
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.database.models.checklist_template import ChecklistTemplate  # noqa: E402
from src.shared.config import settings  # noqa: E402

# ---------------------------------------------------------------------------
# Templates canônicos NR-1 — Portaria MTE 1.419/2024
# Fonte: https://www.gov.br/trabalho-e-emprego/pt-br/acesso-a-informacao/normas-regulamentadoras/nr-1
# ---------------------------------------------------------------------------

NR1_TEMPLATES: Final[list[dict]] = [
    # -----------------------------------------------------------------------
    # Categoria: Identificação de Riscos
    # -----------------------------------------------------------------------
    {
        "codigo": "NR1-1.1",
        "categoria": "Identificação",
        "descricao": (
            "Identificar e classificar os perigos e riscos psicossociais no ambiente de trabalho "
            "conforme metodologia reconhecida (ex: HSE-IT, COPSOQ ou equivalente validado)."
        ),
        "obrigatorio": True,
        "prazo_dias": 30,
        "ordem": 1,
    },
    {
        "codigo": "NR1-1.2",
        "categoria": "Identificação",
        "descricao": (
            "Realizar avaliação quantitativa dos riscos psicossociais identificados "
            "utilizando instrumento validado (HSE-IT ou equivalente), com participação "
            "de representantes dos trabalhadores."
        ),
        "obrigatorio": True,
        "prazo_dias": 60,
        "ordem": 2,
    },
    # -----------------------------------------------------------------------
    # Categoria: Participação dos Trabalhadores
    # -----------------------------------------------------------------------
    {
        "codigo": "NR1-2.1",
        "categoria": "Participação",
        "descricao": (
            "Garantir a participação efetiva dos trabalhadores no processo de identificação "
            "e avaliação dos riscos psicossociais, assegurando representatividade de todos "
            "os setores e grupos ocupacionais."
        ),
        "obrigatorio": True,
        "prazo_dias": 45,
        "ordem": 3,
    },
    {
        "codigo": "NR1-2.2",
        "categoria": "Participação",
        "descricao": (
            "Documentar o processo de participação dos trabalhadores, registrando os mecanismos "
            "utilizados (reuniões, consultas, questionários) e os resultados obtidos."
        ),
        "obrigatorio": True,
        "prazo_dias": 60,
        "ordem": 4,
    },
    # -----------------------------------------------------------------------
    # Categoria: GRO — Gerenciamento de Riscos Ocupacionais
    # -----------------------------------------------------------------------
    {
        "codigo": "NR1-3.1",
        "categoria": "GRO",
        "descricao": (
            "Elaborar ou atualizar o Programa de Gerenciamento de Riscos Ocupacionais (GRO) "
            "incluindo explicitamente os riscos psicossociais identificados e as medidas "
            "de controle previstas."
        ),
        "obrigatorio": True,
        "prazo_dias": 90,
        "ordem": 5,
    },
    {
        "codigo": "NR1-3.2",
        "categoria": "GRO",
        "descricao": (
            "Revisar e atualizar o GRO ao menos anualmente ou após mudanças organizacionais "
            "significativas (reestruturações, fusões, mudanças de processos) que possam "
            "impactar os riscos psicossociais."
        ),
        "obrigatorio": True,
        "prazo_dias": 365,
        "ordem": 6,
    },
    # -----------------------------------------------------------------------
    # Categoria: Plano de Ação
    # -----------------------------------------------------------------------
    {
        "codigo": "NR1-4.1",
        "categoria": "Plano de Ação",
        "descricao": (
            "Elaborar plano de ação estruturado para controle, redução e eliminação dos "
            "riscos psicossociais identificados, priorizando medidas preventivas e "
            "organizacionais sobre medidas individuais."
        ),
        "obrigatorio": True,
        "prazo_dias": 90,
        "ordem": 7,
    },
    {
        "codigo": "NR1-4.2",
        "categoria": "Plano de Ação",
        "descricao": (
            "Definir responsáveis (por nome e cargo), prazos específicos e recursos "
            "necessários para cada medida de controle prevista no plano de ação."
        ),
        "obrigatorio": True,
        "prazo_dias": 90,
        "ordem": 8,
    },
    {
        "codigo": "NR1-4.3",
        "categoria": "Plano de Ação",
        "descricao": (
            "Monitorar periodicamente a execução e eficácia das medidas implementadas, "
            "registrando o progresso, ajustes realizados e indicadores de melhoria."
        ),
        "obrigatorio": True,
        "prazo_dias": 180,
        "ordem": 9,
    },
    # -----------------------------------------------------------------------
    # Categoria: Comunicação
    # -----------------------------------------------------------------------
    {
        "codigo": "NR1-5.1",
        "categoria": "Comunicação",
        "descricao": (
            "Comunicar os resultados da avaliação de riscos psicossociais e as medidas "
            "adotadas a todos os trabalhadores, de forma clara e acessível, em linguagem "
            "adequada ao público."
        ),
        "obrigatorio": True,
        "prazo_dias": 30,
        "ordem": 10,
    },
    {
        "codigo": "NR1-5.2",
        "categoria": "Comunicação",
        "descricao": (
            "Disponibilizar e divulgar canais de comunicação e denúncia para relatos de "
            "situações de violência, assédio moral e sexual, garantindo confidencialidade "
            "e proteção ao denunciante."
        ),
        "obrigatorio": True,
        "prazo_dias": 30,
        "ordem": 11,
    },
    # -----------------------------------------------------------------------
    # Categoria: Capacitação
    # -----------------------------------------------------------------------
    {
        "codigo": "NR1-6.1",
        "categoria": "Capacitação",
        "descricao": (
            "Capacitar gestores, lideranças e membros da CIPA sobre identificação, "
            "prevenção e gestão de riscos psicossociais, incluindo conteúdo específico "
            "sobre NR-1 e legislação aplicável."
        ),
        "obrigatorio": True,
        "prazo_dias": 120,
        "ordem": 12,
    },
    {
        "codigo": "NR1-6.2",
        "categoria": "Capacitação",
        "descricao": (
            "Capacitar os trabalhadores sobre os riscos psicossociais presentes no "
            "ambiente de trabalho, seus direitos, os canais disponíveis para comunicação "
            "e as medidas de proteção implementadas pela empresa."
        ),
        "obrigatorio": True,
        "prazo_dias": 120,
        "ordem": 13,
    },
    # -----------------------------------------------------------------------
    # Categoria: Documentação
    # -----------------------------------------------------------------------
    {
        "codigo": "NR1-7.1",
        "categoria": "Documentação",
        "descricao": (
            "Manter registros documentados e rastreáveis de todas as avaliações de "
            "riscos psicossociais realizadas, incluindo metodologia, participantes, "
            "resultados e medidas adotadas."
        ),
        "obrigatorio": True,
        "prazo_dias": None,  # Contínuo — sem prazo específico
        "ordem": 14,
    },
    {
        "codigo": "NR1-7.2",
        "categoria": "Documentação",
        "descricao": (
            "Garantir a rastreabilidade e preservação de todos os documentos relacionados "
            "à gestão de riscos psicossociais por no mínimo 5 (cinco) anos, com acesso "
            "facilitado para fiscalização e auditoria."
        ),
        "obrigatorio": True,
        "prazo_dias": None,  # Contínuo — sem prazo específico
        "ordem": 15,
    },
]


async def seed_checklist_templates(session: AsyncSession) -> None:
    """Insere os templates NR-1 se ainda não existirem no banco.

    A verificação por `codigo` garante idempotência — execuções repetidas
    do script não duplicam registros.

    Args:
        session: Sessão AsyncSQLAlchemy ativa com transação aberta.
    """
    inserted: int = 0
    skipped: int = 0

    for template_data in NR1_TEMPLATES:
        # Verifica se o template já existe pelo código único
        result = await session.execute(
            select(ChecklistTemplate).where(
                ChecklistTemplate.codigo == template_data["codigo"]
            )
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            print(f"  ⏭  {template_data['codigo']} — já existe, ignorado.")
            skipped += 1
            continue

        template = ChecklistTemplate(
            id=uuid.uuid4(),
            codigo=template_data["codigo"],
            descricao=template_data["descricao"],
            categoria=template_data["categoria"],
            obrigatorio=template_data["obrigatorio"],
            prazo_dias=template_data["prazo_dias"],
            ordem=template_data["ordem"],
        )
        session.add(template)
        print(f"  ✓  {template_data['codigo']} — {template_data['categoria']}")
        inserted += 1

    await session.commit()
    print(
        f"\n  Seed concluído: {inserted} templates inseridos, {skipped} ignorados.\n"
    )


async def main() -> None:
    """Entry point do script de seed."""
    print("\n=== Seed: Checklist NR-1 (Portaria MTE 1.419/2024) ===\n")

    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
    )

    async_session: sessionmaker = sessionmaker(  # type: ignore[type-arg]
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        await seed_checklist_templates(session)

    await engine.dispose()
    print("=== Seed finalizado com sucesso. ===\n")


if __name__ == "__main__":
    asyncio.run(main())
