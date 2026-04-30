-- =============================================================
-- SETUP — Dashboard Financeiro
-- Execute este script no SQL Editor do Supabase
-- =============================================================

-- 1. USUÁRIOS
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Usuário padrão: admin / admin123
-- (SHA-256 de "admin123")
INSERT INTO users (username, password_hash)
VALUES ('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9')
ON CONFLICT (username) DO NOTHING;


-- 2. LANÇAMENTOS (CUSTOS)
CREATE TABLE IF NOT EXISTS lancamentos (
    id          BIGINT PRIMARY KEY,
    username    TEXT NOT NULL,
    data        DATE NOT NULL,
    descricao   TEXT NOT NULL,
    valor       NUMERIC(12, 2) NOT NULL,
    peso        INTEGER NOT NULL CHECK (peso IN (1, 2, 3)),
    status      TEXT NOT NULL DEFAULT 'Em Aberto'
                    CHECK (status IN ('Em Aberto', 'Pago', 'Atrasado')),
    juros_multa NUMERIC(6, 2) DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lanc_user_data
    ON lancamentos (username, data);


-- 3. DEPÓSITOS (RECEITAS)
CREATE TABLE IF NOT EXISTS depositos (
    id         BIGINT PRIMARY KEY,
    username   TEXT NOT NULL,
    data       DATE NOT NULL,
    valor      NUMERIC(12, 2) NOT NULL,
    descricao  TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dep_user_data
    ON depositos (username, data);


-- 4. METAS DE ECONOMIA
CREATE TABLE IF NOT EXISTS metas (
    id         SERIAL PRIMARY KEY,
    username   TEXT NOT NULL,
    ano_mes    TEXT NOT NULL,   -- formato: "YYYY-MM"
    meta       NUMERIC(12, 2) DEFAULT 0,
    guardado   NUMERIC(12, 2) DEFAULT 0,
    UNIQUE (username, ano_mes)
);

CREATE INDEX IF NOT EXISTS idx_metas_user_ano
    ON metas (username, ano_mes);


-- =============================================================
-- ROW LEVEL SECURITY (opcional mas recomendado)
-- Descomente se quiser que cada usuário veja só seus dados
-- =============================================================
-- ALTER TABLE lancamentos ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE depositos   ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE metas       ENABLE ROW LEVEL SECURITY;
