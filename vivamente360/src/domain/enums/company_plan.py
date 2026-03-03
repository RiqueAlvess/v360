from enum import Enum


class CompanyPlan(str, Enum):
    """Planos de assinatura disponíveis para empresas na plataforma."""

    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
