# src/infrastructure/admin/views.py
"""ModelViews do SQLAdmin — painel global de administração.

Acessível em /sqladmin com autenticação própria (separada do JWT da app).
NÃO usa RLS por design — super admin vê dados de todos os tenants.
Regra R2: infraestrutura de admin fica em infrastructure/admin/, não vaza para domain.
"""
from sqladmin import ModelView

from src.infrastructure.database.models.campaign import Campaign
from src.infrastructure.database.models.company import Company
from src.infrastructure.database.models.user import User


class CompanyAdmin(ModelView, model=Company):
    """CRUD de empresas contratantes."""

    name = "Empresa"
    name_plural = "Empresas"
    icon = "fa-solid fa-building"

    column_list = [
        Company.id,
        Company.nome,
        Company.cnpj,
        Company.slug,
        Company.plano,
        Company.ativo,
        Company.created_at,
    ]
    column_searchable_list = [Company.nome, Company.cnpj]
    column_sortable_list = [Company.nome, Company.ativo, Company.created_at]
    column_filters = ["ativo", "plano"]
    form_excluded_columns = [
        Company.created_at,
        Company.updated_at,
        Company.users,
        Company.campaigns,
        Company.organizational_units,
        Company.sectors,
        Company.job_positions,
    ]
    can_delete = False  # Nunca hard delete — use ativo=False


class UserAdmin(ModelView, model=User):
    """Visualização de usuários — sem expor dados sensíveis."""

    name = "Usuário"
    name_plural = "Usuários"
    icon = "fa-solid fa-users"

    column_list = [
        User.id,
        User.nome,
        User.role,
        User.company_id,
        User.ativo,
        User.created_at,
    ]
    column_searchable_list = [User.nome]
    column_sortable_list = [User.nome, User.role, User.ativo]
    column_filters = ["role", "ativo"]
    form_excluded_columns = [
        User.email_criptografado,
        User.email_hash,
        User.hashed_password,
        User.created_at,
        User.updated_at,
    ]
    can_delete = False


class CampaignAdmin(ModelView, model=Campaign):
    """Visualização read-only de campanhas para auditoria global."""

    name = "Campanha"
    name_plural = "Campanhas"
    icon = "fa-solid fa-clipboard-list"

    column_list = [
        Campaign.id,
        Campaign.nome,
        Campaign.company_id,
        Campaign.status,
        Campaign.created_at,
    ]
    column_searchable_list = [Campaign.nome]
    column_sortable_list = [Campaign.nome, Campaign.status, Campaign.created_at]
    column_filters = ["status"]

    can_create = False
    can_edit = False
    can_delete = False
