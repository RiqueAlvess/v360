-- =============================================================================
-- VIVAMENTE 360º — Row Level Security Policies
-- =============================================================================
-- Este arquivo é aplicado via migration 002_rls_policies.
-- Cada transação de aplicação DEVE executar antes de qualquer query:
--   SET LOCAL app.company_id = '<uuid-da-empresa>';
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Habilitar RLS nas tabelas de negócio
-- -----------------------------------------------------------------------------
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE survey_responses ENABLE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------
-- 2. Criar role de aplicação separado do superuser
--    O app_user NÃO tem BYPASSRLS — toda query passa pelas policies.
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user;
    END IF;
END
$$;

-- Permissões de acesso ao banco e às tabelas do schema public
GRANT CONNECT ON DATABASE vivamente360 TO app_user;
GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- -----------------------------------------------------------------------------
-- 3. Policies de isolamento por tenant
-- -----------------------------------------------------------------------------

-- Companies: cada empresa só enxerga a si mesma
DROP POLICY IF EXISTS tenant_isolation_companies ON companies;
CREATE POLICY tenant_isolation_companies ON companies
    AS PERMISSIVE
    FOR ALL
    TO app_user
    USING (id = current_setting('app.company_id', true)::uuid);

-- Campaigns: filtro direto por company_id
DROP POLICY IF EXISTS tenant_isolation_campaigns ON campaigns;
CREATE POLICY tenant_isolation_campaigns ON campaigns
    AS PERMISSIVE
    FOR ALL
    TO app_user
    USING (company_id = current_setting('app.company_id', true)::uuid);

-- Invitations: acesso via campaigns da empresa (join implícito)
DROP POLICY IF EXISTS tenant_isolation_invitations ON invitations;
CREATE POLICY tenant_isolation_invitations ON invitations
    AS PERMISSIVE
    FOR ALL
    TO app_user
    USING (
        campaign_id IN (
            SELECT id FROM campaigns
            WHERE company_id = current_setting('app.company_id', true)::uuid
        )
    );

-- Survey responses: acesso via campaigns da empresa (preserva anonimato, isola por tenant)
DROP POLICY IF EXISTS tenant_isolation_survey_responses ON survey_responses;
CREATE POLICY tenant_isolation_survey_responses ON survey_responses
    AS PERMISSIVE
    FOR ALL
    TO app_user
    USING (
        campaign_id IN (
            SELECT id FROM campaigns
            WHERE company_id = current_setting('app.company_id', true)::uuid
        )
    );

-- -----------------------------------------------------------------------------
-- 4. Tabelas sem RLS (acesso controlado exclusivamente pela service layer)
--    - users: acesso via service layer com validação de company_id
--    - refresh_tokens: acesso via AuthService — sem contexto de tenant
--    - task_queue: processado pelo worker com conexão privilegiada
--    - email_logs: auditoria lida pelo admin com conexão privilegiada
-- -----------------------------------------------------------------------------
-- Nota: users tem RLS implícito via company_id, mas o isolamento
-- é garantido pela UniqueConstraint(company_id, email_hash) e
-- pelos filtros na camada de repositório.
