-- Inicialização do banco de dados VIVAMENTE 360º
-- Habilitar extensões necessárias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Habilitar Row Level Security por padrão (será ativado por tabela nas migrations)
-- Este script apenas garante que as extensões estejam disponíveis
