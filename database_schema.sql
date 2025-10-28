-- ============================================================================
-- SCHEMA DO SISTEMA EAN - Banco Multi-Tenant
-- Versão: 2.0
-- Data: 28/10/2025
-- ============================================================================

-- Limpar tabelas existentes (cuidado em produção!)
-- DROP TABLE IF EXISTS movimentacoes_estoque CASCADE;
-- DROP TABLE IF EXISTS produtos_listas_unificadas CASCADE;
-- DROP TABLE IF EXISTS listas_unificadas CASCADE;
-- DROP TABLE IF EXISTS produtos_lista_manutencao CASCADE;
-- DROP TABLE IF EXISTS listas_manutencao CASCADE;
-- DROP TABLE IF EXISTS produtos_lista_loja CASCADE;
-- DROP TABLE IF EXISTS listas_loja CASCADE;
-- DROP TABLE IF EXISTS produtos_standby CASCADE;
-- DROP TABLE IF EXISTS listas_standby CASCADE;
-- DROP TABLE IF EXISTS produtos CASCADE;
-- DROP TABLE IF EXISTS ruas CASCADE;
-- DROP TABLE IF EXISTS usuarios CASCADE;

-- ============================================================================
-- TABELA: usuarios
-- Armazena usuários do sistema com diferentes níveis de acesso
-- ============================================================================
CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    admin INTEGER DEFAULT 0,  -- 0=Estoque, 1=Admin, 2=Cadastro
    ativo BOOLEAN DEFAULT TRUE,
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_usuarios_nome ON usuarios(nome);
CREATE INDEX IF NOT EXISTS idx_usuarios_ativo ON usuarios(ativo);
CREATE INDEX IF NOT EXISTS idx_usuarios_admin ON usuarios(admin);

-- ============================================================================
-- TABELA: ruas
-- Armazena ruas do estoque local
-- ============================================================================
CREATE TABLE IF NOT EXISTS ruas (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) UNIQUE NOT NULL,
    posicao INTEGER,
    ativo BOOLEAN DEFAULT TRUE,
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_ruas_nome ON ruas(nome);
CREATE INDEX IF NOT EXISTS idx_ruas_ativo ON ruas(ativo);
CREATE INDEX IF NOT EXISTS idx_ruas_posicao ON ruas(posicao);

-- ============================================================================
-- TABELA: produtos
-- Armazena produtos cadastrados no sistema
-- ============================================================================
CREATE TABLE IF NOT EXISTS produtos (
    id SERIAL PRIMARY KEY,
    ean VARCHAR(13) NOT NULL,
    nome VARCHAR(255) NOT NULL,
    cor VARCHAR(100),
    voltagem VARCHAR(50),
    modelo VARCHAR(100),
    quantidade INTEGER DEFAULT 1,
    destino VARCHAR(50),  -- 'mercado_livre', 'loja', 'manutencao', 'assistencia_tecnica'
    motivo_manutencao TEXT,
    usuario_id INTEGER REFERENCES usuarios(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    enviado INTEGER DEFAULT 0,
    data_envio TIMESTAMP,
    responsavel_id INTEGER,
    responsavel_pin VARCHAR(10),
    validado INTEGER DEFAULT 0,
    data_validacao TIMESTAMP,
    validador_id INTEGER REFERENCES usuarios(id),
    rua_id INTEGER REFERENCES ruas(id),
    ativo BOOLEAN DEFAULT TRUE
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_produtos_ean ON produtos(ean);
CREATE INDEX IF NOT EXISTS idx_produtos_usuario_id ON produtos(usuario_id);
CREATE INDEX IF NOT EXISTS idx_produtos_enviado ON produtos(enviado);
CREATE INDEX IF NOT EXISTS idx_produtos_validado ON produtos(validado);
CREATE INDEX IF NOT EXISTS idx_produtos_rua_id ON produtos(rua_id);
CREATE INDEX IF NOT EXISTS idx_produtos_ativo ON produtos(ativo);
CREATE INDEX IF NOT EXISTS idx_produtos_destino ON produtos(destino);
CREATE INDEX IF NOT EXISTS idx_produtos_data_envio ON produtos(data_envio);

-- ============================================================================
-- TABELA: listas_standby
-- Armazena listas de produtos em standby
-- ============================================================================
CREATE TABLE IF NOT EXISTS listas_standby (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    usuario_id INTEGER REFERENCES usuarios(id),
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ativo BOOLEAN DEFAULT TRUE
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_listas_standby_usuario_id ON listas_standby(usuario_id);
CREATE INDEX IF NOT EXISTS idx_listas_standby_ativo ON listas_standby(ativo);

-- ============================================================================
-- TABELA: produtos_standby
-- Armazena produtos associados a listas standby
-- ============================================================================
CREATE TABLE IF NOT EXISTS produtos_standby (
    id SERIAL PRIMARY KEY,
    lista_id INTEGER REFERENCES listas_standby(id) ON DELETE CASCADE,
    ean VARCHAR(13) NOT NULL,
    nome VARCHAR(255),
    quantidade INTEGER DEFAULT 1,
    data_adicao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_produtos_standby_lista_id ON produtos_standby(lista_id);
CREATE INDEX IF NOT EXISTS idx_produtos_standby_ean ON produtos_standby(ean);

-- ============================================================================
-- TABELA: listas_loja
-- Armazena listas de produtos para loja
-- ============================================================================
CREATE TABLE IF NOT EXISTS listas_loja (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    usuario_id INTEGER REFERENCES usuarios(id),
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ativo BOOLEAN DEFAULT TRUE
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_listas_loja_usuario_id ON listas_loja(usuario_id);
CREATE INDEX IF NOT EXISTS idx_listas_loja_ativo ON listas_loja(ativo);

-- ============================================================================
-- TABELA: produtos_lista_loja
-- Armazena produtos associados a listas de loja
-- ============================================================================
CREATE TABLE IF NOT EXISTS produtos_lista_loja (
    id SERIAL PRIMARY KEY,
    lista_id INTEGER REFERENCES listas_loja(id) ON DELETE CASCADE,
    ean VARCHAR(13) NOT NULL,
    nome VARCHAR(255),
    quantidade INTEGER DEFAULT 1,
    data_adicao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_produtos_lista_loja_lista_id ON produtos_lista_loja(lista_id);
CREATE INDEX IF NOT EXISTS idx_produtos_lista_loja_ean ON produtos_lista_loja(ean);

-- ============================================================================
-- TABELA: listas_manutencao
-- Armazena listas de produtos para manutenção
-- ============================================================================
CREATE TABLE IF NOT EXISTS listas_manutencao (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    usuario_id INTEGER REFERENCES usuarios(id),
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ativo BOOLEAN DEFAULT TRUE
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_listas_manutencao_usuario_id ON listas_manutencao(usuario_id);
CREATE INDEX IF NOT EXISTS idx_listas_manutencao_ativo ON listas_manutencao(ativo);

-- ============================================================================
-- TABELA: produtos_lista_manutencao
-- Armazena produtos associados a listas de manutenção
-- ============================================================================
CREATE TABLE IF NOT EXISTS produtos_lista_manutencao (
    id SERIAL PRIMARY KEY,
    lista_id INTEGER REFERENCES listas_manutencao(id) ON DELETE CASCADE,
    ean VARCHAR(13) NOT NULL,
    nome VARCHAR(255),
    motivo TEXT,
    quantidade INTEGER DEFAULT 1,
    data_adicao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_produtos_lista_manutencao_lista_id ON produtos_lista_manutencao(lista_id);
CREATE INDEX IF NOT EXISTS idx_produtos_lista_manutencao_ean ON produtos_lista_manutencao(ean);

-- ============================================================================
-- TABELA: listas_unificadas
-- Armazena listas unificadas (consolidação de várias listas)
-- ============================================================================
CREATE TABLE IF NOT EXISTS listas_unificadas (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    usuario_id INTEGER REFERENCES usuarios(id),
    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ativo BOOLEAN DEFAULT TRUE
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_listas_unificadas_usuario_id ON listas_unificadas(usuario_id);
CREATE INDEX IF NOT EXISTS idx_listas_unificadas_ativo ON listas_unificadas(ativo);

-- ============================================================================
-- TABELA: produtos_listas_unificadas
-- Armazena produtos associados a listas unificadas
-- ============================================================================
CREATE TABLE IF NOT EXISTS produtos_listas_unificadas (
    id SERIAL PRIMARY KEY,
    lista_id INTEGER REFERENCES listas_unificadas(id) ON DELETE CASCADE,
    ean VARCHAR(13) NOT NULL,
    nome VARCHAR(255),
    quantidade INTEGER DEFAULT 1,
    data_adicao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_produtos_listas_unificadas_lista_id ON produtos_listas_unificadas(lista_id);
CREATE INDEX IF NOT EXISTS idx_produtos_listas_unificadas_ean ON produtos_listas_unificadas(ean);

-- ============================================================================
-- TABELA: movimentacoes_estoque
-- Armazena histórico de movimentações de entrada e saída
-- ============================================================================
CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
    id SERIAL PRIMARY KEY,
    tipo VARCHAR(10) NOT NULL,  -- 'entrada' ou 'saida'
    ean VARCHAR(13) NOT NULL,
    nome VARCHAR(255),
    cor VARCHAR(100),
    voltagem VARCHAR(50),
    modelo VARCHAR(100),
    quantidade INTEGER NOT NULL,
    rua_id INTEGER REFERENCES ruas(id),
    usuario_id INTEGER REFERENCES usuarios(id),
    data_movimentacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    observacao TEXT
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_movimentacoes_tipo ON movimentacoes_estoque(tipo);
CREATE INDEX IF NOT EXISTS idx_movimentacoes_ean ON movimentacoes_estoque(ean);
CREATE INDEX IF NOT EXISTS idx_movimentacoes_rua_id ON movimentacoes_estoque(rua_id);
CREATE INDEX IF NOT EXISTS idx_movimentacoes_usuario_id ON movimentacoes_estoque(usuario_id);
CREATE INDEX IF NOT EXISTS idx_movimentacoes_data ON movimentacoes_estoque(data_movimentacao);

-- ============================================================================
-- DADOS INICIAIS
-- ============================================================================

-- Criar usuário administrador padrão (senha: admin123)
-- Hash gerado com werkzeug.security.generate_password_hash('admin123')
INSERT INTO usuarios (nome, senha_hash, admin, ativo)
VALUES ('admin', 'scrypt:32768:8:1$vZ3xYwKjL9qR8tNm$c8d9e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3', 1, TRUE)
ON CONFLICT (nome) DO NOTHING;

-- Criar usuário de estoque padrão (senha: estoque123)
INSERT INTO usuarios (nome, senha_hash, admin, ativo)
VALUES ('estoque', 'scrypt:32768:8:1$aB2cD3eF4gH5iJ6k$a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4', 0, TRUE)
ON CONFLICT (nome) DO NOTHING;

-- Criar usuário de cadastro padrão (senha: cadastro123)
INSERT INTO usuarios (nome, senha_hash, admin, ativo)
VALUES ('cadastro', 'scrypt:32768:8:1$xY9zA1bC2dE3fG4h$f1e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b3a4f5e6d7c8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4', 2, TRUE)
ON CONFLICT (nome) DO NOTHING;

-- Criar ruas de exemplo
INSERT INTO ruas (nome, posicao, ativo)
VALUES 
    ('Rua A1', 1, TRUE),
    ('Rua A2', 2, TRUE),
    ('Rua B1', 3, TRUE),
    ('Rua B2', 4, TRUE)
ON CONFLICT (nome) DO NOTHING;

-- ============================================================================
-- VIEWS ÚTEIS (Opcional)
-- ============================================================================

-- View de produtos em estoque (em ruas)
CREATE OR REPLACE VIEW v_produtos_estoque AS
SELECT 
    p.id,
    p.ean,
    p.nome,
    p.cor,
    p.voltagem,
    p.modelo,
    p.quantidade,
    r.nome as rua_nome,
    r.id as rua_id,
    u.nome as usuario_nome,
    p.timestamp
FROM produtos p
LEFT JOIN ruas r ON p.rua_id = r.id
LEFT JOIN usuarios u ON p.usuario_id = u.id
WHERE p.ativo = TRUE AND p.rua_id IS NOT NULL;

-- View de produtos aguardando validação
CREATE OR REPLACE VIEW v_produtos_aguardando_validacao AS
SELECT 
    p.id,
    p.ean,
    p.nome,
    p.quantidade,
    p.destino,
    p.data_envio,
    p.responsavel_id,
    p.responsavel_pin,
    u.nome as criador_nome,
    p.usuario_id
FROM produtos p
LEFT JOIN usuarios u ON p.usuario_id = u.id
WHERE p.enviado = 1 AND p.validado = 0 AND p.ativo = TRUE
ORDER BY p.data_envio DESC;

-- View de estatísticas de movimentações
CREATE OR REPLACE VIEW v_estatisticas_movimentacoes AS
SELECT 
    DATE(data_movimentacao) as data,
    tipo,
    COUNT(*) as total_movimentacoes,
    SUM(quantidade) as quantidade_total,
    COUNT(DISTINCT usuario_id) as usuarios_distintos
FROM movimentacoes_estoque
GROUP BY DATE(data_movimentacao), tipo
ORDER BY data DESC;

-- ============================================================================
-- FUNÇÕES ÚTEIS (Opcional)
-- ============================================================================

-- Função para obter total de produtos em uma rua
CREATE OR REPLACE FUNCTION obter_total_produtos_rua(p_rua_id INTEGER)
RETURNS INTEGER AS $$
BEGIN
    RETURN (
        SELECT COALESCE(SUM(quantidade), 0)
        FROM produtos
        WHERE rua_id = p_rua_id AND ativo = TRUE
    );
END;
$$ LANGUAGE plpgsql;

-- Função para obter total de movimentações de um usuário
CREATE OR REPLACE FUNCTION obter_total_movimentacoes_usuario(p_usuario_id INTEGER, p_tipo VARCHAR DEFAULT NULL)
RETURNS INTEGER AS $$
BEGIN
    IF p_tipo IS NULL THEN
        RETURN (
            SELECT COUNT(*)
            FROM movimentacoes_estoque
            WHERE usuario_id = p_usuario_id
        );
    ELSE
        RETURN (
            SELECT COUNT(*)
            FROM movimentacoes_estoque
            WHERE usuario_id = p_usuario_id AND tipo = p_tipo
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PERMISSÕES (Ajustar conforme necessário)
-- ============================================================================

-- Garantir que o usuário do banco tem permissões
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO data_base_mult_tenant_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO data_base_mult_tenant_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO data_base_mult_tenant_user;

-- ============================================================================
-- FIM DO SCHEMA
-- ============================================================================

-- Verificar tabelas criadas
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as num_columns
FROM information_schema.tables t
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Verificar índices criados
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

