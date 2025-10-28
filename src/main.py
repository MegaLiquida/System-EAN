import sys
import os
import psycopg2
import psycopg2.extras
from datetime import datetime
import io
import requests
import hashlib
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session, flash
import pandas as pd
import json
from werkzeug.security import generate_password_hash, check_password_hash
from src.utils import formatar_data_brasileira

# ============================================================================
# DEFINIÇÕES DE TIPOS DE USUÁRIO - APENAS 3 PAINÉIS CORRETOS
# ============================================================================

TIPOS_USUARIO = {
    "sistema_estoque": {
        "nome": "Sistema de Estoque",
        "descricao": "Acesso ao painel de estoque",
        "detalhes": "Pode consultar produtos por código EAN, adicionar produtos em ruas e gerenciar estoque local.",
        "painel": "estoque.html",
        "permissoes": {
            "estoque_acesso": True,
            "estoque_consulta": True,
            "estoque_entrada": True,
            "estoque_saida": True,
            "estoque_ruas": True
        }
    },
    "sistema_cadastro": {
        "nome": "Sistema de Cadastro de Produtos", 
        "descricao": "Acesso ao painel de cadastro de produtos",
        "detalhes": "Pode adicionar novos produtos, buscar no Mercado Livre, criar listas e enviar para validação.",
        "painel": "index.html",
        "permissoes": {
            "cadastro_acesso": True,
            "cadastro_consulta": True,
            "cadastro_produtos": True,
            "cadastro_listas": True
        }
    },
    "painel_administrativo": {
        "nome": "Painel Administrativo",
        "descricao": "Acesso completo ao sistema",
        "detalhes": "Acesso completo: gerenciar usuários, validar listas, estoque local, desenvolvedores e todas as funcionalidades.",
        "painel": "admin.html",
        "permissoes": {
            "admin_acesso": True,
            "dev_acesso": True,
            "dev_usuarios": True,
            "estoque_acesso": True,
            "estoque_consulta": True,
            "estoque_entrada": True,
            "estoque_saida": True,
            "estoque_ruas": True,
            "cadastro_acesso": True,
            "cadastro_consulta": True,
            "cadastro_produtos": True,
            "cadastro_listas": True
        }
    }
}

def obter_tipo_por_admin(admin_flag):
    """Mapear flag admin para tipo de usuário"""
    if admin_flag:
        return "painel_administrativo"
    else:
        return "sistema_estoque"  # Padrão para usuários não-admin

def obter_admin_por_tipo(tipo):
    """Mapear tipo de usuário para flag admin (retorna INTEGER para compatibilidade com banco)"""
    if tipo == "painel_administrativo":
        return 1  # Admin
    elif tipo == "sistema_cadastro":
        return 2  # Sistema de Cadastro
    else:
        return 0  # Sistema de Estoque (padrão)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "ean_app_secret_key_default")

@app.template_filter('data_brasileira')
def data_brasileira_filter(data):
    return formatar_data_brasileira(data)

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print("Erro: Variável de ambiente DATABASE_URL não definida.")
    sys.exit(1)

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_database():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    nome TEXT NOT NULL UNIQUE,
                    senha_hash TEXT NOT NULL,
                    admin INTEGER DEFAULT 0
                );
                """)
                
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS responsaveis (
                    id SERIAL PRIMARY KEY,
                    nome TEXT NOT NULL UNIQUE,
                    pin TEXT NOT NULL
                );
                """)
                
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS ruas (
                    id SERIAL PRIMARY KEY,
                    nome TEXT NOT NULL UNIQUE,
                    descricao TEXT,
                    qr_code_data TEXT
                );
                """)
                
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS listas_unificadas (
                    id SERIAL PRIMARY KEY,
                    nome_lista TEXT NOT NULL,
                    validador_id INTEGER NOT NULL,
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_produtos INTEGER DEFAULT 0,
                    total_quantidade INTEGER DEFAULT 0,
                    FOREIGN KEY (validador_id) REFERENCES usuarios (id)
                );
                """)
                
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS produtos_unificados (
                    id SERIAL PRIMARY KEY,
                    lista_unificada_id INTEGER NOT NULL,
                    ean TEXT NOT NULL,
                    nome TEXT NOT NULL,
                    cor TEXT,
                    voltagem TEXT,
                    modelo TEXT,
                    quantidade_total INTEGER NOT NULL,
                    listas_origem TEXT, -- JSON com informações das listas originais
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (lista_unificada_id) REFERENCES listas_unificadas (id) ON DELETE CASCADE
                );
                """)
                
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS produtos (
                    id SERIAL PRIMARY KEY,
                    ean TEXT NOT NULL,
                    nome TEXT NOT NULL,
                    cor TEXT,
                    voltagem TEXT,
                    modelo TEXT,
                    quantidade INTEGER NOT NULL,
                    usuario_id INTEGER NOT NULL,
                    timestamp TIMESTAMP,
                    enviado INTEGER DEFAULT 0,
                    data_envio TIMESTAMP,
                    validado INTEGER DEFAULT 0,
                    validador_id INTEGER,
                    data_validacao TIMESTAMP,
                    responsavel_id INTEGER,
                    responsavel_pin TEXT,
                    rua_id INTEGER,
                    ativo BOOLEAN DEFAULT TRUE,
                    destino VARCHAR(20) DEFAULT 'mercado_livre' CHECK (destino IN ('mercado_livre', 'loja', 'manutencao')),
                    FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
                    FOREIGN KEY (validador_id) REFERENCES usuarios (id),
                    FOREIGN KEY (responsavel_id) REFERENCES responsaveis (id),
                    FOREIGN KEY (rua_id) REFERENCES ruas (id)
                );
                """)
                
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS movimentacoes (
                    id SERIAL PRIMARY KEY,
                    tipo_movimentacao VARCHAR(20) NOT NULL CHECK (tipo_movimentacao IN ('ENTRADA', 'SAIDA', 'TRANSFERENCIA')),
                    produto_id INTEGER,
                    ean TEXT NOT NULL,
                    nome_produto TEXT NOT NULL,
                    cor TEXT,
                    voltagem TEXT,
                    modelo TEXT,
                    quantidade INTEGER NOT NULL,
                    rua_origem_id INTEGER,
                    rua_destino_id INTEGER,
                    usuario_id INTEGER NOT NULL,
                    data_movimentacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    observacoes TEXT,
                    FOREIGN KEY (produto_id) REFERENCES produtos (id),
                    FOREIGN KEY (rua_origem_id) REFERENCES ruas (id),
                    FOREIGN KEY (rua_destino_id) REFERENCES ruas (id),
                    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
                );
                """)
                
                # Criar índices para otimizar consultas
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_movimentacoes_data 
                ON movimentacoes (data_movimentacao);
                """)
                
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_movimentacoes_usuario 
                ON movimentacoes (usuario_id);
                """)
                
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_movimentacoes_tipo 
                ON movimentacoes (tipo_movimentacao);
                """)
                
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_movimentacoes_ean 
                ON movimentacoes (ean);
                """)
                
                # Adicionar campo destino à tabela produtos se não existir
                try:
                    cursor.execute("""
                        ALTER TABLE produtos 
                        ADD COLUMN IF NOT EXISTS destino VARCHAR(20) DEFAULT 'mercado_livre'
                    """)
                    cursor.execute("""
                        ALTER TABLE produtos 
                        DROP CONSTRAINT IF EXISTS check_destino
                    """)
                    cursor.execute("""
                        ALTER TABLE produtos 
                        ADD CONSTRAINT check_destino 
                        CHECK (destino IN ('mercado_livre', 'loja', 'manutencao'))
                    """)
                except psycopg2.Error:
                    pass  # Campo já existe
                
                # Criar tabelas para destino Loja
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS listas_loja (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER NOT NULL,
                    data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
                );
                """)
                
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS produtos_loja (
                    id SERIAL PRIMARY KEY,
                    lista_loja_id INTEGER NOT NULL,
                    ean TEXT NOT NULL,
                    nome TEXT NOT NULL,
                    cor TEXT,
                    voltagem TEXT,
                    modelo TEXT,
                    quantidade INTEGER NOT NULL,
                    FOREIGN KEY (lista_loja_id) REFERENCES listas_loja (id) ON DELETE CASCADE
                );
                """)
                
                # Criar tabelas para destino Manutenção
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS listas_manutencao (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER NOT NULL,
                    data_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
                );
                """)
                
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS produtos_manutencao (
                    id SERIAL PRIMARY KEY,
                    lista_manutencao_id INTEGER NOT NULL,
                    ean TEXT NOT NULL,
                    nome TEXT NOT NULL,
                    cor TEXT,
                    voltagem TEXT,
                    modelo TEXT,
                    quantidade INTEGER NOT NULL,
                    FOREIGN KEY (lista_manutencao_id) REFERENCES listas_manutencao (id) ON DELETE CASCADE
                );
                """)
                
                # Criar índices para otimização
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_produtos_destino 
                ON produtos (destino);
                """)
                
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_produtos_loja_ean 
                ON produtos_loja (ean);
                """)
                
                cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_produtos_manutencao_ean 
                ON produtos_manutencao (ean);
                """)
                
                cursor.execute("SELECT COUNT(*) FROM usuarios")
                user_count = cursor.fetchone()[0]
                
                if user_count == 0:
                    cursor.execute("SELECT * FROM usuarios WHERE admin = 1")
                    admin = cursor.fetchone()
                    if not admin:
                        admin_hash = generate_password_hash("admin")
                        cursor.execute("INSERT INTO usuarios (nome, senha_hash, admin) VALUES (%s, %s, %s)", 
                                      ("admin", admin_hash, 1))
                
                inicializar_responsaveis()
                
                # Migração: Adicionar campo destino na tabela produtos se não existir
                try:
                    cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'produtos' AND column_name = 'destino'
                    """)
                    if not cursor.fetchone():
                        cursor.execute("""
                        ALTER TABLE produtos 
                        ADD COLUMN destino VARCHAR(20) DEFAULT 'mercado_livre' 
                        CHECK (destino IN ('mercado_livre', 'loja', 'manutencao'))
                        """)
                        print("Campo 'destino' adicionado à tabela produtos.")
                    else:
                        print("Campo 'destino' já existe na tabela produtos.")
                except psycopg2.Error as e:
                    print(f"Erro na migração do campo destino: {e}")
                
                # Migração: Adicionar campo motivo_manutencao na tabela produtos
                try:
                    cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'produtos' AND column_name = 'motivo_manutencao'
                    """)
                    if not cursor.fetchone():
                        cursor.execute("""
                        ALTER TABLE produtos 
                        ADD COLUMN motivo_manutencao TEXT
                        """)
                        print("Campo 'motivo_manutencao' adicionado à tabela produtos.")
                    else:
                        print("Campo 'motivo_manutencao' já existe na tabela produtos.")
                except psycopg2.Error as e:
                    print(f"Erro na migração do campo motivo_manutencao: {e}")
                
                # Migração: Adicionar campo status_manutencao na tabela produtos
                try:
                    cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'produtos' AND column_name = 'status_manutencao'
                    """)
                    if not cursor.fetchone():
                        cursor.execute("""
                        ALTER TABLE produtos 
                        ADD COLUMN status_manutencao VARCHAR(50)
                        """)
                        print("Campo 'status_manutencao' adicionado à tabela produtos.")
                    else:
                        print("Campo 'status_manutencao' já existe na tabela produtos.")
                except psycopg2.Error as e:
                    print(f"Erro na migração do campo status_manutencao: {e}")
                
        print("Banco de dados inicializado com sucesso.")
    except psycopg2.Error as e:
        print(f"Erro ao inicializar o banco de dados: {e}")

def inicializar_responsaveis():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM responsaveis")
                count = cursor.fetchone()[0]
                
                if count == 0:
                    responsaveis = [
                        ("Liliane", "5584"),
                        ("Rogerio", "9841"),
                        ("Celso", "2122"),
                        ("Marcos", "6231")
                    ]
                    
                    for nome, pin in responsaveis:
                        cursor.execute("INSERT INTO responsaveis (nome, pin) VALUES (%s, %s)", (nome, pin))
                    
                    print(f"Responsáveis inicializados: {len(responsaveis)}")
    except psycopg2.Error as e:
        print(f"Erro ao inicializar responsáveis: {e}")
        conn.rollback()

def obter_responsaveis():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, nome FROM responsaveis ORDER BY nome")
                responsaveis = [dict(row) for row in cursor.fetchall()]
        return responsaveis
    except psycopg2.Error as e:
        print(f"Erro ao obter responsáveis: {e}")
        return []

def verificar_pin_responsavel(responsavel_id, pin):
    """
    Versão melhorada da função de verificação de PIN com logs detalhados
    e tratamento de casos especiais.
    """
    from datetime import datetime
    
    # Log detalhado para debug
    log_entry = f"[{datetime.now()}] Verificando PIN - ID: {responsavel_id}, PIN: '{pin}'"
    print(log_entry)
    
    try:
        # Validações básicas
        if not responsavel_id:
            print(f"❌ ERRO: responsavel_id é None ou vazio: {responsavel_id}")
            return False
        
        if not pin:
            print(f"❌ ERRO: PIN é None ou vazio: {pin}")
            return False
        
        # Converter responsavel_id para int se necessário
        if isinstance(responsavel_id, str):
            try:
                responsavel_id = int(responsavel_id)
                print(f"✅ Convertido responsavel_id para int: {responsavel_id}")
            except ValueError:
                print(f"❌ ERRO: Não foi possível converter responsavel_id '{responsavel_id}' para int")
                return False
        
        # Limpar PIN de espaços em branco
        pin_original = pin
        pin = str(pin).strip()
        
        if pin != pin_original:
            print(f"⚠️  PIN tinha espaços: '{pin_original}' -> '{pin}'")
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Buscar responsável
                cursor.execute("SELECT id, nome, pin FROM responsaveis WHERE id = %s", (responsavel_id,))
                resultado = cursor.fetchone()
                
                if not resultado:
                    print(f"❌ ERRO: Responsável com ID {responsavel_id} não encontrado")
                    return False
                
                id_banco, nome_banco, pin_banco = resultado
                
                # Log detalhado da comparação
                print(f"📋 Responsável encontrado: {nome_banco} (ID: {id_banco})")
                print(f"🔍 Comparação de PINs:")
                print(f"   PIN fornecido: '{pin}' (tipo: {type(pin)}, len: {len(pin)})")
                print(f"   PIN no banco:  '{pin_banco}' (tipo: {type(pin_banco)}, len: {len(pin_banco)})")
                
                # Limpar PIN do banco também
                pin_banco_limpo = str(pin_banco).strip()
                
                # Múltiplas comparações para debug
                comparacao_direta = (pin_banco == pin)
                comparacao_limpa = (pin_banco_limpo == pin)
                
                print(f"   Comparação direta: {comparacao_direta}")
                print(f"   Comparação limpa:  {comparacao_limpa}")
                
                # Resultado final
                if comparacao_direta or comparacao_limpa:
                    print(f"✅ PIN VÁLIDO para {nome_banco}")
                    return True
                else:
                    print(f"❌ PIN INVÁLIDO para {nome_banco}")
                    return False
                
    except psycopg2.Error as e:
        print(f"❌ ERRO de banco de dados: {e}")
        return False
    except Exception as e:
        print(f"❌ ERRO inesperado: {e}")
        return False

def obter_nome_responsavel(responsavel_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT nome FROM responsaveis WHERE id = %s", (responsavel_id,))
                resultado = cursor.fetchone()
                
                if resultado:
                    return resultado[0]
                return None
    except psycopg2.Error as e:
        print(f"Erro ao obter nome do responsável: {e}")
        return None

def registrar_usuario(nome, senha):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                senha_hash = generate_password_hash(senha)
                cursor.execute("INSERT INTO usuarios (nome, senha_hash) VALUES (%s, %s)", (nome, senha_hash))
        return True
    except psycopg2.errors.UniqueViolation:
        return False
    except psycopg2.Error as e:
        print(f"Erro ao registrar usuário: {e}")
        return False

def verificar_usuario(nome, senha):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, senha_hash, admin FROM usuarios WHERE nome = %s", (nome,))
                usuario = cursor.fetchone()
        
        if usuario and check_password_hash(usuario["senha_hash"], senha):
            return {"id": usuario["id"], "admin": usuario["admin"]}
        return None
    except psycopg2.Error as e:
        print(f"Erro ao verificar usuário: {e}")
        return None

def obter_nome_usuario(usuario_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT nome FROM usuarios WHERE id = %s", (usuario_id,))
                usuario = cursor.fetchone()
        return usuario[0] if usuario else None
    except psycopg2.Error as e:
        print(f"Erro ao obter nome do usuário: {e}")
        return None

def carregar_produtos_usuario(usuario_id, apenas_nao_enviados=False):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                if apenas_nao_enviados:
                    # CORREÇÃO: Filtrar apenas produtos do estoque geral (sem rua_id)
                    cursor.execute("SELECT * FROM produtos WHERE usuario_id = %s AND enviado = 0 AND rua_id IS NULL AND ativo = TRUE ORDER BY timestamp DESC", (usuario_id,))
                else:
                    # CORREÇÃO: Filtrar apenas produtos do estoque geral (sem rua_id)
                    cursor.execute("SELECT * FROM produtos WHERE usuario_id = %s AND rua_id IS NULL AND ativo = TRUE ORDER BY timestamp DESC", (usuario_id,))
                produtos = [dict(row) for row in cursor.fetchall()]
        return produtos
    except psycopg2.Error as e:
        print(f"Erro ao carregar produtos do usuário: {e}")
        return []

def carregar_todas_listas_enviadas():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                SELECT p.*, 
                       u.nome as nome_usuario,
                       v.nome as nome_validador,
                       r.nome as nome_responsavel
                FROM produtos p 
                JOIN usuarios u ON p.usuario_id = u.id 
                LEFT JOIN usuarios v ON p.validador_id = v.id
                LEFT JOIN responsaveis r ON p.responsavel_id = r.id
                WHERE p.enviado = 1 AND p.destino = 'mercado_livre'
                ORDER BY p.data_envio DESC
                """)
                produtos = [dict(row) for row in cursor.fetchall()]
                
                print(f"Produtos enviados encontrados: {len(produtos)}")
                if len(produtos) > 0:
                    print(f"Exemplo do primeiro produto: {produtos[0]}")
                    
        return produtos
    except psycopg2.Error as e:
        print(f"Erro ao carregar todas as listas enviadas: {e}")
        return []

def carregar_listas_enviadas_paginadas(pagina=1, por_pagina=10, termo_pesquisa="", data_busca=None, data_inicio=None, data_fim=None, criador_filtro=""):
    try:
        from datetime import datetime
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                base_query = """
                SELECT p.*, 
                       u.nome as nome_usuario,
                       v.nome as nome_validador,
                       r.nome as nome_responsavel
                FROM produtos p 
                JOIN usuarios u ON p.usuario_id = u.id 
                LEFT JOIN usuarios v ON p.validador_id = v.id
                LEFT JOIN responsaveis r ON p.responsavel_id = r.id
                WHERE p.enviado = 1 AND p.destino = 'mercado_livre'
                """
                
                params = []
                
                if termo_pesquisa:
                    termo_like = f"%{termo_pesquisa}%"
                    base_query += " AND (p.ean ILIKE %s OR p.nome ILIKE %s OR p.cor ILIKE %s OR p.modelo ILIKE %s)"
                    params.extend([termo_like, termo_like, termo_like, termo_like])
                
                if data_busca:
                    try:
                        data_obj = datetime.strptime(data_busca, "%d/%m/%Y")
                        data_sql = data_obj.strftime("%Y-%m-%d")
                        base_query += " AND DATE(p.data_envio) = %s"
                        params.append(data_sql)
                    except ValueError:
                        print(f"Formato de data inválido para data_busca: {data_busca}")
                
                if data_inicio and data_fim:
                    try:
                        data_inicio_obj = datetime.strptime(data_inicio, "%d/%m/%Y")
                        data_fim_obj = datetime.strptime(data_fim, "%d/%m/%Y")
                        
                        if data_inicio_obj > data_fim_obj:
                            print("Data de início deve ser anterior ou igual à data de fim")
                            return {
                                "listas_agrupadas": [],
                                "total_listas": 0,
                                "pagina_atual": 1,
                                "total_paginas": 0,
                                "por_pagina": por_pagina,
                                "tem_anterior": False,
                                "tem_proximo": False
                            }
                        
                        data_inicio_sql = data_inicio_obj.strftime("%Y-%m-%d")
                        data_fim_sql = data_fim_obj.strftime("%Y-%m-%d")
                        base_query += " AND DATE(p.data_envio::timestamp - INTERVAL '3 hours') >= %s::date AND DATE(p.data_envio::timestamp - INTERVAL '3 hours') <= %s::date"
                        params.extend([data_inicio_sql, data_fim_sql])
                    except ValueError:
                        print(f"Formato de data inválido para período: {data_inicio} - {data_fim}")
                
                if criador_filtro:
                    criador_like = f"%{criador_filtro}%"
                    base_query += " AND u.nome ILIKE %s"
                    params.append(criador_like)
                
                base_query += " ORDER BY p.data_envio DESC"
                
                cursor.execute(base_query, params)
                produtos = [dict(row) for row in cursor.fetchall()]
                
                listas_agrupadas = {}
                for produto in produtos:
                    data_envio_key = produto.get("data_envio")
                    if not data_envio_key:
                        data_envio_key = "Sem data de envio"
                        
                    chave = (data_envio_key, produto["nome_usuario"])
                    if chave not in listas_agrupadas:
                        listas_agrupadas[chave] = {
                            "produtos": [],
                            "validado": produto.get("validado", 0),
                            "nome_validador": produto.get("nome_validador"),
                            "data_validacao": produto.get("data_validacao"),
                            "nome_responsavel": produto.get("nome_responsavel"),
                            "data_envio": data_envio_key,
                            "nome_usuario": produto["nome_usuario"]
                        }
                    listas_agrupadas[chave]["produtos"].append(produto)
                
                listas_ordenadas = []
                for chave, lista_info in listas_agrupadas.items():
                    listas_ordenadas.append(lista_info)
                
                listas_ordenadas.sort(key=lambda x: x["data_envio"] if x["data_envio"] != "Sem data de envio" else "", reverse=True)
                
                total_listas = len(listas_ordenadas)
                total_paginas = (total_listas + por_pagina - 1) // por_pagina
                
                if pagina < 1:
                    pagina = 1
                elif total_paginas > 0 and pagina > total_paginas:
                    pagina = total_paginas
                
                inicio = (pagina - 1) * por_pagina
                fim = inicio + por_pagina
                
                listas_paginadas = listas_ordenadas[inicio:fim]
                
                return {
                    "listas_agrupadas": listas_paginadas,
                    "total_listas": total_listas,
                    "pagina_atual": pagina,
                    "total_paginas": total_paginas,
                    "por_pagina": por_pagina,
                    "tem_anterior": pagina > 1,
                    "tem_proximo": pagina < total_paginas
                }
                
    except psycopg2.Error as e:
        print(f"Erro ao carregar listas enviadas paginadas: {e}")
        return {
            "listas_agrupadas": [],
            "total_listas": 0,
            "pagina_atual": 1,
            "total_paginas": 0,
            "por_pagina": por_pagina,
            "tem_anterior": False,
            "tem_proximo": False
        }
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                termo_like = f"%{termo_pesquisa}%"
                cursor.execute("""
                SELECT p.*, 
                       u.nome as nome_usuario,
                       v.nome as nome_validador,
                       r.nome as nome_responsavel
                FROM produtos p 
                JOIN usuarios u ON p.usuario_id = u.id 
                LEFT JOIN usuarios v ON p.validador_id = v.id
                LEFT JOIN responsaveis r ON p.responsavel_id = r.id
                WHERE p.enviado = 1 
                  AND (p.ean ILIKE %s OR p.nome ILIKE %s OR p.cor ILIKE %s OR p.modelo ILIKE %s)
                ORDER BY p.data_envio DESC
                """, (termo_like, termo_like, termo_like, termo_like))
                produtos = [dict(row) for row in cursor.fetchall()]
        return produtos
    except psycopg2.Error as e:
        print(f"Erro ao pesquisar produtos: {e}")
        return []

def buscar_produto_local(ean, usuario_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT * FROM produtos WHERE ean = %s AND usuario_id = %s AND enviado = 0 AND ativo = TRUE", (ean, usuario_id))
                produto = cursor.fetchone()
        return dict(produto) if produto else None
    except psycopg2.Error as e:
        print(f"Erro ao buscar produto local: {e}")
        return None

def buscar_produto_nas_listas_enviadas(ean):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                SELECT ean, nome, cor, voltagem, modelo, 
                       COUNT(*) as total_ocorrencias,
                       SUM(quantidade) as quantidade_total,
                       MAX(data_envio) as ultima_data_envio
                FROM produtos 
                WHERE ean = %s AND enviado = 1 
                GROUP BY ean, nome, cor, voltagem, modelo
                ORDER BY ultima_data_envio DESC
                LIMIT 1
                """, (ean,))
                
                resultado = cursor.fetchone()
                
                if resultado:
                    return {
                        "ean": resultado["ean"],
                        "nome": resultado["nome"],
                        "cor": resultado["cor"] or "",
                        "voltagem": resultado["voltagem"] or "",
                        "modelo": resultado["modelo"] or "",
                        "quantidade_total_historico": resultado["quantidade_total"],
                        "ocorrencias": resultado["total_ocorrencias"],
                        "ultima_data_envio": resultado["ultima_data_envio"]
                    }
                
                return None
                
    except psycopg2.Error as e:
        print(f"Erro ao buscar produto nas listas enviadas: {e}")
        return None

def buscar_produto_priorizado(ean):
    try:
        produto_lista = buscar_produto_nas_listas_enviadas(ean)
        if produto_lista:
            return {
                "success": True,
                "data": produto_lista,
                "source": "listas_enviadas",
                "message": f"Produto encontrado nas listas enviadas ({produto_lista['ocorrencias']} ocorrências)"
            }
        
        resultado_ml = buscar_produto_online(ean)
        
        if resultado_ml and resultado_ml.get("success"):
            resultado_ml["source"] = "mercado_livre"
            return resultado_ml
        
        return {
            "success": False,
            "message": "Produto não encontrado em nenhuma fonte",
            "source": "none"
        }
        
    except Exception as e:
        print(f"Erro na busca priorizada: {e}")
        return {
            "success": False,
            "message": f"Erro na busca: {str(e)}",
            "source": "error"
        }

def buscar_produtos_por_nome(nome):
    try:
        if not nome or len(nome.strip()) < 3:
            return []
            
        nome = nome.strip()
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                query = """
                SELECT DISTINCT 
                    ean, nome, cor, voltagem, modelo,
                    COUNT(*) as total_cadastros,
                    SUM(quantidade) as quantidade_total,
                    MAX(timestamp) as ultimo_cadastro
                FROM produtos 
                WHERE nome ILIKE %s 
                GROUP BY ean, nome, cor, voltagem, modelo
                ORDER BY ultimo_cadastro DESC, quantidade_total DESC
                LIMIT 20
                """
                
                nome_busca = f"%{nome}%"
                cursor.execute(query, (nome_busca,))
                
                produtos = []
                for row in cursor.fetchall():
                    produtos.append({
                        'ean': row['ean'],
                        'nome': row['nome'],
                        'cor': row['cor'] or '',
                        'voltagem': row['voltagem'] or '',
                        'modelo': row['modelo'] or '',
                        'total_cadastros': row['total_cadastros'],
                        'quantidade_total': row['quantidade_total'],
                        'ultimo_cadastro': row['ultimo_cadastro'].isoformat() if row['ultimo_cadastro'] else None
                    })
                
                return produtos
                
    except psycopg2.Error as e:
        print(f"Erro na busca por nome '{nome}': {e}")
        return []
    except Exception as e:
        print(f"Erro inesperado na busca por nome '{nome}': {e}")
        return []

def salvar_produto(produto, usuario_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM produtos WHERE ean = %s AND usuario_id = %s AND enviado = 0 AND ativo = TRUE AND destino = %s", 
                              (produto["ean"], usuario_id, produto.get("destino", "mercado_livre")))
                existing = cursor.fetchone()
                
                timestamp_obj = produto.get("timestamp")
                if isinstance(timestamp_obj, str):
                    try:
                        timestamp_obj = datetime.strptime(timestamp_obj, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        timestamp_obj = datetime.now()
                elif not isinstance(timestamp_obj, datetime):
                     timestamp_obj = datetime.now()

                if existing:
                    # Para produtos existentes, atualizar também o motivo_manutencao se fornecido
                    if produto.get("destino") == "manutencao" and produto.get("motivo_manutencao"):
                        cursor.execute("""
                        UPDATE produtos 
                        SET quantidade = quantidade + %s, 
                            timestamp = %s,
                            motivo_manutencao = %s
                        WHERE ean = %s AND usuario_id = %s AND enviado = 0 AND destino = %s
                        """, (produto["quantidade"], timestamp_obj, produto.get("motivo_manutencao"), produto["ean"], usuario_id, produto.get("destino", "mercado_livre")))
                    else:
                        cursor.execute("""
                        UPDATE produtos 
                        SET quantidade = quantidade + %s, 
                            timestamp = %s 
                        WHERE ean = %s AND usuario_id = %s AND enviado = 0 AND destino = %s
                        """, (produto["quantidade"], timestamp_obj, produto["ean"], usuario_id, produto.get("destino", "mercado_livre")))
                else:
                    cursor.execute("""
                    INSERT INTO produtos (ean, nome, cor, voltagem, modelo, quantidade, usuario_id, timestamp, enviado, destino, motivo_manutencao)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
                    """, (
                        produto["ean"], 
                        produto["nome"], 
                        produto.get("cor"),
                        produto.get("voltagem"), 
                        produto.get("modelo"), 
                        produto["quantidade"], 
                        usuario_id,
                        timestamp_obj,
                        produto.get("destino"),
                        produto.get("motivo_manutencao") if produto.get("destino") == "manutencao" else None
                    ))
        return True
    except psycopg2.Error as e:
        print(f"Erro ao salvar produto: {e}")
        conn.rollback()
        return False
    except Exception as e:
        print(f"Erro inesperado ao salvar produto: {e}")
        return False

def enviar_lista_produtos(usuario_id, responsavel_id, pin):
    try:
        if not verificar_pin_responsavel(responsavel_id, pin):
            print(f"PIN inválido para o responsável ID {responsavel_id}")
            return None
            
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                data_envio = datetime.now()
                
                # 1. ENVIO NORMAL PARA PAINEL ADMINISTRADOR (como sempre foi)
                cursor.execute("""
                UPDATE produtos 
                SET enviado = 1, 
                    data_envio = %s,
                    responsavel_id = %s,
                    responsavel_pin = %s
                WHERE usuario_id = %s AND enviado = 0 AND rua_id IS NULL
                """, (data_envio, responsavel_id, pin, usuario_id))
                
                affected_rows = cursor.rowcount
                print(f"Produtos marcados como enviados para painel admin: {affected_rows}")
                
                # 2. DUPLICAÇÃO AUTOMÁTICA PARA STAND-BY
                if affected_rows > 0:
                    # Converter data_envio para string para comparação (coluna é TEXT no banco)
                    data_envio_str = data_envio.strftime("%Y-%m-%d %H:%M:%S.%f")
                    
                    # Buscar produtos que foram enviados para duplicar no stand-by
                    cursor.execute("""
                        SELECT ean, nome, cor, voltagem, modelo, quantidade
                        FROM produtos 
                        WHERE usuario_id = %s AND data_envio = %s AND rua_id IS NULL
                    """, (usuario_id, data_envio_str))
                    
                    produtos_enviados = cursor.fetchall()
                    
                    if produtos_enviados:
                        # Criar entrada na tabela listas_standby
                        cursor.execute("""
                            INSERT INTO listas_standby (usuario_id, data_envio)
                            VALUES (%s, %s)
                            RETURNING id
                        """, (usuario_id, data_envio))
                        
                        lista_standby_id = cursor.fetchone()[0]
                        
                        # Copiar produtos para produtos_standby
                        for produto in produtos_enviados:
                            cursor.execute("""
                                INSERT INTO produtos_standby (lista_standby_id, ean, nome, cor, voltagem, modelo, quantidade)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (
                                lista_standby_id,
                                produto[0],  # ean
                                produto[1],  # nome
                                produto[2],  # cor
                                produto[3],  # voltagem
                                produto[4],  # modelo
                                produto[5]   # quantidade
                            ))
                        
                        print(f"Lista duplicada para stand-by com {len(produtos_enviados)} produtos")
                
                conn.commit()
                
        return data_envio
    except psycopg2.Error as e:
        print(f"Erro ao enviar lista de produtos: {e}")
        conn.rollback()
        return None

def validar_lista(data_envio, nome_usuario, validador_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM usuarios WHERE nome = %s", (nome_usuario,))
                usuario = cursor.fetchone()
                
                if not usuario:
                    print(f"Usuário não encontrado: {nome_usuario}")
                    return False
                
                usuario_id = usuario[0]
                data_validacao = datetime.now()
                
                if isinstance(data_envio, datetime):
                    data_envio_str = data_envio.strftime("%Y-%m-%d %H:%M")
                else:
                    data_envio_str = data_envio
                
                print(f"Validando lista com data_envio aproximada: {data_envio_str}")
                
                cursor.execute("""
                UPDATE produtos 
                SET validado = 1, 
                    validador_id = %s,
                    data_validacao = %s
                WHERE usuario_id = %s AND data_envio::text LIKE %s AND destino = 'mercado_livre'
                """, (validador_id, data_validacao, usuario_id, f"{data_envio_str}%"))
                
                affected_rows = cursor.rowcount
                print(f"Produtos marcados como validados: {affected_rows}")
                
                if affected_rows == 0:
                    if len(data_envio_str) >= 10:
                        data_apenas = data_envio_str[:10]
                        print(f"Tentando validação apenas com a data: {data_apenas}")
                        
                        cursor.execute("""
                        UPDATE produtos 
                        SET validado = 1, 
                            validador_id = %s,
                            data_validacao = %s
                        WHERE usuario_id = %s AND data_envio::text LIKE %s AND destino = 'mercado_livre'
                        """, (validador_id, data_validacao, usuario_id, f"{data_apenas}%"))
                        
                        affected_rows = cursor.rowcount
                        print(f"Produtos marcados como validados (segunda tentativa): {affected_rows}")
                
        return affected_rows > 0
    except psycopg2.Error as e:
        print(f"Erro ao validar lista: {e}")
        conn.rollback()
        return False
    except Exception as e:
        print(f"Erro inesperado ao validar lista: {e}")
        print(f"Tipo de data_envio: {type(data_envio)}, Valor: {data_envio}")
        conn.rollback()
        return False

def criar_lista_unificada(listas_validadas, validador_id):
    """
    Cria uma lista unificada a partir de múltiplas listas validadas.
    Produtos com mesmo EAN são agrupados e suas quantidades somadas.
    """
    try:
        # Obter nome do validador
        nome_validador = obter_nome_usuario(validador_id)
        if not nome_validador:
            print(f"Validador não encontrado: {validador_id}")
            return None
        
        # Criar nome único para a lista
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_lista = f"Lista_Unificada_{nome_validador}_{timestamp}"
        
        # Coletar todos os produtos das listas validadas
        produtos_unificados = {}
        listas_origem_info = []
        
        for lista in listas_validadas:
            data_envio = lista.get("data_envio")
            nome_usuario = lista.get("nome_usuario")
            
            if not data_envio or not nome_usuario:
                print(f"Lista com dados incompletos ignorada: data_envio={data_envio}, nome_usuario={nome_usuario}")
                continue
            
            # Buscar produtos da lista
            produtos_lista = buscar_produtos_lista_validada(data_envio, nome_usuario)
            
            if produtos_lista:
                print(f"Processando lista de {nome_usuario}: {len(produtos_lista)} produtos encontrados")
                listas_origem_info.append({
                    "usuario": nome_usuario,
                    "data_envio": data_envio,
                    "total_produtos": len(produtos_lista)
                })
                
                # Unificar produtos
                for produto in produtos_lista:
                    ean = produto["ean"]
                    
                    # Validar EAN
                    if not ean or ean.strip() == "":
                        print(f"Produto com EAN inválido ignorado: {produto}")
                        continue
                    
                    # Validar quantidade
                    quantidade = produto.get("quantidade", 0)
                    if quantidade <= 0:
                        print(f"Produto com quantidade inválida ignorado: {produto}")
                        continue
                    
                    if ean in produtos_unificados:
                        # Produto já existe, somar quantidade
                        produtos_unificados[ean]["quantidade_total"] += quantidade
                        produtos_unificados[ean]["listas_origem"].append({
                            "usuario": nome_usuario,
                            "data_envio": data_envio,
                            "quantidade": quantidade
                        })
                        print(f"Produto {ean} unificado: nova quantidade total = {produtos_unificados[ean]['quantidade_total']}")
                    else:
                        # Novo produto
                        produtos_unificados[ean] = {
                            "ean": ean,
                            "nome": produto["nome"],
                            "cor": produto.get("cor", ""),
                            "voltagem": produto.get("voltagem", ""),
                            "modelo": produto.get("modelo", ""),
                            "quantidade_total": quantidade,
                            "listas_origem": [{
                                "usuario": nome_usuario,
                                "data_envio": data_envio,
                                "quantidade": quantidade
                            }]
                        }
                        print(f"Novo produto adicionado: {ean} - {produto['nome']} (quantidade: {quantidade})")
            else:
                print(f"Nenhum produto encontrado para a lista de {nome_usuario} em {data_envio}")
        
        if not produtos_unificados:
            print("Nenhum produto válido encontrado nas listas validadas")
            return None
        
        print(f"Total de produtos únicos após unificação: {len(produtos_unificados)}")
        print(f"Quantidade total de itens: {sum(p['quantidade_total'] for p in produtos_unificados.values())}")
        
        # Salvar no banco de dados
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Criar registro da lista unificada
                cursor.execute("""
                INSERT INTO listas_unificadas (nome_lista, validador_id, total_produtos, total_quantidade)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """, (
                    nome_lista,
                    validador_id,
                    len(produtos_unificados),
                    sum(p['quantidade_total'] for p in produtos_unificados.values())
                ))
                
                lista_unificada_id = cursor.fetchone()[0]
                print(f"Lista unificada criada com ID: {lista_unificada_id}")
                
                # Salvar produtos unificados
                for produto in produtos_unificados.values():
                    cursor.execute("""
                    INSERT INTO produtos_unificados 
                    (lista_unificada_id, ean, nome, cor, voltagem, modelo, quantidade_total, listas_origem)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        lista_unificada_id,
                        produto["ean"],
                        produto["nome"],
                        produto["cor"],
                        produto["voltagem"],
                        produto["modelo"],
                        produto["quantidade_total"],
                        json.dumps(produto["listas_origem"])
                    ))
                
                conn.commit()
                print(f"Lista unificada '{nome_lista}' criada com sucesso!")
                return lista_unificada_id
                
    except Exception as e:
        print(f"Erro ao criar lista unificada: {e}")
        return None

def buscar_produtos_lista_validada(data_envio, nome_usuario):
    """
    Busca produtos de uma lista específica que foi validada.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Buscar ID do usuário
                cursor.execute("SELECT id FROM usuarios WHERE nome = %s", (nome_usuario,))
                usuario = cursor.fetchone()
                
                if not usuario:
                    print(f"Usuário não encontrado: {nome_usuario}")
                    return []
                
                usuario_id = usuario[0]
                
                # Buscar produtos da lista
                if isinstance(data_envio, datetime):
                    data_envio_str = data_envio.strftime("%Y-%m-%d %H:%M")
                else:
                    data_envio_str = str(data_envio)
                
                cursor.execute("""
                SELECT ean, nome, cor, voltagem, modelo, quantidade, data_envio
                FROM produtos 
                WHERE usuario_id = %s AND data_envio::text LIKE %s AND validado = 1
                """, (usuario_id, f"{data_envio_str}%"))
                
                produtos = []
                for row in cursor.fetchall():
                    produtos.append({
                        'ean': row['ean'],
                        'nome': row['nome'],
                        'cor': row['cor'] or '',
                        'voltagem': row['voltagem'] or '',
                        'modelo': row['modelo'] or '',
                        'quantidade': row['quantidade'],
                        'data_envio': row['data_envio']
                    })
                
                return produtos
                
    except Exception as e:
        print(f"Erro ao buscar produtos da lista validada: {e}")
        return []

def carregar_listas_unificadas():
    """
    Carrega todas as listas unificadas.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Buscar todas as listas
                cursor.execute("""
                SELECT lu.*, u.nome as nome_validador
                FROM listas_unificadas lu
                JOIN usuarios u ON lu.validador_id = u.id
                ORDER BY lu.data_criacao DESC
                """)
                
                listas = []
                for row in cursor.fetchall():
                    listas.append({
                        'id': row['id'],
                        'nome_lista': row['nome_lista'],
                        'nome_validador': row['nome_validador'],
                        'data_criacao': row['data_criacao'],
                        'total_produtos': row['total_produtos'],
                        'total_quantidade': row['total_quantidade']
                    })
                
                return listas
                
    except Exception as e:
        print(f"Erro ao carregar listas unificadas: {e}")
        return {
            'listas': [],
            'paginacao': {
                'pagina_atual': 1,
                'total_paginas': 0,
                'total_registros': 0,
                'por_pagina': por_pagina,
                'tem_anterior': False,
                'tem_proximo': False,
                'pagina_anterior': None,
                'pagina_proximo': None
            }
        }

def carregar_produtos_lista_unificada(lista_unificada_id):
    """
    Carrega produtos de uma lista unificada específica.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                SELECT * FROM produtos_unificados 
                WHERE lista_unificada_id = %s
                ORDER BY nome
                """, (lista_unificada_id,))
                
                produtos = []
                for row in cursor.fetchall():
                    # Parse das listas de origem
                    listas_origem = []
                    if row['listas_origem']:
                        try:
                            listas_origem = json.loads(row['listas_origem'])
                        except:
                            listas_origem = []
                    
                    produtos.append({
                        'id': row['id'],
                        'ean': row['ean'],
                        'nome': row['nome'],
                        'cor': row['cor'] or '',
                        'voltagem': row['voltagem'] or '',
                        'modelo': row['modelo'] or '',
                        'quantidade_total': row['quantidade_total'],
                        'listas_origem': listas_origem,
                        'data_criacao': row['data_criacao']
                    })
                
                return produtos
                
    except Exception as e:
        print(f"Erro ao carregar produtos da lista unificada: {e}")
        return []

def excluir_produto(produto_id, usuario_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM produtos WHERE id = %s AND usuario_id = %s AND enviado = 0 AND ativo = TRUE", 
                              (produto_id, usuario_id))
                produto = cursor.fetchone()
                
                if not produto:
                    return False
                
                cursor.execute("DELETE FROM produtos WHERE id = %s", (produto_id,))
                
        return True
    except psycopg2.Error as e:
        print(f"Erro ao excluir produto: {e}")
        conn.rollback()
        return False

from src.mercado_livre import buscar_produto_por_ean as buscar_produto_online

# ============================================================================
# FUNÇÕES DE MÉTRICAS PARA PAINEL DE DESEMPENHO
# ============================================================================

def obter_metricas_usuarios(periodo_dias=None):
    """
    Obtém métricas de desempenho dos usuários.
    Se periodo_dias for especificado, filtra apenas os produtos desse período.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Query base para métricas dos usuários
                if periodo_dias:
                    # Tratamento especial para "último dia" (apenas hoje)
                    if periodo_dias == 1:
                        # Query para apenas hoje (data atual)
                        base_query = """
                        SELECT 
                            u.id,
                            u.nome,
                            COUNT(CASE WHEN DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.id END) as total_produtos,
                            COUNT(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN 1 END) as produtos_enviados,
                            COUNT(CASE WHEN p.validado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN 1 END) as produtos_validados,
                            MAX(CASE WHEN p.enviado = 1 THEN p.data_envio::timestamp ELSE p.timestamp END) as ultima_atividade,
                            MIN(CASE WHEN DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.timestamp END) as primeira_atividade,
                            SUM(CASE WHEN DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as quantidade_total,
                            MIN(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.data_envio::timestamp END) as primeiro_envio,
                            MAX(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.data_envio::timestamp END) as ultimo_envio,
                            SUM(CASE WHEN p.destino = 'mercado_livre' AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_mercado_livre,
                            SUM(CASE WHEN p.destino = 'loja' AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_loja,
                            SUM(CASE WHEN p.destino = 'manutencao' AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_manutencao,
                            SUM(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_geral_enviado
                        FROM usuarios u
                        LEFT JOIN produtos p ON u.id = p.usuario_id
                        WHERE u.admin = 2
                        GROUP BY u.id, u.nome
                        ORDER BY total_produtos DESC
                        """
                        params = []
                    else:
                        # Query com filtro de período - aplica filtro apenas nos cálculos
                        base_query = """
                        SELECT 
                            u.id,
                            u.nome,
                            COUNT(CASE WHEN p.timestamp >= NOW() - INTERVAL %s THEN p.id END) as total_produtos,
                            COUNT(CASE WHEN p.enviado = 1 AND p.timestamp >= NOW() - INTERVAL %s THEN 1 END) as produtos_enviados,
                            COUNT(CASE WHEN p.validado = 1 AND p.timestamp >= NOW() - INTERVAL %s THEN 1 END) as produtos_validados,
                            MAX(CASE WHEN p.enviado = 1 THEN p.data_envio::timestamp ELSE p.timestamp END) as ultima_atividade,
                            MIN(CASE WHEN p.timestamp >= NOW() - INTERVAL %s THEN p.timestamp END) as primeira_atividade,
                            SUM(CASE WHEN p.timestamp >= NOW() - INTERVAL %s THEN p.quantidade ELSE 0 END) as quantidade_total,
                            MIN(CASE WHEN p.enviado = 1 AND p.timestamp >= NOW() - INTERVAL %s THEN p.data_envio END) as primeiro_envio,
                            MAX(CASE WHEN p.enviado = 1 AND p.timestamp >= NOW() - INTERVAL %s THEN p.data_envio END) as ultimo_envio,
                            SUM(CASE WHEN p.destino = 'mercado_livre' AND p.timestamp >= NOW() - INTERVAL %s THEN p.quantidade ELSE 0 END) as total_mercado_livre,
                            SUM(CASE WHEN p.destino = 'loja' AND p.timestamp >= NOW() - INTERVAL %s THEN p.quantidade ELSE 0 END) as total_loja,
                            SUM(CASE WHEN p.destino = 'manutencao' AND p.timestamp >= NOW() - INTERVAL %s THEN p.quantidade ELSE 0 END) as total_manutencao,
                            SUM(CASE WHEN p.enviado = 1 AND p.timestamp >= NOW() - INTERVAL %s THEN p.quantidade ELSE 0 END) as total_geral_enviado
                        FROM usuarios u
                        LEFT JOIN produtos p ON u.id = p.usuario_id
                        WHERE u.admin = 2
                        GROUP BY u.id, u.nome
                        ORDER BY total_produtos DESC
                        """
                        params = [f"{periodo_dias} days"] * 11  # 11 parâmetros para os INTERVAL
                else:
                    # Query sem filtro de período - mostra todos os dados históricos
                    base_query = """
                    SELECT 
                        u.id,
                        u.nome,
                        COUNT(p.id) as total_produtos,
                        COUNT(CASE WHEN p.enviado = 1 THEN 1 END) as produtos_enviados,
                        COUNT(CASE WHEN p.validado = 1 THEN 1 END) as produtos_validados,
                        MAX(CASE WHEN p.enviado = 1 THEN p.data_envio::timestamp ELSE p.timestamp END) as ultima_atividade,
                        MIN(p.timestamp) as primeira_atividade,
                        SUM(p.quantidade) as quantidade_total,
                        MIN(CASE WHEN p.enviado = 1 THEN p.data_envio END) as primeiro_envio,
                        MAX(CASE WHEN p.enviado = 1 THEN p.data_envio END) as ultimo_envio,
                        SUM(CASE WHEN p.destino = 'mercado_livre' THEN p.quantidade ELSE 0 END) as total_mercado_livre,
                        SUM(CASE WHEN p.destino = 'loja' THEN p.quantidade ELSE 0 END) as total_loja,
                        SUM(CASE WHEN p.destino = 'manutencao' THEN p.quantidade ELSE 0 END) as total_manutencao,
                        SUM(CASE WHEN p.enviado = 1 THEN p.quantidade ELSE 0 END) as total_geral_enviado
                    FROM usuarios u
                    LEFT JOIN produtos p ON u.id = p.usuario_id
                    WHERE u.admin = 2
                    GROUP BY u.id, u.nome
                    ORDER BY total_produtos DESC
                    """
                    params = []
                
                cursor.execute(base_query, params)
                usuarios = []
                
                for row in cursor.fetchall():
                    # Calcular Taxa de Envio: Produtos Enviados / Total de Horas de Envio Ativo
                    taxa_envio = 0
                    if row['produtos_enviados'] and row['primeiro_envio'] and row['ultimo_envio']:
                        primeiro_envio = row['primeiro_envio']
                        ultimo_envio = row['ultimo_envio']
                        
                        # Garantir que as datas são objetos datetime
                        if isinstance(primeiro_envio, str):
                            from datetime import datetime
                            primeiro_envio = datetime.fromisoformat(primeiro_envio.replace('Z', '+00:00'))
                        if isinstance(ultimo_envio, str):
                            from datetime import datetime
                            ultimo_envio = datetime.fromisoformat(ultimo_envio.replace('Z', '+00:00'))
                        
                        # Calcular diferença em horas
                        if primeiro_envio == ultimo_envio:
                            # Se só há um envio, considerar 1 hora
                            horas_ativo = 1
                        else:
                            try:
                                diferenca = ultimo_envio - primeiro_envio
                                horas_ativo = diferenca.total_seconds() / 3600  # Converter para horas
                                if horas_ativo < 1:
                                    horas_ativo = 1  # Mínimo de 1 hora
                            except (TypeError, AttributeError):
                                # Em caso de erro, usar 1 hora como padrão
                                horas_ativo = 1
                        
                        taxa_envio = row['produtos_enviados'] / horas_ativo
                    
                    usuarios.append({
                        'id': row['id'],
                        'nome': row['nome'],
                        'total_produtos': row['total_produtos'] or 0,
                        'produtos_enviados': row['produtos_enviados'] or 0,
                        'produtos_validados': row['produtos_validados'] or 0,
                        'quantidade_total': row['quantidade_total'] or 0,
                        'ultima_atividade': row['ultima_atividade'],
                        'primeira_atividade': row['primeira_atividade'],
                        'taxa_envio': round(taxa_envio, 2),
                        'total_mercado_livre': row['total_mercado_livre'] or 0,
                        'total_loja': row['total_loja'] or 0,
                        'total_manutencao': row['total_manutencao'] or 0,
                        'total_geral_enviado': row['total_geral_enviado'] or 0
                    })
                
                return usuarios
                
    except Exception as e:
        print(f"Erro ao obter métricas dos usuários: {e}")
        return []

def obter_metricas_usuarios_por_periodo(data_inicio, data_fim):
    """
    Obtém métricas de desempenho dos usuários para um período específico.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Converter datas para timezone local (não UTC)
                from datetime import datetime, timezone
                import pytz
                
                # Assumir que as datas de entrada são em timezone local (Brasil)
                brasil_tz = pytz.timezone('America/Sao_Paulo')
                
                # Se as datas não têm timezone, assumir que são em timezone local
                if data_inicio.tzinfo is None:
                    data_inicio = brasil_tz.localize(data_inicio)
                if data_fim.tzinfo is None:
                    data_fim = brasil_tz.localize(data_fim)
                
                # CORREÇÃO: Usar apenas data sem hora para evitar problemas de timezone
                data_inicio_local = data_inicio.strftime('%Y-%m-%d')
                data_fim_local = data_fim.strftime('%Y-%m-%d')
                
                base_query = """
                SELECT 
                    u.id,
                    u.nome,
                    COUNT(p.id) as total_produtos,
                    COUNT(CASE WHEN p.enviado = 1 THEN 1 END) as produtos_enviados,
                    COUNT(CASE WHEN p.validado = 1 THEN 1 END) as produtos_validados,
                    MAX(CASE WHEN p.enviado = 1 THEN p.data_envio::timestamp ELSE p.timestamp END) as ultima_atividade,
                    MIN(p.timestamp) as primeira_atividade,
                    SUM(p.quantidade) as quantidade_total,
                    MIN(CASE WHEN p.enviado = 1 THEN p.data_envio END) as primeiro_envio,
                    MAX(CASE WHEN p.enviado = 1 THEN p.data_envio END) as ultimo_envio,
                    SUM(CASE WHEN p.destino = 'mercado_livre' THEN p.quantidade ELSE 0 END) as total_mercado_livre,
                    SUM(CASE WHEN p.destino = 'loja' THEN p.quantidade ELSE 0 END) as total_loja,
                    SUM(CASE WHEN p.destino = 'manutencao' THEN p.quantidade ELSE 0 END) as total_manutencao,
                    SUM(CASE WHEN p.enviado = 1 THEN p.quantidade ELSE 0 END) as total_geral_enviado
                FROM usuarios u
                LEFT JOIN produtos p ON u.id = p.usuario_id
                WHERE u.admin = 2 AND DATE(p.timestamp - INTERVAL '3 hours') >= %s::date AND DATE(p.timestamp - INTERVAL '3 hours') <= %s::date
                GROUP BY u.id, u.nome
                ORDER BY total_produtos DESC
                """
                
                cursor.execute(base_query, [data_inicio_local, data_fim_local])
                usuarios = []
                
                for row in cursor.fetchall():
                    # Calcular Taxa de Envio
                    taxa_envio = 0
                    if row['produtos_enviados'] and row['primeiro_envio'] and row['ultimo_envio']:
                        primeiro_envio = row['primeiro_envio']
                        ultimo_envio = row['ultimo_envio']
                        
                        if isinstance(primeiro_envio, str):
                            from datetime import datetime
                            primeiro_envio = datetime.fromisoformat(primeiro_envio.replace('Z', '+00:00'))
                        if isinstance(ultimo_envio, str):
                            from datetime import datetime
                            ultimo_envio = datetime.fromisoformat(ultimo_envio.replace('Z', '+00:00'))
                        
                        if primeiro_envio == ultimo_envio:
                            horas_ativo = 1
                        else:
                            try:
                                diferenca = ultimo_envio - primeiro_envio
                                horas_ativo = diferenca.total_seconds() / 3600
                                if horas_ativo < 1:
                                    horas_ativo = 1
                            except (TypeError, AttributeError):
                                horas_ativo = 1
                        
                        taxa_envio = row['produtos_enviados'] / horas_ativo
                    
                    usuarios.append({
                        'id': row['id'],
                        'nome': row['nome'],
                        'total_produtos': row['total_produtos'] or 0,
                        'produtos_enviados': row['produtos_enviados'] or 0,
                        'produtos_validados': row['produtos_validados'] or 0,
                        'quantidade_total': row['quantidade_total'] or 0,
                        'ultima_atividade': row['ultima_atividade'],
                        'primeira_atividade': row['primeira_atividade'],
                        'taxa_envio': round(taxa_envio, 2),
                        'total_mercado_livre': row['total_mercado_livre'] or 0,
                        'total_loja': row['total_loja'] or 0,
                        'total_manutencao': row['total_manutencao'] or 0,
                        'total_geral_enviado': row['total_geral_enviado'] or 0
                    })
                
                return usuarios
                
    except Exception as e:
        print(f"Erro ao obter métricas dos usuários por período: {e}")
        return []

def obter_atividade_periodo(usuario_id=None, dias=7):
    """
    Obtém atividade dos usuários por período (últimos X dias).
    Se usuario_id for especificado, filtra apenas esse usuário.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                base_query = """
                SELECT 
                    u.nome,
                    DATE(p.timestamp - INTERVAL '3 hours') as data,
                    COUNT(p.id) as produtos_dia,
                    SUM(p.quantidade) as quantidade_dia
                FROM usuarios u
                LEFT JOIN produtos p ON u.id = p.usuario_id
                WHERE p.timestamp >= NOW() - INTERVAL %s
                    AND u.admin = 2
                """
                
                params = [f"{dias} days"]
                
                if usuario_id:
                    base_query += " AND u.id = %s"
                    params.append(usuario_id)
                
                base_query += """
                GROUP BY u.nome, DATE(p.timestamp - INTERVAL '3 hours')
                ORDER BY data DESC, u.nome
                """
                
                cursor.execute(base_query, params)
                atividades = []
                
                for row in cursor.fetchall():
                    atividades.append({
                        'nome_usuario': row['nome'],
                        'data': row['data'],
                        'produtos_dia': row['produtos_dia'] or 0,
                        'quantidade_dia': row['quantidade_dia'] or 0
                    })
                
                return atividades
                
    except Exception as e:
        print(f"Erro ao obter atividade por período: {e}")
        return []

def obter_estatisticas_gerais(periodo_dias=None):
    """
    Obtém estatísticas gerais do sistema.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Query para estatísticas gerais
                base_query = """
                SELECT 
                    COUNT(DISTINCT u.id) as total_usuarios_ativos,
                    SUM(CASE WHEN p.destino = 'mercado_livre' THEN p.quantidade ELSE 0 END) as total_produtos,
                    SUM(CASE WHEN p.destino = 'loja' AND p.enviado = 1 THEN p.quantidade ELSE 0 END) as total_enviados,
                    SUM(CASE WHEN p.destino = 'manutencao' AND p.enviado = 1 THEN p.quantidade ELSE 0 END) as total_validados,
                    SUM(p.quantidade) as quantidade_total
                FROM usuarios u
                LEFT JOIN produtos p ON u.id = p.usuario_id
                WHERE u.admin = 2
                """
                
                params = []
                
                if periodo_dias:
                    base_query += " AND p.timestamp >= NOW() - INTERVAL %s"
                    params.append(f"{periodo_dias} days")
                
                cursor.execute(base_query, params)
                resultado = cursor.fetchone()
                
                if resultado:
                    return {
                        'total_usuarios_ativos': resultado['total_usuarios_ativos'] or 0,
                        'total_produtos': resultado['total_produtos'] or 0,
                        'total_enviados': resultado['total_enviados'] or 0,
                        'total_validados': resultado['total_validados'] or 0,
                        'quantidade_total': resultado['quantidade_total'] or 0
                    }
                
                return {
                    'total_usuarios_ativos': 0,
                    'total_produtos': 0,
                    'total_enviados': 0,
                    'total_validados': 0,
                    'quantidade_total': 0
                }
                
    except Exception as e:
        print(f"Erro ao obter estatísticas gerais: {e}")
        return {
            'total_usuarios_ativos': 0,
            'total_produtos': 0,
            'total_enviados': 0,
            'total_validados': 0,
            'quantidade_total': 0
        }

def obter_atividade_por_periodo_customizado(data_inicio, data_fim):
    """
    Obtém atividade dos usuários para um período customizado.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Converter datas para timezone local
                from datetime import datetime
                import pytz
                
                brasil_tz = pytz.timezone('America/Sao_Paulo')
                
                if data_inicio.tzinfo is None:
                    data_inicio = brasil_tz.localize(data_inicio)
                if data_fim.tzinfo is None:
                    data_fim = brasil_tz.localize(data_fim)
                
                data_inicio_local = data_inicio.strftime('%Y-%m-%d')
                data_fim_local = data_fim.strftime('%Y-%m-%d')
                
                base_query = """
                SELECT 
                    u.nome,
                    DATE(p.timestamp - INTERVAL '3 hours') as data,
                    COUNT(p.id) as produtos_dia,
                    SUM(p.quantidade) as quantidade_dia
                FROM usuarios u
                LEFT JOIN produtos p ON u.id = p.usuario_id
                WHERE DATE(p.timestamp - INTERVAL '3 hours') >= %s::date AND DATE(p.timestamp - INTERVAL '3 hours') <= %s::date
                    AND u.admin = 2
                GROUP BY u.nome, DATE(p.timestamp - INTERVAL '3 hours')
                ORDER BY data DESC, u.nome
                """
                
                cursor.execute(base_query, [data_inicio_local, data_fim_local])
                atividades = []
                
                for row in cursor.fetchall():
                    atividades.append({
                        'nome_usuario': row['nome'],
                        'data': row['data'],
                        'produtos_dia': row['produtos_dia'] or 0,
                        'quantidade_dia': row['quantidade_dia'] or 0
                    })
                
                return atividades
                
    except Exception as e:
        print(f"Erro ao obter atividade por período customizado: {e}")
        return []

def obter_listas_aprovadas_por_responsavel(periodo_dias=None):
    """
    Obtém listas aprovadas agrupadas por responsável.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                if periodo_dias:
                    # Tratamento especial para "último dia" (apenas hoje)
                    if periodo_dias == 1:
                        # Query para apenas hoje (data atual)
                        base_query = """
                        SELECT 
                            u.id,
                            u.nome,
                            COUNT(CASE WHEN DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.id END) as total_produtos,
                            COUNT(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN 1 END) as produtos_enviados,
                            COUNT(CASE WHEN p.validado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN 1 END) as produtos_validados,
                            MAX(CASE WHEN p.enviado = 1 THEN p.data_envio::timestamp ELSE p.timestamp END) as ultima_atividade,
                            MIN(CASE WHEN DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.timestamp END) as primeira_atividade,
                            SUM(CASE WHEN DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as quantidade_total,
                            MIN(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.data_envio::timestamp END) as primeiro_envio,
                            MAX(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.data_envio::timestamp END) as ultimo_envio,
                            SUM(CASE WHEN p.destino = 'mercado_livre' AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_mercado_livre,
                            SUM(CASE WHEN p.destino = 'loja' AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_loja,
                            SUM(CASE WHEN p.destino = 'manutencao' AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_manutencao,
                            SUM(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_geral_enviado
                        FROM usuarios u
                        LEFT JOIN produtos p ON u.id = p.usuario_id
                        WHERE u.admin = 2
                        GROUP BY u.id, u.nome
                        ORDER BY total_produtos DESC
                        """
                        params = []
                    else:
                        # Query com filtro de período - aplica filtro apenas nos cálculos
                        base_query = """
                    SELECT 
                        r.nome as responsavel_nome,
                        COUNT(CASE WHEN p.validado = 1 AND p.data_envio >= NOW() - INTERVAL %s THEN p.data_envio END) as total_listas,
                        COUNT(CASE WHEN p.validado = 1 AND p.data_envio >= NOW() - INTERVAL %s THEN p.id END) as total_produtos,
                        SUM(CASE WHEN p.validado = 1 AND p.data_envio >= NOW() - INTERVAL %s THEN p.quantidade ELSE 0 END) as total_quantidade
                    FROM responsaveis r
                    LEFT JOIN produtos p ON r.id = p.responsavel_id
                    GROUP BY r.nome
                    ORDER BY total_listas DESC
                    """
                    params = [f"{periodo_dias} days"] * 3
                else:
                    # Query sem filtro de período - mostra todos os dados históricos
                    base_query = """
                    SELECT 
                        r.nome as responsavel_nome,
                        COUNT(DISTINCT p.data_envio) as total_listas,
                        COUNT(p.id) as total_produtos,
                        SUM(p.quantidade) as total_quantidade
                    FROM produtos p
                    LEFT JOIN responsaveis r ON p.responsavel_id = r.id
                    WHERE p.validado = 1
                    GROUP BY r.nome
                    ORDER BY total_listas DESC
                    """
                    params = []
                
                cursor.execute(base_query, params)
                listas = []
                
                for row in cursor.fetchall():
                    listas.append({
                        'responsavel_nome': row['responsavel_nome'] or 'Sem responsável',
                        'total_listas': row['total_listas'] or 0,
                        'total_produtos': row['total_produtos'] or 0,
                        'total_quantidade': row['total_quantidade'] or 0
                    })
                
                return listas
                
    except Exception as e:
        print(f"Erro ao obter listas aprovadas por responsável: {e}")
        return []

def obter_listas_aprovadas_por_periodo(data_inicio, data_fim):
    """
    Obtém listas aprovadas para um período específico.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Converter datas para timezone local
                from datetime import datetime
                import pytz
                
                brasil_tz = pytz.timezone('America/Sao_Paulo')
                
                if data_inicio.tzinfo is None:
                    data_inicio = brasil_tz.localize(data_inicio)
                if data_fim.tzinfo is None:
                    data_fim = brasil_tz.localize(data_fim)
                
                data_inicio_local = data_inicio.strftime('%Y-%m-%d %H:%M:%S')
                data_fim_local = data_fim.strftime('%Y-%m-%d %H:%M:%S')
                
                base_query = """
                SELECT 
                    r.nome as responsavel_nome,
                    COUNT(DISTINCT p.data_envio) as total_listas,
                    COUNT(p.id) as total_produtos,
                    SUM(p.quantidade) as total_quantidade
                FROM produtos p
                LEFT JOIN responsaveis r ON p.responsavel_id = r.id
                WHERE p.validado = 1 AND DATE(p.data_envio::timestamp - INTERVAL '3 hours') >= %s::date AND DATE(p.data_envio::timestamp - INTERVAL '3 hours') <= %s::date
                GROUP BY r.nome
                ORDER BY total_listas DESC
                """
                
                cursor.execute(base_query, [data_inicio_local, data_fim_local])
                listas = []
                
                for row in cursor.fetchall():
                    listas.append({
                        'responsavel_nome': row['responsavel_nome'] or 'Sem responsável',
                        'total_listas': row['total_listas'] or 0,
                        'total_produtos': row['total_produtos'] or 0,
                        'total_quantidade': row['total_quantidade'] or 0
                    })
                
                return listas
                
    except Exception as e:
        print(f"Erro ao obter listas aprovadas por período: {e}")
        return []

def obter_produtos_detalhados_por_periodo(data_inicio, data_fim):
    """
    Obtém produtos detalhados para um período específico.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Converter datas para timezone local
                from datetime import datetime
                import pytz
                
                brasil_tz = pytz.timezone('America/Sao_Paulo')
                
                if data_inicio.tzinfo is None:
                    data_inicio = brasil_tz.localize(data_inicio)
                if data_fim.tzinfo is None:
                    data_fim = brasil_tz.localize(data_fim)
                
                data_inicio_local = data_inicio.strftime('%Y-%m-%d %H:%M:%S')
                data_fim_local = data_fim.strftime('%Y-%m-%d %H:%M:%S')
                
                base_query = """
                SELECT 
                    p.ean,
                    p.nome,
                    p.cor,
                    p.voltagem,
                    p.modelo,
                    p.quantidade,
                    p.destino,
                    u.nome as usuario_nome,
                    r.nome as responsavel_nome,
                    p.data_envio,
                    p.data_validacao
                FROM produtos p
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                LEFT JOIN responsaveis r ON p.responsavel_id = r.id
                WHERE p.validado = 1 AND DATE(p.data_envio::timestamp - INTERVAL '3 hours') >= %s::date AND DATE(p.data_envio::timestamp - INTERVAL '3 hours') <= %s::date
                ORDER BY p.data_envio DESC
                """
                
                cursor.execute(base_query, [data_inicio_local, data_fim_local])
                produtos = []
                
                for row in cursor.fetchall():
                    produtos.append({
                        'ean': row['ean'],
                        'nome': row['nome'],
                        'cor': row['cor'],
                        'voltagem': row['voltagem'],
                        'modelo': row['modelo'],
                        'quantidade': row['quantidade'],
                        'destino': row['destino'],
                        'usuario_nome': row['usuario_nome'],
                        'responsavel_nome': row['responsavel_nome'] or 'Sem responsável',
                        'data_envio': row['data_envio'],
                        'data_validacao': row['data_validacao']
                    })
                
                return produtos
                
    except Exception as e:
        print(f"Erro ao obter produtos detalhados por período: {e}")
        return []

@app.route("/")
def index():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    
    produtos = carregar_produtos_usuario(session["usuario_id"], apenas_nao_enviados=True)
    return render_template("index.html", produtos=produtos)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nome = request.form.get("nome")
        senha = request.form.get("senha")
        
        usuario = verificar_usuario(nome, senha)
        if usuario:
            session["usuario_id"] = usuario["id"]
            session["usuario_nome"] = nome
            session["admin"] = usuario["admin"]
            session["logado"] = True
            
            # Redirecionar baseado no tipo de usuário
            if usuario["admin"] == 1:
                # Painel Administrativo
                return redirect(url_for("admin"))
            else:
                # Buscar tipo de usuário baseado no admin flag
                # admin = 0 -> sistema_estoque (padrão)
                # admin = 2 -> sistema_cadastro
                if usuario["admin"] == 2:
                    # Sistema de Cadastro de Produtos
                    return redirect(url_for("index"))
                else:
                    # Sistema de Estoque (padrão para admin = 0)
                    return redirect(url_for("estoque"))
        else:
            flash("Nome de usuário ou senha incorretos")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nome = request.form.get("nome")
        senha = request.form.get("senha")
        
        if registrar_usuario(nome, senha):
            flash("Usuário registrado com sucesso! Faça login.")
            return redirect(url_for("login"))
        else:
            flash("Erro ao registrar usuário. Nome de usuário já existe.")
    
    return render_template("registro.html")

@app.route("/stand_by")
def stand_by():
    if "usuario_id" not in session or not session.get("admin"):
        return redirect(url_for("login"))
    
    return render_template("stand_by.html")

@app.route("/admin")
def admin():
    if "usuario_id" not in session or not session.get("admin"):
        return redirect(url_for("login"))
    
    termo_pesquisa = request.args.get("pesquisa", "")
    pagina = request.args.get("pagina", 1, type=int)
    por_pagina = 40
    data_busca = request.args.get("data", "")
    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")
    criador_filtro = request.args.get("criador", "")
    
    resultado_paginacao = carregar_listas_enviadas_paginadas(
        pagina=pagina, 
        por_pagina=por_pagina, 
        termo_pesquisa=termo_pesquisa,
        data_busca=data_busca,
        data_inicio=data_inicio,
        data_fim=data_fim,
        criador_filtro=criador_filtro
    )
    
    print(f"Página {pagina}: {len(resultado_paginacao['listas_agrupadas'])} listas de {resultado_paginacao['total_listas']} total")
    
    return render_template("admin.html", 
                         listas_agrupadas=resultado_paginacao["listas_agrupadas"],
                         termo_pesquisa=termo_pesquisa,
                         paginacao=resultado_paginacao,
                         data_busca=data_busca,
                         data_inicio=data_inicio,
                         data_fim=data_fim,
                         criador_filtro=criador_filtro)

@app.route("/listas-unificadas")
def listas_unificadas():
    if "usuario_id" not in session or not session.get("admin"):
        return redirect(url_for("login"))
    
    listas = carregar_listas_unificadas()
    return render_template("listas_unificadas.html", listas=listas)

@app.route("/listas-unificadas/<int:lista_id>")
def detalhes_lista_unificada(lista_id):
    if "usuario_id" not in session or not session.get("admin"):
        return redirect(url_for("login"))
    
    # Carregar informações da lista
    listas = carregar_listas_unificadas()
    lista_info = None
    for lista in listas:
        if lista["id"] == lista_id:
            lista_info = lista
            break
    
    if not lista_info:
        flash("Lista unificada não encontrada", "error")
        return redirect(url_for("listas_unificadas"))
    
    # Carregar produtos da lista
    produtos = carregar_produtos_lista_unificada(lista_id)
    
    return render_template("detalhes_lista_unificada.html", 
                         lista_info=lista_info, 
                         produtos=produtos)

@app.route("/api/responsaveis", methods=["GET"])
def get_responsaveis():
    if "usuario_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    responsaveis = obter_responsaveis()
    return jsonify(responsaveis)

@app.route("/api/buscar-produto", methods=["GET"])
def buscar_produto():
    if "usuario_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    ean = request.args.get("ean")
    if not ean:
        return jsonify({"error": "EAN não fornecido"}), 400
    
    produto_local = buscar_produto_local(ean, session["usuario_id"])
    if produto_local:
        return jsonify({
            "ean": produto_local["ean"],
            "nome": produto_local["nome"],
            "cor": produto_local.get("cor", ""),
            "voltagem": produto_local.get("voltagem", ""),
            "modelo": produto_local.get("modelo", ""),
            "quantidade": produto_local["quantidade"],
            "message": "Produto já existe na sua lista atual.",
            "source": "local"
        }), 200
    
    resultado = buscar_produto_priorizado(ean)
    
    if resultado["success"]:
        produto_data = resultado["data"]
        produto_data["ean"] = ean
        produto_data["quantidade"] = 1
        
        source_message = ""
        if resultado["source"] == "listas_enviadas":
            source_message = " (encontrado nas listas enviadas)"
        elif resultado["source"] == "mercado_livre":
            source_message = " (encontrado no Mercado Livre)"
        
        return jsonify({
            **produto_data,
            "message": resultado.get("message", "") + source_message,
            "source": resultado["source"]
        }), 200
    else:
        return jsonify({
            "ean": ean,
            "nome": f"Produto {ean}",
            "cor": "",
            "voltagem": "",
            "modelo": "",
            "quantidade": 1,
            "message": resultado.get("message", "Produto não encontrado. Preencha manualmente."),
            "source": "manual"
        }), 200

@app.route("/api/buscar-por-nome", methods=["POST"])
def buscar_por_nome_api():
    try:
        if 'usuario_id' not in session:
            return jsonify({"error": "Usuário não autenticado"}), 401
        
        data = request.get_json()
        if not data or 'nome' not in data:
            return jsonify({"error": "Nome do produto é obrigatório"}), 400
        
        nome = data['nome'].strip()
        if len(nome) < 3:
            return jsonify({"error": "Nome deve ter pelo menos 3 caracteres"}), 400
        
        produtos = buscar_produtos_por_nome(nome)
        
        return jsonify({
            "success": True,
            "produtos": produtos,
            "total": len(produtos)
        }), 200
        
    except Exception as e:
        print(f"Erro na rota buscar-por-nome: {e}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@app.route("/api/produtos", methods=["GET"])
def get_produtos():
    if "usuario_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    produtos = carregar_produtos_usuario(session["usuario_id"], apenas_nao_enviados=True)
    return jsonify(produtos)

@app.route("/api/produtos", methods=["POST"])
def add_produto():
    if "usuario_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        produto = request.json
        if not produto or not produto.get("ean") or not produto.get("nome"):
            return jsonify({"error": "Dados do produto incompletos"}), 400
        
        # Validar motivo de manutenção se destino for manutenção
        if produto.get("destino") == "manutencao":
            motivo_manutencao = produto.get("motivo_manutencao", "").strip()
            if not motivo_manutencao:
                return jsonify({"error": "Motivo da manutenção é obrigatório quando o destino for Manutenção"}), 400
            if len(motivo_manutencao) < 10:
                return jsonify({"error": "Motivo da manutenção deve ter pelo menos 10 caracteres"}), 400
        
        try:
            produto["quantidade"] = int(produto.get("quantidade", 1))
        except ValueError:
            produto["quantidade"] = 1
        
        produto["timestamp"] = datetime.now()
        
        if salvar_produto(produto, session["usuario_id"]):
            produtos_atualizados = carregar_produtos_usuario(session["usuario_id"], apenas_nao_enviados=True)
            return jsonify(produtos_atualizados), 200
        else:
            return jsonify({"error": "Erro ao salvar produto"}), 500
    except Exception as e:
        print(f"Erro ao adicionar produto: {e}")
        return jsonify({"error": f"Erro ao processar requisição: {str(e)}"}), 500

@app.route("/api/produtos/<int:produto_id>", methods=["DELETE"])
def delete_produto(produto_id):
    if "usuario_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    if excluir_produto(produto_id, session["usuario_id"]):
        return jsonify({"success": True, "message": "Produto excluído com sucesso"}), 200
    else:
        return jsonify({"error": "Erro ao excluir produto"}), 500

def processar_envio_por_destino(usuario_id, responsavel_id, pin):
    """
    Processa o envio de produtos agrupados por destino
    """
    try:
        if not verificar_pin_responsavel(responsavel_id, pin):
            return {"success": False, "message": "PIN inválido"}
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Buscar produtos não enviados agrupados por destino
                cursor.execute("""
                    SELECT destino, COUNT(*) as quantidade_produtos, SUM(quantidade) as quantidade_total
                    FROM produtos 
                    WHERE usuario_id = %s AND enviado = 0 AND ativo = TRUE
                    GROUP BY destino
                """, (usuario_id,))
                
                destinos = cursor.fetchall()
                
                if not destinos:
                    return {"success": False, "message": "Nenhum produto para enviar"}
                
                data_envio = datetime.now()
                resultados = []
                
                for destino_info in destinos:
                    destino = destino_info[0]
                    qtd_produtos = destino_info[1]
                    qtd_total = destino_info[2]
                    
                    # Marcar produtos como enviados para este destino
                    cursor.execute("""
                        UPDATE produtos 
                        SET enviado = 1, data_envio = %s, responsavel_id = %s, responsavel_pin = %s
                        WHERE usuario_id = %s AND enviado = 0 AND ativo = TRUE AND destino = %s
                    """, (data_envio, responsavel_id, pin, usuario_id, destino))
                    
                    # Determinar nome do destino para exibição
                    nome_destino = destino
                    if destino == 'mercado_livre':
                        nome_destino = 'Mercado Livre'
                    elif destino == 'loja':
                        nome_destino = 'Loja'
                    elif destino == 'manutencao':
                        nome_destino = 'Manutenção'
                    
                    resultados.append({
                        "destino": nome_destino,
                        "produtos": qtd_produtos,
                        "quantidade_total": qtd_total
                    })
                
                conn.commit()
                
                # Criar mensagem de sucesso
                mensagem_destinos = []
                for resultado in resultados:
                    mensagem_destinos.append(f"{resultado['produtos']} produtos para {resultado['destino']}")
                
                mensagem = f"Lista enviada com sucesso: {', '.join(mensagem_destinos)}"
                
                return {
                    "success": True,
                    "message": mensagem,
                    "data_envio": formatar_data_brasileira(data_envio),
                    "destinos": resultados
                }
                
    except psycopg2.Error as e:
        print(f"Erro ao processar envio por destino: {e}")
        return {"success": False, "message": f"Erro no banco de dados: {e}"}
    except Exception as e:
        print(f"Erro inesperado ao processar envio: {e}")
        return {"success": False, "message": f"Erro inesperado: {e}"}

@app.route("/api/enviar-lista", methods=["POST"])
def enviar_lista():
    if "usuario_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        data = request.json
        responsavel_id = data.get("responsavel_id")
        pin = data.get("pin")
        
        if not responsavel_id or not pin:
            return jsonify({"error": "Responsável e PIN são obrigatórios"}), 400
        
        try:
            responsavel_id = int(responsavel_id)
        except ValueError:
            return jsonify({"error": "ID do responsável inválido"}), 400
        
        # Processar envio por destino
        resultado = processar_envio_por_destino(session["usuario_id"], responsavel_id, pin)
        
        if resultado["success"]:
            return jsonify(resultado), 200
        else:
            return jsonify({"error": resultado["message"]}), 400
    except Exception as e:
        print(f"Erro ao enviar lista de produtos: {e}")
        return jsonify({"error": f"Erro ao processar requisição: {str(e)}"}), 500

# Novas rotas para destinos específicos
@app.route("/api/enviar-loja", methods=["POST"])
def enviar_loja():
    """Rota específica para envio de produtos para a Loja"""
    if "usuario_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        data = request.json
        responsavel_id = data.get("responsavel_id")
        pin = data.get("pin")
        
        if not responsavel_id or not pin:
            return jsonify({"error": "Responsável e PIN são obrigatórios"}), 400
        
        resultado = processar_envio_destino_especifico(session["usuario_id"], responsavel_id, pin, "loja")
        
        if resultado["success"]:
            return jsonify(resultado), 200
        else:
            return jsonify({"error": resultado["message"]}), 400
    except Exception as e:
        print(f"Erro ao enviar para loja: {e}")
        return jsonify({"error": f"Erro ao processar requisição: {str(e)}"}), 500

@app.route("/api/enviar-manutencao", methods=["POST"])
def enviar_manutencao():
    """Rota específica para envio de produtos para Manutenção"""
    if "usuario_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        data = request.json
        responsavel_id = data.get("responsavel_id")
        pin = data.get("pin")
        
        if not responsavel_id or not pin:
            return jsonify({"error": "Responsável e PIN são obrigatórios"}), 400
        
        resultado = processar_envio_destino_especifico(session["usuario_id"], responsavel_id, pin, "manutencao")
        
        if resultado["success"]:
            return jsonify(resultado), 200
        else:
            return jsonify({"error": resultado["message"]}), 400
    except Exception as e:
        print(f"Erro ao enviar para manutenção: {e}")
        return jsonify({"error": f"Erro ao processar requisição: {str(e)}"}), 500

@app.route("/api/enviar-lista-automatica", methods=["POST"])
def enviar_lista_automatica():
    """Rota para envio automático distribuindo produtos por destinos"""
    if "usuario_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        data = request.json
        responsavel_id = data.get("responsavel_id")
        pin = data.get("pin")
        
        if not responsavel_id or not pin:
            return jsonify({"error": "Responsável e PIN são obrigatórios"}), 400
        
        # Processar envio automático por destinos
        resultado = processar_envio_automatico_por_destinos(session["usuario_id"], responsavel_id, pin)
        
        if resultado["success"]:
            return jsonify(resultado), 200
        else:
            return jsonify({"error": resultado["message"]}), 400
    except Exception as e:
        print(f"Erro ao enviar lista automática: {e}")
        return jsonify({"error": f"Erro ao processar requisição: {str(e)}"}), 500

def processar_envio_automatico_por_destinos(usuario_id, responsavel_id, pin):
    """
    Processa o envio automático de produtos distribuindo por destinos
    """
    try:
        if not verificar_pin_responsavel(responsavel_id, pin):
            return {"success": False, "message": "PIN inválido"}
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Buscar produtos não enviados agrupados por destino
                cursor.execute("""
                    SELECT destino, COUNT(*) as quantidade_produtos, SUM(quantidade) as quantidade_total
                    FROM produtos 
                    WHERE usuario_id = %s AND enviado = 0 AND ativo = TRUE
                    GROUP BY destino
                """, (usuario_id,))
                
                destinos = cursor.fetchall()
                
                if not destinos:
                    return {"success": False, "message": "Nenhum produto para enviar"}
                
                data_envio = datetime.now()
                resultados = []
                
                for destino_info in destinos:
                    destino = destino_info[0]
                    qtd_produtos = destino_info[1]
                    qtd_total = destino_info[2]
                    
                    # Processar cada destino
                    if destino == 'mercado_livre':
                        # Para Mercado Livre, usar a lógica existente do stand-by
                        resultado_ml = processar_envio_mercado_livre(usuario_id, responsavel_id, pin, cursor, data_envio)
                        if resultado_ml:
                            resultados.append({
                                "destino": "Mercado Livre",
                                "produtos": qtd_produtos,
                                "quantidade_total": qtd_total
                            })
                    
                    elif destino == 'loja':
                        # Para Loja, criar lista e produtos específicos
                        resultado_loja = processar_envio_loja(usuario_id, cursor, data_envio)
                        if resultado_loja:
                            resultados.append({
                                "destino": "Loja", 
                                "produtos": qtd_produtos,
                                "quantidade_total": qtd_total
                            })
                    
                    elif destino == 'manutencao':
                        # Para Manutenção, criar lista e produtos específicos
                        resultado_manutencao = processar_envio_manutencao(usuario_id, cursor, data_envio)
                        if resultado_manutencao:
                            resultados.append({
                                "destino": "Manutenção",
                                "produtos": qtd_produtos,
                                "quantidade_total": qtd_total
                            })
                    
                    # Marcar produtos como enviados para este destino
                    cursor.execute("""
                        UPDATE produtos 
                        SET enviado = 1, data_envio = %s, responsavel_id = %s, responsavel_pin = %s
                        WHERE usuario_id = %s AND enviado = 0 AND ativo = TRUE AND destino = %s
                    """, (data_envio, responsavel_id, pin, usuario_id, destino))
                
                conn.commit()
                
                # Criar resumo da operação
                if resultados:
                    resumo_destinos = []
                    for resultado in resultados:
                        resumo_destinos.append(f"🎯 {resultado['destino']}: {resultado['produtos']} produto(s)")
                    
                    resumo = "Produtos enviados automaticamente:\n\n" + "\n".join(resumo_destinos)
                    
                    return {
                        "success": True,
                        "message": "Lista enviada automaticamente com sucesso!",
                        "resumo": resumo,
                        "data_envio": formatar_data_brasileira(data_envio),
                        "destinos": resultados
                    }
                else:
                    return {"success": False, "message": "Nenhum produto foi processado"}
                
    except psycopg2.Error as e:
        print(f"Erro ao processar envio automático: {e}")
        return {"success": False, "message": f"Erro no banco de dados: {e}"}
    except Exception as e:
        print(f"Erro inesperado ao processar envio automático: {e}")
        return {"success": False, "message": f"Erro inesperado: {e}"}

def processar_envio_mercado_livre(usuario_id, responsavel_id, pin, cursor, data_envio):
    """Processa envio para Mercado Livre (stand-by)"""
    try:
        # Buscar produtos do Mercado Livre
        cursor.execute("""
            SELECT ean, nome, cor, voltagem, modelo, quantidade
            FROM produtos 
            WHERE usuario_id = %s AND enviado = 0 AND ativo = TRUE AND destino = 'mercado_livre'
        """, (usuario_id,))
        
        produtos = cursor.fetchall()
        
        if produtos:
            # Criar lista no stand-by
            cursor.execute("""
                INSERT INTO listas_standby (usuario_id, data_envio)
                VALUES (%s, %s)
                RETURNING id
            """, (usuario_id, data_envio))
            
            lista_standby_id = cursor.fetchone()[0]
            
            # Copiar produtos para stand-by
            for produto in produtos:
                cursor.execute("""
                    INSERT INTO produtos_standby (lista_standby_id, ean, nome, cor, voltagem, modelo, quantidade)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (lista_standby_id, produto[0], produto[1], produto[2], produto[3], produto[4], produto[5]))
            
            return True
        return False
    except Exception as e:
        print(f"Erro ao processar Mercado Livre: {e}")
        return False

def processar_envio_loja(usuario_id, cursor, data_envio):
    """Processa envio para Loja"""
    try:
        # Buscar produtos da Loja
        cursor.execute("""
            SELECT ean, nome, cor, voltagem, modelo, quantidade
            FROM produtos 
            WHERE usuario_id = %s AND enviado = 0 AND ativo = TRUE AND destino = 'loja'
        """, (usuario_id,))
        
        produtos = cursor.fetchall()
        
        if produtos:
            # Criar lista na loja
            cursor.execute("""
                INSERT INTO listas_loja (usuario_id, data_envio)
                VALUES (%s, %s)
                RETURNING id
            """, (usuario_id, data_envio))
            
            lista_loja_id = cursor.fetchone()[0]
            
            # Copiar produtos para loja
            for produto in produtos:
                cursor.execute("""
                    INSERT INTO produtos_loja (lista_loja_id, ean, nome, cor, voltagem, modelo, quantidade, usuario_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (lista_loja_id, produto[0], produto[1], produto[2], produto[3], produto[4], produto[5], usuario_id))
            
            return True
        return False
    except Exception as e:
        print(f"Erro ao processar Loja: {e}")
        return False

def processar_envio_manutencao(usuario_id, cursor, data_envio):
    """Processa envio para Manutenção"""
    try:
        # Buscar produtos da Manutenção
        cursor.execute("""
            SELECT ean, nome, cor, voltagem, modelo, quantidade
            FROM produtos 
            WHERE usuario_id = %s AND enviado = 0 AND ativo = TRUE AND destino = 'manutencao'
        """, (usuario_id,))
        
        produtos = cursor.fetchall()
        
        if produtos:
            # Criar lista na manutenção
            cursor.execute("""
                INSERT INTO listas_manutencao (usuario_id, data_envio)
                VALUES (%s, %s)
                RETURNING id
            """, (usuario_id, data_envio))
            
            lista_manutencao_id = cursor.fetchone()[0]
            
            # Copiar produtos para manutenção
            for produto in produtos:
                cursor.execute("""
                    INSERT INTO produtos_manutencao (lista_manutencao_id, ean, nome, cor, voltagem, modelo, quantidade, usuario_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (lista_manutencao_id, produto[0], produto[1], produto[2], produto[3], produto[4], produto[5], usuario_id))
            
            return True
        return False
    except Exception as e:
        print(f"Erro ao processar Manutenção: {e}")
        return False

def processar_envio_destino_especifico(usuario_id, responsavel_id, pin, destino):
    """
    Processa o envio de produtos para um destino específico
    """
    try:
        if not verificar_pin_responsavel(responsavel_id, pin):
            return {"success": False, "message": "PIN inválido"}
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Buscar produtos não enviados para o destino específico
                cursor.execute("""
                    SELECT COUNT(*) as quantidade_produtos, SUM(quantidade) as quantidade_total
                    FROM produtos 
                    WHERE usuario_id = %s AND enviado = 0 AND ativo = TRUE AND destino = %s
                """, (usuario_id, destino))
                
                resultado = cursor.fetchone()
                
                if not resultado or resultado[0] == 0:
                    nome_destino = "Loja" if destino == "loja" else "Manutenção"
                    return {"success": False, "message": f"Nenhum produto para enviar para {nome_destino}"}
                
                qtd_produtos = resultado[0]
                qtd_total = resultado[1]
                data_envio = datetime.now()
                
                # Marcar produtos como enviados para este destino
                cursor.execute("""
                    UPDATE produtos 
                    SET enviado = 1, data_envio = %s, responsavel_id = %s, responsavel_pin = %s
                    WHERE usuario_id = %s AND enviado = 0 AND ativo = TRUE AND destino = %s
                """, (data_envio, responsavel_id, pin, usuario_id, destino))
                
                conn.commit()
                
                # Determinar nome do destino para exibição
                nome_destino = "Loja" if destino == "loja" else "Manutenção"
                
                return {
                    "success": True,
                    "message": f"{qtd_produtos} produtos enviados para {nome_destino} com sucesso",
                    "data_envio": formatar_data_brasileira(data_envio),
                    "destino": nome_destino,
                    "produtos": qtd_produtos,
                    "quantidade_total": qtd_total
                }
                
    except psycopg2.Error as e:
        print(f"Erro ao processar envio para {destino}: {e}")
        return {"success": False, "message": f"Erro no banco de dados: {e}"}
    except Exception as e:
        print(f"Erro inesperado ao processar envio para {destino}: {e}")
        return {"success": False, "message": f"Erro inesperado: {e}"}

# Rotas para os painéis Loja e Manutenção
@app.route("/painel-loja")
def painel_loja():
    if 'usuario_id' not in session or session.get('admin') != 1:
        return redirect(url_for("login"))
    
    return render_template("loja.html")

@app.route("/painel-manutencao")
def painel_manutencao():
    if 'usuario_id' not in session or session.get('admin') != 1:
        return redirect(url_for("login"))
    
    return render_template("manutencao.html")

@app.route("/painel-assistencia")
def painel_assistencia():
    if 'usuario_id' not in session or session.get('admin') != 1:
        return redirect(url_for("login"))
    
    return render_template("assistencia.html")

# APIs para os painéis
@app.route("/api/produtos-loja")
def api_produtos_loja():
    if 'usuario_id' not in session or session.get('admin') != 1:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Buscar produtos enviados para loja
                cursor.execute("""
                    SELECT p.*, u.nome as usuario_nome
                    FROM produtos p
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE p.destino = 'loja' AND p.enviado = 1 AND p.ativo = TRUE
                    ORDER BY p.data_envio DESC
                """)
                
                produtos = []
                for row in cursor.fetchall():
                    produto = dict(row)
                    produto['data_envio_formatada'] = formatar_data_brasileira(produto['data_envio'])
                    produtos.append(produto)
                
                # Calcular estatísticas
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_produtos,
                        SUM(quantidade) as quantidade_total,
                        COUNT(CASE WHEN data_envio::timestamp >= NOW() - INTERVAL '7 days' THEN 1 END) as produtos_recentes,
                        COUNT(DISTINCT usuario_id) as usuarios_ativos
                    FROM produtos 
                    WHERE destino = 'loja' AND enviado = 1 AND ativo = TRUE
                """)
                
                stats = cursor.fetchone()
                estatisticas = {
                    'total_produtos': stats[0] or 0,
                    'quantidade_total': stats[1] or 0,
                    'produtos_recentes': stats[2] or 0,
                    'usuarios_ativos': stats[3] or 0
                }
                
                return jsonify({
                    "produtos": produtos,
                    "estatisticas": estatisticas
                })
                
    except psycopg2.Error as e:
        print(f"Erro ao buscar produtos da loja: {e}")
        return jsonify({"error": "Erro no banco de dados"}), 500

@app.route("/api/produtos-manutencao")
def api_produtos_manutencao():
    if 'usuario_id' not in session or session.get('admin') != 1:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        # Parâmetros de paginação
        pagina = int(request.args.get('pagina', 1))
        por_pagina = 20
        offset = (pagina - 1) * por_pagina
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Contar total de listas
                cursor.execute("""
                    SELECT COUNT(*) as total
                    FROM listas_manutencao lm
                """)
                total_listas = cursor.fetchone()['total']
                total_paginas = (total_listas + por_pagina - 1) // por_pagina
                
                # Buscar listas com paginação
                cursor.execute("""
                    SELECT 
                        lm.id,
                        lm.usuario_id,
                        lm.data_envio,
                        u.nome as usuario_nome,
                        COUNT(pm.id) as total_produtos,
                        SUM(pm.quantidade) as quantidade_total
                    FROM listas_manutencao lm
                    JOIN usuarios u ON lm.usuario_id = u.id
                    LEFT JOIN produtos_manutencao pm ON lm.id = pm.lista_manutencao_id
                    GROUP BY lm.id, lm.usuario_id, lm.data_envio, u.nome
                    ORDER BY lm.data_envio DESC
                    LIMIT %s OFFSET %s
                """, (por_pagina, offset))
                
                listas = []
                for row in cursor.fetchall():
                    lista = dict(row)
                    lista['data_envio_formatada'] = formatar_data_brasileira(lista['data_envio'])
                    
                    # Buscar produtos da lista
                    cursor.execute("""
                        SELECT 
                            pm.id,
                            pm.ean,
                            pm.nome,
                            pm.cor,
                            pm.voltagem,
                            pm.modelo,
                            pm.quantidade,
                            p.motivo_manutencao,
                            p.status_manutencao
                        FROM produtos_manutencao pm
                        LEFT JOIN produtos p ON pm.ean = p.ean 
                           AND p.destino = 'manutencao' 
                           AND p.enviado = 1
                           AND p.usuario_id = pm.usuario_id
                           AND p.data_envio::date = pm.data_envio::date
                        WHERE pm.lista_manutencao_id = %s
                        ORDER BY pm.nome
                    """, (lista['id'],))
                    
                    produtos = []
                    for produto_row in cursor.fetchall():
                        produto = dict(produto_row)
                        produtos.append(produto)
                    
                    lista['produtos'] = produtos
                    listas.append(lista)
                
                # Calcular estatísticas gerais
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT lm.id) as total_listas,
                        COUNT(pm.id) as total_produtos,
                        SUM(pm.quantidade) as quantidade_total,
                        COUNT(DISTINCT lm.usuario_id) as usuarios_ativos
                    FROM listas_manutencao lm
                    LEFT JOIN produtos_manutencao pm ON lm.id = pm.lista_manutencao_id
                """)
                
                stats = cursor.fetchone()
                estatisticas = {
                    'total_listas': stats['total_listas'] or 0,
                    'total_produtos': stats['total_produtos'] or 0,
                    'quantidade_total': stats['quantidade_total'] or 0,
                    'usuarios_ativos': stats['usuarios_ativos'] or 0
                }
                
                return jsonify({
                    "listas": listas,
                    "estatisticas": estatisticas,
                    "paginacao": {
                        "pagina_atual": pagina,
                        "total_paginas": total_paginas,
                        "total_produtos": total_listas,
                        "por_pagina": por_pagina
                    }
                })
                
    except psycopg2.Error as e:
        print(f"Erro ao buscar listas da manutenção: {e}")
        return jsonify({"error": "Erro no banco de dados"}), 500

@app.route("/api/atualizar-status-manutencao", methods=["POST"])
def atualizar_status_manutencao():
    if 'usuario_id' not in session or session.get('admin') != 1:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        data = request.get_json()
        produto_id = data.get('produto_id')
        novo_status = data.get('status')
        
        # Validar status
        status_validos = ['em_manutencao', 'reparo_concluido', 'descarte', None, '']
        if novo_status not in status_validos:
            return jsonify({"error": "Status inválido"}), 400
        
        # Converter string vazia para NULL
        if novo_status == '':
            novo_status = None
            
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE produtos 
                    SET status_manutencao = %s 
                    WHERE id = %s AND destino = 'manutencao' AND enviado = 1 AND ativo = TRUE
                """, (novo_status, produto_id))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    return jsonify({"success": True, "message": "Status atualizado com sucesso"})
                else:
                    return jsonify({"error": "Produto não encontrado"}), 404
                    
    except Exception as e:
        print(f"Erro ao atualizar status da manutenção: {e}")
        return jsonify({"error": "Erro interno do servidor"}), 500

@app.route("/api/produtos-assistencia")
def api_produtos_assistencia():
    if 'usuario_id' not in session or session.get('admin') != 1:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Buscar produtos enviados para assistência
                cursor.execute("""
                    SELECT p.*, u.nome as usuario_nome
                    FROM produtos p
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE p.destino = 'assistencia' AND p.enviado = 1 AND p.ativo = TRUE
                    ORDER BY p.data_envio DESC
                """)
                
                produtos = []
                for row in cursor.fetchall():
                    produto = dict(row)
                    produto['data_envio_formatada'] = formatar_data_brasileira(produto['data_envio'])
                    produtos.append(produto)
                
                # Calcular estatísticas
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_produtos,
                        SUM(quantidade) as quantidade_total,
                        COUNT(CASE WHEN data_envio::timestamp >= NOW() - INTERVAL '7 days' THEN 1 END) as produtos_recentes,
                        COUNT(DISTINCT usuario_id) as usuarios_ativos
                    FROM produtos 
                    WHERE destino = 'assistencia' AND enviado = 1 AND ativo = TRUE
                """)
                
                stats = cursor.fetchone()
                estatisticas = {
                    'total_produtos': stats[0] or 0,
                    'quantidade_total': stats[1] or 0,
                    'produtos_recentes': stats[2] or 0,
                    'usuarios_ativos': stats[3] or 0
                }
                
                return jsonify({
                    "produtos": produtos,
                    "estatisticas": estatisticas
                })
                
    except psycopg2.Error as e:
        print(f"Erro ao buscar produtos da assistência: {e}")
        return jsonify({"error": "Erro no banco de dados"}), 500

@app.route("/api/export-loja")
def export_loja():
    if 'usuario_id' not in session or session.get('admin') != 1:
        return redirect(url_for("login"))
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT p.ean, p.nome, p.cor, p.voltagem, p.modelo, p.quantidade, 
                           u.nome as usuario, p.data_envio,
                           CASE WHEN p.validado = 1 THEN 'Validado' ELSE 'Pendente' END as status
                    FROM produtos p
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE p.destino = 'loja' AND p.enviado = 1 AND p.ativo = TRUE
                    ORDER BY p.data_envio DESC
                """)
                
                produtos = [dict(row) for row in cursor.fetchall()]
                
                # Criar DataFrame e exportar
                df = pd.DataFrame(produtos)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Produtos Loja', index=False)
                
                output.seek(0)
                
                return send_file(
                    output,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True,
                    download_name=f'produtos_loja_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
                )
                
    except Exception as e:
        print(f"Erro ao exportar produtos da loja: {e}")
        return redirect(url_for("painel_loja"))

@app.route("/api/export-manutencao")
def export_manutencao():
    if 'usuario_id' not in session or session.get('admin') != 1:
        return redirect(url_for("login"))
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT p.ean, p.nome, p.cor, p.voltagem, p.modelo, p.quantidade, 
                           u.nome as usuario, p.data_envio,
                           CASE WHEN p.validado = 1 THEN 'Validado' ELSE 'Pendente' END as status
                    FROM produtos p
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE p.destino = 'manutencao' AND p.enviado = 1 AND p.ativo = TRUE
                    ORDER BY p.data_envio DESC
                """)
                
                produtos = [dict(row) for row in cursor.fetchall()]
                
                # Criar DataFrame e exportar
                df = pd.DataFrame(produtos)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Produtos Manutenção', index=False)
                
                output.seek(0)
                
                return send_file(
                    output,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True,
                    download_name=f'produtos_manutencao_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
                )
                
    except Exception as e:
        print(f"Erro ao exportar produtos da manutenção: {e}")
        return redirect(url_for("painel_manutencao"))

@app.route("/api/export-assistencia")
def export_assistencia():
    if 'usuario_id' not in session or session.get('admin') != 1:
        return redirect(url_for("login"))
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT p.ean, p.nome, p.cor, p.voltagem, p.modelo, p.quantidade, 
                           u.nome as usuario, p.data_envio,
                           CASE WHEN p.validado = 1 THEN 'Validado' ELSE 'Pendente' END as status
                    FROM produtos p
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE p.destino = 'assistencia' AND p.enviado = 1 AND p.ativo = TRUE
                    ORDER BY p.data_envio DESC
                """)
                
                produtos = [dict(row) for row in cursor.fetchall()]
                
                # Criar DataFrame e exportar
                df = pd.DataFrame(produtos)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Produtos Assistência', index=False)
                
                output.seek(0)
                
                return send_file(
                    output,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True,
                    download_name=f'produtos_assistencia_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
                )
                
    except Exception as e:
        print(f"Erro ao exportar produtos da assistência: {e}")
        return redirect(url_for("painel_assistencia"))

@app.route("/api/validar-lista", methods=["POST"])
def validar_lista_api():
    if "usuario_id" not in session or not session.get("admin"):
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        data = request.json
        data_envio = data.get("data_envio")
        nome_usuario = data.get("nome_usuario")
        
        print(f"Recebida solicitação para validar lista: data_envio={data_envio}, nome_usuario={nome_usuario}")
        
        if not data_envio or not nome_usuario:
            return jsonify({"error": "Dados incompletos"}), 400
        
        if validar_lista(data_envio, nome_usuario, session["usuario_id"]):
            return jsonify({"success": True, "message": "Lista validada com sucesso"}), 200
        else:
            return jsonify({"error": "Erro ao validar lista. Verifique se a lista existe e não foi validada anteriormente."}), 500
            
    except Exception as e:
        print(f"Erro ao validar lista: {e}")
        return jsonify({"error": f"Erro ao processar requisição: {str(e)}"}), 500

@app.route("/api/validar-listas-lote", methods=["POST"])
def validar_listas_lote():
    if "usuario_id" not in session or not session.get("admin"):
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        data = request.get_json()
        listas = data.get("listas", [])
        
        if not listas:
            return jsonify({"error": "Nenhuma lista fornecida"}), 400
        
        validadas = 0
        erros = []
        
        # Validar cada lista individualmente
        for lista in listas:
            data_envio = lista.get("data_envio")
            nome_usuario = lista.get("nome_usuario")
            
            if not data_envio or not nome_usuario:
                erros.append(f"Lista com dados incompletos: {lista}")
                continue
            
            try:
                if validar_lista(data_envio, nome_usuario, session["usuario_id"]):
                    validadas += 1
                    print(f"Lista validada: {nome_usuario} - {data_envio}")
                else:
                    erros.append(f"Falha ao validar lista de {nome_usuario} ({data_envio})")
            except Exception as e:
                erros.append(f"Erro ao validar lista de {nome_usuario}: {str(e)}")
        
        # Se pelo menos uma lista foi validada, criar lista unificada
        if validadas > 0:
            # Criar lista unificada com as listas validadas
            try:
                lista_unificada_id = criar_lista_unificada(listas, session["usuario_id"])
                if lista_unificada_id:
                    message = f"{validadas} lista(s) validada(s) e lista unificada criada com sucesso"
                else:
                    message = f"{validadas} lista(s) validada(s) com sucesso, mas houve erro ao criar lista unificada"
            except Exception as e:
                print(f"Erro ao criar lista unificada: {e}")
                message = f"{validadas} lista(s) validada(s) com sucesso, mas houve erro ao criar lista unificada"
            
            if erros:
                message += f". {len(erros)} erro(s) encontrado(s)"
            
            return jsonify({
                "success": True, 
                "message": message,
                "validadas": validadas,
                "lista_unificada_id": lista_unificada_id if 'lista_unificada_id' in locals() else None,
                "erros": erros
            }), 200
        else:
            return jsonify({
                "error": "Nenhuma lista foi validada",
                "erros": erros
            }), 500
            
    except Exception as e:
        print(f"Erro ao validar listas em lote: {e}")
        return jsonify({"error": f"Erro ao processar requisição: {str(e)}"}), 500

@app.route("/api/export", methods=["GET"])
def export_produtos():
    if "usuario_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        produtos = carregar_produtos_usuario(session["usuario_id"], apenas_nao_enviados=True)
        
        if not produtos:
            return jsonify({"error": "Não há produtos para exportar"}), 404
        
        df = pd.DataFrame(produtos)
        
        colunas = ["ean", "nome", "cor", "voltagem", "modelo", "quantidade"]
        df = df[colunas]
        
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Produtos")
        
        output.seek(0)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"produtos_{timestamp}.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        print(f"Erro ao exportar produtos: {e}")
        return jsonify({"error": f"Erro ao exportar produtos: {str(e)}"}), 500

@app.route("/api/export-lista-unificada/<int:lista_id>", methods=["GET"])
def export_lista_unificada(lista_id):
    if "usuario_id" not in session or not session.get("admin"):
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        # Carregar informações da lista
        listas = carregar_listas_unificadas()
        lista_info = None
        for lista in listas:
            if lista["id"] == lista_id:
                lista_info = lista
                break
        
        if not lista_info:
            return jsonify({"error": "Lista unificada não encontrada"}), 404
        
        # Carregar produtos da lista
        produtos = carregar_produtos_lista_unificada(lista_id)
        
        if not produtos:
            return jsonify({"error": "Não há produtos para exportar"}), 404
        
        # Preparar dados para o Excel
        dados_produtos = []
        dados_origem = []
        
        for produto in produtos:
            # Dados principais do produto
            dados_produtos.append({
                'EAN': produto['ean'],
                'Nome': produto['nome'],
                'Cor': produto['cor'],
                'Voltagem': produto['voltagem'],
                'Modelo': produto['modelo'],
                'Quantidade Total': produto['quantidade_total']
            })
            
            # Dados de origem para cada produto
            for origem in produto['listas_origem']:
                dados_origem.append({
                    'EAN': produto['ean'],
                    'Nome do Produto': produto['nome'],
                    'Usuário de Origem': origem['usuario'],
                    'Data de Envio': origem['data_envio'],
                    'Quantidade Contribuída': origem['quantidade']
                })
        
        # Criar DataFrames
        df_produtos = pd.DataFrame(dados_produtos)
        df_origem = pd.DataFrame(dados_origem)
        
        # Criar arquivo Excel
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Aba principal com produtos
            df_produtos.to_excel(writer, index=False, sheet_name="Produtos Unificados")
            
            # Aba com detalhes de origem
            df_origem.to_excel(writer, index=False, sheet_name="Origem das Quantidades")
            
            # Aba com informações da lista
            info_lista = pd.DataFrame([{
                'Nome da Lista': lista_info['nome_lista'],
                'Validador': lista_info['nome_validador'],
                'Data de Criação': lista_info['data_criacao'].strftime("%d/%m/%Y %H:%M:%S") if hasattr(lista_info['data_criacao'], 'strftime') else str(lista_info['data_criacao']),
                'Total de Produtos Únicos': lista_info['total_produtos'],
                'Quantidade Total de Itens': lista_info['total_quantidade']
            }])
            info_lista.to_excel(writer, index=False, sheet_name="Informações da Lista")
        
        output.seek(0)
        
        # Nome do arquivo
        nome_arquivo_limpo = lista_info['nome_lista'].replace('Lista_Unificada_', '').replace('_', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Lista_Unificada_{nome_arquivo_limpo}_{timestamp}.xlsx"
        
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except Exception as e:
        print(f"Erro ao exportar lista unificada: {e}")
        return jsonify({"error": f"Erro ao exportar lista unificada: {str(e)}"}), 500

# Funções para Painel de Desempenho de Usuários

def obter_metricas_usuarios(periodo_dias=None):
    """
    Obtém métricas de desempenho dos usuários.
    Se periodo_dias for especificado, filtra apenas os produtos desse período.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Query base para métricas dos usuários
                if periodo_dias:
                    # Tratamento especial para "último dia" (apenas hoje)
                    if periodo_dias == 1:
                        # Query para apenas hoje (data atual)
                        base_query = """
                        SELECT 
                            u.id,
                            u.nome,
                            COUNT(CASE WHEN DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.id END) as total_produtos,
                            COUNT(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN 1 END) as produtos_enviados,
                            COUNT(CASE WHEN p.validado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN 1 END) as produtos_validados,
                            MAX(CASE WHEN p.enviado = 1 THEN p.data_envio::timestamp ELSE p.timestamp END) as ultima_atividade,
                            MIN(CASE WHEN DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.timestamp END) as primeira_atividade,
                            SUM(CASE WHEN DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as quantidade_total,
                            MIN(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.data_envio::timestamp END) as primeiro_envio,
                            MAX(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.data_envio::timestamp END) as ultimo_envio,
                            SUM(CASE WHEN p.destino = 'mercado_livre' AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_mercado_livre,
                            SUM(CASE WHEN p.destino = 'loja' AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_loja,
                            SUM(CASE WHEN p.destino = 'manutencao' AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_manutencao,
                            SUM(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_geral_enviado
                        FROM usuarios u
                        LEFT JOIN produtos p ON u.id = p.usuario_id
                        WHERE u.admin = 2
                        GROUP BY u.id, u.nome
                        ORDER BY total_produtos DESC
                        """
                        params = []
                    else:
                        # Query com filtro de período - aplica filtro apenas nos cálculos
                        base_query = """
                        SELECT 
                            u.id,
                            u.nome,
                            COUNT(CASE WHEN p.timestamp >= NOW() - INTERVAL %s THEN p.id END) as total_produtos,
                            COUNT(CASE WHEN p.enviado = 1 AND p.timestamp >= NOW() - INTERVAL %s THEN 1 END) as produtos_enviados,
                            COUNT(CASE WHEN p.validado = 1 AND p.timestamp >= NOW() - INTERVAL %s THEN 1 END) as produtos_validados,
                            MAX(CASE WHEN p.enviado = 1 THEN p.data_envio::timestamp ELSE p.timestamp END) as ultima_atividade,
                            MIN(CASE WHEN p.timestamp >= NOW() - INTERVAL %s THEN p.timestamp END) as primeira_atividade,
                            SUM(CASE WHEN p.timestamp >= NOW() - INTERVAL %s THEN p.quantidade ELSE 0 END) as quantidade_total,
                            MIN(CASE WHEN p.enviado = 1 AND p.timestamp >= NOW() - INTERVAL %s THEN p.data_envio END) as primeiro_envio,
                            MAX(CASE WHEN p.enviado = 1 AND p.timestamp >= NOW() - INTERVAL %s THEN p.data_envio END) as ultimo_envio,
                            SUM(CASE WHEN p.destino = 'mercado_livre' AND p.timestamp >= NOW() - INTERVAL %s THEN p.quantidade ELSE 0 END) as total_mercado_livre,
                            SUM(CASE WHEN p.destino = 'loja' AND p.timestamp >= NOW() - INTERVAL %s THEN p.quantidade ELSE 0 END) as total_loja,
                            SUM(CASE WHEN p.destino = 'manutencao' AND p.timestamp >= NOW() - INTERVAL %s THEN p.quantidade ELSE 0 END) as total_manutencao,
                            SUM(CASE WHEN p.enviado = 1 AND p.timestamp >= NOW() - INTERVAL %s THEN p.quantidade ELSE 0 END) as total_geral_enviado
                        FROM usuarios u
                        LEFT JOIN produtos p ON u.id = p.usuario_id
                        WHERE u.admin = 2
                        GROUP BY u.id, u.nome
                        ORDER BY total_produtos DESC
                        """
                        params = [f"{periodo_dias} days"] * 11  # 11 parâmetros para os INTERVAL
                else:
                    # Query sem filtro de período - mostra todos os dados históricos
                    base_query = """
                    SELECT 
                        u.id,
                        u.nome,
                        COUNT(p.id) as total_produtos,
                        COUNT(CASE WHEN p.enviado = 1 THEN 1 END) as produtos_enviados,
                        COUNT(CASE WHEN p.validado = 1 THEN 1 END) as produtos_validados,
                        MAX(CASE WHEN p.enviado = 1 THEN p.data_envio::timestamp ELSE p.timestamp END) as ultima_atividade,
                        MIN(p.timestamp) as primeira_atividade,
                        SUM(p.quantidade) as quantidade_total,
                        MIN(CASE WHEN p.enviado = 1 THEN p.data_envio END) as primeiro_envio,
                        MAX(CASE WHEN p.enviado = 1 THEN p.data_envio END) as ultimo_envio,
                        SUM(CASE WHEN p.destino = 'mercado_livre' THEN p.quantidade ELSE 0 END) as total_mercado_livre,
                        SUM(CASE WHEN p.destino = 'loja' THEN p.quantidade ELSE 0 END) as total_loja,
                        SUM(CASE WHEN p.destino = 'manutencao' THEN p.quantidade ELSE 0 END) as total_manutencao,
                        SUM(CASE WHEN p.enviado = 1 THEN p.quantidade ELSE 0 END) as total_geral_enviado
                    FROM usuarios u
                    LEFT JOIN produtos p ON u.id = p.usuario_id
                    WHERE u.admin = 2
                    GROUP BY u.id, u.nome
                    ORDER BY total_produtos DESC
                    """
                    params = []
                
                cursor.execute(base_query, params)
                usuarios = []
                
                for row in cursor.fetchall():
                    # Calcular Taxa de Envio: Produtos Enviados / Total de Horas de Envio Ativo
                    taxa_envio = 0
                    if row['produtos_enviados'] and row['primeiro_envio'] and row['ultimo_envio']:
                        primeiro_envio = row['primeiro_envio']
                        ultimo_envio = row['ultimo_envio']
                        
                        # Garantir que as datas são objetos datetime
                        if isinstance(primeiro_envio, str):
                            from datetime import datetime
                            primeiro_envio = datetime.fromisoformat(primeiro_envio.replace('Z', '+00:00'))
                        if isinstance(ultimo_envio, str):
                            from datetime import datetime
                            ultimo_envio = datetime.fromisoformat(ultimo_envio.replace('Z', '+00:00'))
                        
                        # Calcular diferença em horas
                        if primeiro_envio == ultimo_envio:
                            # Se só há um envio, considerar 1 hora
                            horas_ativo = 1
                        else:
                            try:
                                diferenca = ultimo_envio - primeiro_envio
                                horas_ativo = diferenca.total_seconds() / 3600  # Converter para horas
                                if horas_ativo < 1:
                                    horas_ativo = 1  # Mínimo de 1 hora
                            except (TypeError, AttributeError):
                                # Em caso de erro, usar 1 hora como padrão
                                horas_ativo = 1
                        
                        taxa_envio = row['produtos_enviados'] / horas_ativo
                    
                    usuarios.append({
                        'id': row['id'],
                        'nome': row['nome'],
                        'total_produtos': row['total_produtos'] or 0,
                        'produtos_enviados': row['produtos_enviados'] or 0,
                        'produtos_validados': row['produtos_validados'] or 0,
                        'quantidade_total': row['quantidade_total'] or 0,
                        'ultima_atividade': row['ultima_atividade'],
                        'primeira_atividade': row['primeira_atividade'],
                        'taxa_envio': round(taxa_envio, 2),  # Taxa de envio calculada (produtos/hora)
                        'total_mercado_livre': row['total_mercado_livre'] or 0,
                        'total_loja': row['total_loja'] or 0,
                        'total_manutencao': row['total_manutencao'] or 0,
                        'total_geral_enviado': row['total_geral_enviado'] or 0
                    })
                
                return usuarios
                
    except Exception as e:
        print(f"Erro ao obter métricas dos usuários: {e}")
        return []

def obter_atividade_periodo(usuario_id=None, dias=7):
    """
    Obtém atividade dos usuários por período (últimos X dias).
    Se usuario_id for especificado, filtra apenas esse usuário.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                base_query = """
                SELECT 
                    u.nome,
                    DATE(p.timestamp - INTERVAL '3 hours') as data,
                    COUNT(p.id) as produtos_dia,
                    SUM(p.quantidade) as quantidade_dia
                FROM usuarios u
                LEFT JOIN produtos p ON u.id = p.usuario_id
                WHERE p.timestamp >= NOW() - INTERVAL %s
                    AND u.admin = 2
                """
                
                params = [f"{dias} days"]
                
                if usuario_id:
                    base_query += " AND u.id = %s"
                    params.append(usuario_id)
                
                base_query += """
                GROUP BY u.nome, DATE(p.timestamp - INTERVAL '3 hours')
                ORDER BY data DESC, u.nome
                """
                
                cursor.execute(base_query, params)
                atividades = []
                
                for row in cursor.fetchall():
                    atividades.append({
                        'nome_usuario': row['nome'],
                        'data': row['data'],
                        'produtos_dia': row['produtos_dia'] or 0,
                        'quantidade_dia': row['quantidade_dia'] or 0
                    })
                
                return atividades
                
    except Exception as e:
        print(f"Erro ao obter atividade por período: {e}")
        return []

def obter_estatisticas_gerais(periodo_dias=None):
    """
    Obtém estatísticas gerais do sistema.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Query para estatísticas gerais
                base_query = """
                SELECT 
                    COUNT(DISTINCT u.id) as total_usuarios_ativos,
                    SUM(CASE WHEN p.destino = 'mercado_livre' THEN p.quantidade ELSE 0 END) as total_produtos,
                    SUM(CASE WHEN p.destino = 'loja' AND p.enviado = 1 THEN p.quantidade ELSE 0 END) as total_enviados,
                    SUM(CASE WHEN p.destino = 'manutencao' AND p.enviado = 1 THEN p.quantidade ELSE 0 END) as total_validados,
                    SUM(p.quantidade) as quantidade_total
                FROM usuarios u
                LEFT JOIN produtos p ON u.id = p.usuario_id
                WHERE u.admin = 2
                """
                
                params = []
                
                if periodo_dias:
                    base_query += " AND p.timestamp >= NOW() - INTERVAL %s"
                    params.append(f"{periodo_dias} days")
                
                cursor.execute(base_query, params)
                resultado = cursor.fetchone()
                
                if resultado:
                    return {
                        'total_usuarios_ativos': resultado['total_usuarios_ativos'] or 0,
                        'total_produtos': resultado['total_produtos'] or 0,
                        'total_enviados': resultado['total_enviados'] or 0,
                        'total_validados': resultado['total_validados'] or 0,
                        'quantidade_total': resultado['quantidade_total'] or 0
                    }
                
                return {
                    'total_usuarios_ativos': 0,
                    'total_produtos': 0,
                    'total_enviados': 0,
                    'total_validados': 0,
                    'quantidade_total': 0
                }
                
    except Exception as e:
        print(f"Erro ao obter estatísticas gerais: {e}")
        return {
            'total_usuarios_ativos': 0,
            'total_produtos': 0,
            'total_enviados': 0,
            'total_validados': 0,
            'quantidade_total': 0
        }

def obter_listas_aprovadas_por_responsavel(periodo_dias=None):
    """
    Obtém a quantidade de listas aprovadas por cada responsável.
    Se periodo_dias for especificado, filtra apenas as aprovações desse período.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Query para contar listas aprovadas por responsável
                if periodo_dias:
                    # Tratamento especial para "último dia" (apenas hoje)
                    if periodo_dias == 1:
                        # Query para apenas hoje (data atual)
                        base_query = """
                        SELECT 
                            u.id,
                            u.nome,
                            COUNT(CASE WHEN DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.id END) as total_produtos,
                            COUNT(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN 1 END) as produtos_enviados,
                            COUNT(CASE WHEN p.validado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN 1 END) as produtos_validados,
                            MAX(CASE WHEN p.enviado = 1 THEN p.data_envio::timestamp ELSE p.timestamp END) as ultima_atividade,
                            MIN(CASE WHEN DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.timestamp END) as primeira_atividade,
                            SUM(CASE WHEN DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as quantidade_total,
                            MIN(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.data_envio::timestamp END) as primeiro_envio,
                            MAX(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.data_envio::timestamp END) as ultimo_envio,
                            SUM(CASE WHEN p.destino = 'mercado_livre' AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_mercado_livre,
                            SUM(CASE WHEN p.destino = 'loja' AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_loja,
                            SUM(CASE WHEN p.destino = 'manutencao' AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_manutencao,
                            SUM(CASE WHEN p.enviado = 1 AND DATE(p.timestamp - INTERVAL '3 hours') = CURRENT_DATE THEN p.quantidade ELSE 0 END) as total_geral_enviado
                        FROM usuarios u
                        LEFT JOIN produtos p ON u.id = p.usuario_id
                        WHERE u.admin = 2
                        GROUP BY u.id, u.nome
                        ORDER BY total_produtos DESC
                        """
                        params = []
                    else:
                        # Query com filtro de período - aplica filtro apenas nos cálculos
                        base_query = """
                    SELECT 
                        r.nome as responsavel_nome,
                        COUNT(CASE WHEN p.data_envio::timestamp >= NOW() - INTERVAL %s THEN 
                              CONCAT(CAST(p.data_envio AS TEXT), '-', CAST(p.usuario_id AS TEXT)) END) as listas_aprovadas
                    FROM responsaveis r
                    LEFT JOIN produtos p ON r.id = p.responsavel_id
                    GROUP BY r.id, r.nome
                    ORDER BY r.nome
                    """
                    params = [f"{periodo_dias} days"]
                else:
                    # Query sem filtro de período - mostra todos os dados históricos
                    base_query = """
                    SELECT 
                        r.nome as responsavel_nome,
                        COUNT(DISTINCT CONCAT(CAST(p.data_envio AS TEXT), '-', CAST(p.usuario_id AS TEXT))) as listas_aprovadas
                    FROM responsaveis r
                    LEFT JOIN produtos p ON r.id = p.responsavel_id
                    WHERE p.responsavel_id IS NOT NULL
                    GROUP BY r.id, r.nome
                    ORDER BY r.nome
                    """
                    params = []
                
                cursor.execute(base_query, params)
                responsaveis_stats = []
                
                for row in cursor.fetchall():
                    responsaveis_stats.append({
                        'nome': row['responsavel_nome'],
                        'listas_aprovadas': row['listas_aprovadas'] or 0
                    })
                
                # Garantir que todos os responsáveis apareçam, mesmo sem aprovações
                responsaveis_fixos = ["Liliane", "Rogerio", "Celso", "Marcos"]
                responsaveis_encontrados = [r['nome'] for r in responsaveis_stats]
                
                for responsavel in responsaveis_fixos:
                    if responsavel not in responsaveis_encontrados:
                        responsaveis_stats.append({
                            'nome': responsavel,
                            'listas_aprovadas': 0
                        })
                
                # Ordenar por nome
                responsaveis_stats.sort(key=lambda x: x['nome'])
                
                return responsaveis_stats
                
    except Exception as e:
        print(f"Erro ao obter listas aprovadas por responsável: {e}")
        return [
            {'nome': 'Liliane', 'listas_aprovadas': 0},
            {'nome': 'Rogerio', 'listas_aprovadas': 0},
            {'nome': 'Celso', 'listas_aprovadas': 0},
            {'nome': 'Marcos', 'listas_aprovadas': 0}
        ]

def obter_metricas_usuarios_por_periodo(data_inicio, data_fim):
    """
    Obtém métricas de desempenho dos usuários para um período específico.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Converter datas para timezone local (não UTC)
                from datetime import datetime, timezone
                import pytz
                
                # Assumir que as datas de entrada são em timezone local (Brasil)
                brasil_tz = pytz.timezone('America/Sao_Paulo')
                
                # Se as datas não têm timezone, assumir que são em timezone local
                if data_inicio.tzinfo is None:
                    data_inicio = brasil_tz.localize(data_inicio)
                if data_fim.tzinfo is None:
                    data_fim = brasil_tz.localize(data_fim)
                
                # CORREÇÃO: Usar apenas data sem hora para evitar problemas de timezone
                data_inicio_local = data_inicio.strftime('%Y-%m-%d')
                data_fim_local = data_fim.strftime('%Y-%m-%d')
                
                base_query = """
                SELECT 
                    u.id,
                    u.nome,
                    COUNT(p.id) as total_produtos,
                    COUNT(CASE WHEN p.enviado = 1 THEN 1 END) as produtos_enviados,
                    COUNT(CASE WHEN p.validado = 1 THEN 1 END) as produtos_validados,
                    MAX(CASE WHEN p.enviado = 1 THEN p.data_envio::timestamp ELSE p.timestamp END) as ultima_atividade,
                    MIN(p.timestamp) as primeira_atividade,
                    SUM(p.quantidade) as quantidade_total,
                    MIN(CASE WHEN p.enviado = 1 THEN p.data_envio END) as primeiro_envio,
                    MAX(CASE WHEN p.enviado = 1 THEN p.data_envio END) as ultimo_envio,
                    SUM(CASE WHEN p.destino = 'mercado_livre' THEN p.quantidade ELSE 0 END) as total_mercado_livre,
                    SUM(CASE WHEN p.destino = 'loja' THEN p.quantidade ELSE 0 END) as total_loja,
                    SUM(CASE WHEN p.destino = 'manutencao' THEN p.quantidade ELSE 0 END) as total_manutencao,
                    SUM(CASE WHEN p.enviado = 1 THEN p.quantidade ELSE 0 END) as total_geral_enviado
                FROM usuarios u
                LEFT JOIN produtos p ON u.id = p.usuario_id
                WHERE u.admin = 2 AND DATE(p.timestamp - INTERVAL '3 hours') >= %s::date AND DATE(p.timestamp - INTERVAL '3 hours') <= %s::date
                GROUP BY u.id, u.nome
                ORDER BY total_produtos DESC
                """
                
                cursor.execute(base_query, [data_inicio_local, data_fim_local])
                usuarios = []
                
                for row in cursor.fetchall():
                    # Calcular Taxa de Envio
                    taxa_envio = 0
                    if row['produtos_enviados'] and row['primeiro_envio'] and row['ultimo_envio']:
                        primeiro_envio = row['primeiro_envio']
                        ultimo_envio = row['ultimo_envio']
                        
                        if isinstance(primeiro_envio, str):
                            from datetime import datetime
                            primeiro_envio = datetime.fromisoformat(primeiro_envio.replace('Z', '+00:00'))
                        if isinstance(ultimo_envio, str):
                            from datetime import datetime
                            ultimo_envio = datetime.fromisoformat(ultimo_envio.replace('Z', '+00:00'))
                        
                        if primeiro_envio == ultimo_envio:
                            horas_ativo = 1
                        else:
                            try:
                                diferenca = ultimo_envio - primeiro_envio
                                horas_ativo = diferenca.total_seconds() / 3600
                                if horas_ativo < 1:
                                    horas_ativo = 1
                            except (TypeError, AttributeError):
                                horas_ativo = 1
                        
                        taxa_envio = row['produtos_enviados'] / horas_ativo
                    
                    usuarios.append({
                        'id': row['id'],
                        'nome': row['nome'],
                        'total_produtos': row['total_produtos'] or 0,
                        'produtos_enviados': row['produtos_enviados'] or 0,
                        'produtos_validados': row['produtos_validados'] or 0,
                        'quantidade_total': row['quantidade_total'] or 0,
                        'ultima_atividade': row['ultima_atividade'],
                        'primeira_atividade': row['primeira_atividade'],
                        'taxa_envio': round(taxa_envio, 2),
                        'total_mercado_livre': row['total_mercado_livre'] or 0,
                        'total_loja': row['total_loja'] or 0,
                        'total_manutencao': row['total_manutencao'] or 0,
                        'total_geral_enviado': row['total_geral_enviado'] or 0
                    })
                
                return usuarios
                
    except Exception as e:
        print(f"Erro ao obter métricas dos usuários por período: {e}")
        return []

def obter_estatisticas_gerais_por_periodo(data_inicio, data_fim):
    """
    Obtém estatísticas gerais do sistema para um período específico.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Converter datas para timezone local (não UTC)
                from datetime import datetime, timezone
                import pytz
                
                # Assumir que as datas de entrada são em timezone local (Brasil)
                brasil_tz = pytz.timezone('America/Sao_Paulo')
                
                # Se as datas não têm timezone, assumir que são em timezone local
                if data_inicio.tzinfo is None:
                    data_inicio = brasil_tz.localize(data_inicio)
                if data_fim.tzinfo is None:
                    data_fim = brasil_tz.localize(data_fim)
                
                # CORREÇÃO: Usar apenas data sem hora para evitar problemas de timezone
                data_inicio_local = data_inicio.strftime('%Y-%m-%d')
                data_fim_local = data_fim.strftime('%Y-%m-%d')
                
                base_query = """
                SELECT 
                    COUNT(DISTINCT u.id) as total_usuarios_ativos,
                    SUM(CASE WHEN p.destino = 'mercado_livre' THEN p.quantidade ELSE 0 END) as total_produtos,
                    SUM(CASE WHEN p.destino = 'loja' AND p.enviado = 1 THEN p.quantidade ELSE 0 END) as total_enviados,
                    SUM(CASE WHEN p.destino = 'manutencao' AND p.enviado = 1 THEN p.quantidade ELSE 0 END) as total_validados,
                    SUM(p.quantidade) as quantidade_total
                FROM usuarios u
                LEFT JOIN produtos p ON u.id = p.usuario_id
                WHERE u.admin = 2 AND DATE(p.timestamp - INTERVAL '3 hours') >= %s::date AND DATE(p.timestamp - INTERVAL '3 hours') <= %s::date
                """
                
                cursor.execute(base_query, [data_inicio_local, data_fim_local])
                resultado = cursor.fetchone()
                
                if resultado:
                    return {
                        'total_usuarios_ativos': resultado['total_usuarios_ativos'] or 0,
                        'total_produtos': resultado['total_produtos'] or 0,
                        'total_enviados': resultado['total_enviados'] or 0,
                        'total_validados': resultado['total_validados'] or 0,
                        'quantidade_total': resultado['quantidade_total'] or 0
                    }
                
                return {
                    'total_usuarios_ativos': 0,
                    'total_produtos': 0,
                    'total_enviados': 0,
                    'total_validados': 0,
                    'quantidade_total': 0
                }
                
    except Exception as e:
        print(f"Erro ao obter estatísticas gerais por período: {e}")
        return {
            'total_usuarios_ativos': 0,
            'total_produtos': 0,
            'total_enviados': 0,
            'total_validados': 0,
            'quantidade_total': 0
        }

def obter_atividade_por_periodo_customizado(data_inicio, data_fim):
    """
    Obtém atividade dos usuários para um período customizado.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Converter datas para timezone local (não UTC)
                from datetime import datetime, timezone
                import pytz
                
                # Assumir que as datas de entrada são em timezone local (Brasil)
                brasil_tz = pytz.timezone('America/Sao_Paulo')
                
                # Se as datas não têm timezone, assumir que são em timezone local
                if data_inicio.tzinfo is None:
                    data_inicio = brasil_tz.localize(data_inicio)
                if data_fim.tzinfo is None:
                    data_fim = brasil_tz.localize(data_fim)
                
                # CORREÇÃO: Usar apenas data sem hora para evitar problemas de timezone
                data_inicio_local = data_inicio.strftime('%Y-%m-%d')
                data_fim_local = data_fim.strftime('%Y-%m-%d')
                
                base_query = """
                SELECT 
                    u.nome,
                    DATE(p.timestamp - INTERVAL '3 hours') as data,
                    COUNT(p.id) as produtos_dia,
                    SUM(p.quantidade) as quantidade_dia
                FROM usuarios u
                LEFT JOIN produtos p ON u.id = p.usuario_id
                WHERE DATE(p.timestamp - INTERVAL '3 hours') >= %s::date AND DATE(p.timestamp - INTERVAL '3 hours') <= %s::date AND u.admin = 2
                GROUP BY u.nome, DATE(p.timestamp - INTERVAL '3 hours')
                ORDER BY data DESC, u.nome
                """
                
                cursor.execute(base_query, [data_inicio_local, data_fim_local])
                atividades = []
                
                for row in cursor.fetchall():
                    atividades.append({
                        'nome_usuario': row['nome'],
                        'data': row['data'],
                        'produtos_dia': row['produtos_dia'] or 0,
                        'quantidade_dia': row['quantidade_dia'] or 0
                    })
                
                return atividades
                
    except Exception as e:
        print(f"Erro ao obter atividade por período customizado: {e}")
        return []

def obter_listas_aprovadas_por_periodo(data_inicio, data_fim):
    """
    Obtém listas aprovadas por responsável para um período específico.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Converter datas para timezone local (não UTC)
                from datetime import datetime, timezone
                import pytz
                
                # Assumir que as datas de entrada são em timezone local (Brasil)
                brasil_tz = pytz.timezone('America/Sao_Paulo')
                
                # Se as datas não têm timezone, assumir que são em timezone local
                if data_inicio.tzinfo is None:
                    data_inicio = brasil_tz.localize(data_inicio)
                if data_fim.tzinfo is None:
                    data_fim = brasil_tz.localize(data_fim)
                
                # CORREÇÃO: Usar apenas data sem hora para evitar problemas de timezone
                data_inicio_local = data_inicio.strftime('%Y-%m-%d')
                data_fim_local = data_fim.strftime('%Y-%m-%d')
                
                base_query = """
                SELECT 
                    r.nome as responsavel_nome,
                    COUNT(CASE WHEN DATE(p.data_envio::timestamp - INTERVAL '3 hours') >= %s::date AND DATE(p.data_envio::timestamp - INTERVAL '3 hours') <= %s::date THEN 
                          CONCAT(CAST(p.data_envio AS TEXT), '-', CAST(p.usuario_id AS TEXT)) END) as listas_aprovadas
                FROM responsaveis r
                LEFT JOIN produtos p ON r.id = p.responsavel_id
                GROUP BY r.id, r.nome
                ORDER BY r.nome
                """
                
                cursor.execute(base_query, [data_inicio_local, data_fim_local])
                responsaveis_stats = []
                
                for row in cursor.fetchall():
                    responsaveis_stats.append({
                        'nome': row['responsavel_nome'],
                        'listas_aprovadas': row['listas_aprovadas'] or 0
                    })
                
                # Garantir que todos os responsáveis apareçam
                responsaveis_fixos = ["Liliane", "Rogerio", "Celso", "Marcos"]
                responsaveis_encontrados = [r['nome'] for r in responsaveis_stats]
                
                for responsavel in responsaveis_fixos:
                    if responsavel not in responsaveis_encontrados:
                        responsaveis_stats.append({
                            'nome': responsavel,
                            'listas_aprovadas': 0
                        })
                
                responsaveis_stats.sort(key=lambda x: x['nome'])
                return responsaveis_stats
                
    except Exception as e:
        print(f"Erro ao obter listas aprovadas por período: {e}")
        return [
            {'nome': 'Liliane', 'listas_aprovadas': 0},
            {'nome': 'Rogerio', 'listas_aprovadas': 0},
            {'nome': 'Celso', 'listas_aprovadas': 0},
            {'nome': 'Marcos', 'listas_aprovadas': 0}
        ]

def obter_produtos_detalhados_por_periodo(data_inicio, data_fim):
    """
    Obtém produtos detalhados das listas aprovadas para um período específico.
    Retorna cada produto individual com quantidade, responsável e data/hora de aprovação.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Converter datas para timezone local (não UTC)
                from datetime import datetime, timezone
                import pytz
                
                # Assumir que as datas de entrada são em timezone local (Brasil)
                brasil_tz = pytz.timezone('America/Sao_Paulo')
                
                # Se as datas não têm timezone, assumir que são em timezone local
                if data_inicio.tzinfo is None:
                    data_inicio = brasil_tz.localize(data_inicio)
                if data_fim.tzinfo is None:
                    data_fim = brasil_tz.localize(data_fim)
                
                # CORREÇÃO: Usar apenas data sem hora para evitar problemas de timezone
                data_inicio_local = data_inicio.strftime('%Y-%m-%d')
                data_fim_local = data_fim.strftime('%Y-%m-%d')
                
                base_query = """
                SELECT 
                    p.ean,
                    p.nome,
                    p.cor,
                    p.voltagem,
                    p.modelo,
                    SUM(p.quantidade) as quantidade_total,
                    r.nome as responsavel_nome,
                    p.data_envio,
                    u.nome as usuario_nome,
                    COUNT(p.id) as total_registros
                FROM produtos p
                LEFT JOIN responsaveis r ON p.responsavel_id = r.id
                LEFT JOIN usuarios u ON p.usuario_id = u.id
                WHERE p.responsavel_id IS NOT NULL 
                AND DATE(p.data_envio::timestamp - INTERVAL '3 hours') >= %s::date AND DATE(p.data_envio::timestamp - INTERVAL '3 hours') <= %s::date
                GROUP BY p.ean, p.nome, p.cor, p.voltagem, p.modelo, r.nome, p.data_envio, u.nome
                ORDER BY p.data_envio DESC, p.nome
                """
                
                cursor.execute(base_query, [data_inicio_local, data_fim_local])
                produtos_detalhados = []
                
                for row in cursor.fetchall():
                    # Converter data_envio de volta para timezone local para exibição
                    data_envio_local = row['data_envio']
                    try:
                        if data_envio_local:
                            # Se é string, tentar converter para datetime
                            if isinstance(data_envio_local, str):
                                try:
                                    data_envio_local = datetime.fromisoformat(data_envio_local.replace('Z', '+00:00'))
                                except ValueError:
                                    # Se falhar, usar como string mesmo
                                    data_envio_formatada = data_envio_local
                                    continue
                            
                            # Se é datetime, processar timezone
                            if hasattr(data_envio_local, 'tzinfo'):
                                if data_envio_local.tzinfo:
                                    data_envio_local = data_envio_local.astimezone(brasil_tz)
                                else:
                                    # Se não tem timezone, assumir que é UTC e converter
                                    data_envio_local = pytz.UTC.localize(data_envio_local).astimezone(brasil_tz)
                                data_envio_formatada = data_envio_local.strftime('%d/%m/%Y %H:%M')
                            else:
                                data_envio_formatada = str(data_envio_local)
                        else:
                            data_envio_formatada = 'N/A'
                    except Exception as e:
                        # Em caso de erro, usar string simples
                        data_envio_formatada = str(row['data_envio']) if row['data_envio'] else 'N/A'
                    
                    produtos_detalhados.append({
                        'ean': row['ean'] or 'N/A',
                        'nome': row['nome'] or 'N/A',
                        'cor': row['cor'] or 'N/A',
                        'voltagem': row['voltagem'] or 'N/A',
                        'modelo': row['modelo'] or 'N/A',
                        'quantidade_total': row['quantidade_total'] or 0,
                        'responsavel_nome': row['responsavel_nome'] or 'N/A',
                        'data_envio': data_envio_formatada,
                        'usuario_nome': row['usuario_nome'] or 'N/A',
                        'total_registros': row['total_registros'] or 0
                    })
                
                return produtos_detalhados
                
    except Exception as e:
        print(f"Erro ao obter produtos detalhados por período: {e}")
        return []

# Rotas para Painel de Desempenho

@app.route("/painel_desempenho")
def painel_desempenho():
    """Rota principal do painel de desempenho de usuários"""
    if "usuario_id" not in session or not session.get("admin"):
        return redirect(url_for("login"))
    
    # Obter parâmetros de filtro
    periodo_dias = request.args.get("periodo", 7, type=str)
    usuario_filtro = request.args.get("usuario", "", type=str)
    data_inicio = request.args.get("data_inicio", "", type=str)
    data_fim = request.args.get("data_fim", "", type=str)
    
    # Verificar se é filtro customizado
    filtro_customizado = periodo_dias == "custom"
    
    if not filtro_customizado:
        # Converter período para int se não for customizado
        try:
            periodo_dias = int(periodo_dias)
            # Limitar período máximo a 30 dias
            if periodo_dias > 30:
                periodo_dias = 30
        except ValueError:
            periodo_dias = 7
        
        # Obter dados usando período em dias
        metricas_usuarios = obter_metricas_usuarios(periodo_dias)
        estatisticas_gerais = obter_estatisticas_gerais(periodo_dias)
        atividade_periodo = obter_atividade_periodo(dias=periodo_dias)
        listas_aprovadas_responsavel = obter_listas_aprovadas_por_responsavel(periodo_dias)
        produtos_detalhados = []
    else:
        # Usar filtro customizado por data
        if data_inicio and data_fim:
            try:
                from datetime import datetime, time
                
                # Converter datas do formato YYYY-MM-DD para datetime
                # Data início: 00:00:00 do dia
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
                data_inicio_obj = datetime.combine(data_inicio_obj.date(), time.min)
                
                # Data fim: 23:59:59 do dia
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
                data_fim_obj = datetime.combine(data_fim_obj.date(), time.max)
                
                # Obter dados usando datas específicas
                metricas_usuarios = obter_metricas_usuarios_por_periodo(data_inicio_obj, data_fim_obj)
                estatisticas_gerais = obter_estatisticas_gerais_por_periodo(data_inicio_obj, data_fim_obj)
                atividade_periodo = obter_atividade_por_periodo_customizado(data_inicio_obj, data_fim_obj)
                listas_aprovadas_responsavel = obter_listas_aprovadas_por_periodo(data_inicio_obj, data_fim_obj)
                produtos_detalhados = []
            except ValueError:
                # Em caso de erro nas datas, usar período padrão
                periodo_dias = 7
                filtro_customizado = False
                data_inicio = ""
                data_fim = ""
                metricas_usuarios = obter_metricas_usuarios(periodo_dias)
                estatisticas_gerais = obter_estatisticas_gerais(periodo_dias)
                atividade_periodo = obter_atividade_periodo(dias=periodo_dias)
                listas_aprovadas_responsavel = obter_listas_aprovadas_por_responsavel(periodo_dias)
                produtos_detalhados = []
        else:
            # Se não há datas, usar período padrão
            periodo_dias = 7
            filtro_customizado = False
            metricas_usuarios = obter_metricas_usuarios(periodo_dias)
            estatisticas_gerais = obter_estatisticas_gerais(periodo_dias)
            atividade_periodo = obter_atividade_periodo(dias=periodo_dias)
            listas_aprovadas_responsavel = obter_listas_aprovadas_por_responsavel(periodo_dias)
            produtos_detalhados = []
    
    # Filtrar por usuário se especificado
    if usuario_filtro:
        metricas_usuarios = [u for u in metricas_usuarios if usuario_filtro.lower() in u['nome'].lower()]
    
    return render_template("desempenho_usuarios.html", 
                         metricas_usuarios=metricas_usuarios,
                         estatisticas_gerais=estatisticas_gerais,
                         atividade_periodo=atividade_periodo,
                         listas_aprovadas_responsavel=listas_aprovadas_responsavel,
                         produtos_detalhados=produtos_detalhados,
                         periodo_dias=periodo_dias,
                         usuario_filtro=usuario_filtro,
                         filtro_customizado=filtro_customizado,
                         data_inicio=data_inicio,
                         data_fim=data_fim)

@app.route("/admin/desempenho/api/dados")
def api_dados_desempenho():
    """API para obter dados de desempenho via AJAX"""
    if "usuario_id" not in session or not session.get("admin"):
        return jsonify({"error": "Acesso negado"}), 403
    
    periodo_dias = request.args.get("periodo", 7, type=int)
    usuario_id = request.args.get("usuario_id", None, type=int)
    
    # Limitar período máximo a 30 dias
    if periodo_dias > 30:
        periodo_dias = 30
    
    try:
        metricas = obter_metricas_usuarios(periodo_dias)
        estatisticas = obter_estatisticas_gerais(periodo_dias)
        atividade = obter_atividade_periodo(usuario_id, periodo_dias)
        
        return jsonify({
            "success": True,
            "metricas_usuarios": metricas,
            "estatisticas_gerais": estatisticas,
            "atividade_periodo": atividade
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/admin/desempenho/api/grafico")
def api_grafico_desempenho():
    """API para dados dos gráficos"""
    if "usuario_id" not in session or not session.get("admin"):
        return jsonify({"error": "Acesso negado"}), 403
    
    periodo_dias = request.args.get("periodo", 7, type=str)
    tipo_grafico = request.args.get("tipo", "usuarios", type=str)
    data_inicio = request.args.get("data_inicio", "", type=str)
    data_fim = request.args.get("data_fim", "", type=str)
    
    # Verificar se é filtro customizado
    filtro_customizado = periodo_dias == "custom"
    
    try:
        if not filtro_customizado:
            # Converter período para int se não for customizado
            try:
                periodo_dias = int(periodo_dias)
                # Limitar período máximo a 30 dias
                if periodo_dias > 30:
                    periodo_dias = 30
            except ValueError:
                periodo_dias = 7
            
            # Usar funções padrão
            if tipo_grafico == "usuarios":
                metricas = obter_metricas_usuarios(periodo_dias)
            elif tipo_grafico == "atividade":
                atividade = obter_atividade_periodo(dias=periodo_dias)
        else:
            # Usar filtro customizado por data/hora
            if data_inicio and data_fim:
                try:
                    from datetime import datetime
                    # Conversão robusta de datas
                    if 'T' in data_inicio:
                        data_inicio_obj = datetime.fromisoformat(data_inicio)
                    else:
                        data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d %H:%M')
                    
                    if 'T' in data_fim:
                        data_fim_obj = datetime.fromisoformat(data_fim)
                    else:
                        data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d %H:%M')
                    
                    # Usar funções de período customizado
                    if tipo_grafico == "usuarios":
                        metricas = obter_metricas_usuarios_por_periodo(data_inicio_obj, data_fim_obj)
                    elif tipo_grafico == "atividade":
                        atividade = obter_atividade_por_periodo_customizado(data_inicio_obj, data_fim_obj)
                except ValueError:
                    # Em caso de erro nas datas, usar período padrão
                    periodo_dias = 7
                    if tipo_grafico == "usuarios":
                        metricas = obter_metricas_usuarios(periodo_dias)
                    elif tipo_grafico == "atividade":
                        atividade = obter_atividade_periodo(dias=periodo_dias)
            else:
                # Se não há datas, usar período padrão
                periodo_dias = 7
                if tipo_grafico == "usuarios":
                    metricas = obter_metricas_usuarios(periodo_dias)
                elif tipo_grafico == "atividade":
                    atividade = obter_atividade_periodo(dias=periodo_dias)
        
        if tipo_grafico == "usuarios":
            # Gráfico de barras por usuário
            dados = {
                "labels": [u['nome'] for u in metricas[:10]],  # Top 10 usuários
                "datasets": [
                    {
                        "label": "Produtos Adicionados",
                        "data": [u['total_produtos'] for u in metricas[:10]],
                        "backgroundColor": "rgba(54, 162, 235, 0.6)"
                    },
                    {
                        "label": "Produtos Enviados",
                        "data": [u['produtos_enviados'] for u in metricas[:10]],
                        "backgroundColor": "rgba(255, 206, 86, 0.6)"
                    }
                ]
            }
        elif tipo_grafico == "atividade":
            # Gráfico de linha temporal
            # Agrupar por data
            atividade_por_data = {}
            for item in atividade:
                data_str = item['data'].strftime("%d/%m") if item['data'] else "Sem data"
                if data_str not in atividade_por_data:
                    atividade_por_data[data_str] = 0
                atividade_por_data[data_str] += item['produtos_dia']
            
            dados = {
                "labels": list(atividade_por_data.keys()),
                "datasets": [
                    {
                        "label": "Produtos por Dia",
                        "data": list(atividade_por_data.values()),
                        "borderColor": "rgba(75, 192, 192, 1)",
                        "backgroundColor": "rgba(75, 192, 192, 0.2)",
                        "fill": True
                    }
                ]
            }
        else:
            return jsonify({"error": "Tipo de gráfico inválido"}), 400
        
        return jsonify({
            "success": True,
            "dados": dados
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# API para entrada de produto na rua - VERSÃO SIMPLIFICADA
@app.route("/api/entrada_produto_rua", methods=["POST"])
def api_entrada_produto_rua():
    """
    API SIMPLIFICADA para adicionar produto à rua
    Busca produto no banco local e adiciona à rua selecionada
    """
    print(f"[DEBUG] api_entrada_produto_rua CHAMADA!")
    print(f"[DEBUG] Método: {request.method}")
    print(f"[DEBUG] URL: {request.url}")
    print(f"[DEBUG] Headers: {dict(request.headers)}")
    
    if "usuario_id" not in session:
        print(f"[DEBUG] ERRO: Usuário não autorizado - session: {dict(session)}")
        return jsonify({"error": "Não autorizado"}), 401
    
    print(f"[DEBUG] Usuário autorizado: {session.get('usuario_id')}")
    
    try:
        data = request.json
        print(f"[DEBUG] Dados recebidos: {data}")
        ean = data.get("ean")
        rua_id = data.get("rua_id")
        quantidade = data.get("quantidade", 1)
        
        if not ean or not rua_id:
            return jsonify({"error": "EAN e rua_id são obrigatórios"}), 400
        
        if quantidade <= 0:
            return jsonify({"error": "Quantidade deve ser maior que zero"}), 400
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                
                # 1. Verificar se a rua existe
                cursor.execute("SELECT id, nome FROM ruas WHERE id = %s", (rua_id,))
                rua = cursor.fetchone()
                
                if not rua:
                    return jsonify({"error": "Rua não encontrada"}), 404
                
                # 2. Buscar produto no banco local (qualquer lugar)
                produto_info = None
                
                # Buscar primeiro na tabela produtos (produtos já cadastrados)
                cursor.execute("""
                    SELECT DISTINCT ean, nome, cor, voltagem, modelo
                    FROM produtos 
                    WHERE ean = %s AND ativo = TRUE 
                    LIMIT 1
                """, (ean,))
                
                produto_info = cursor.fetchone()
                
                # Se não encontrou, buscar na tabela produtos_standby
                if not produto_info:
                    cursor.execute("""
                        SELECT ean, nome, cor, voltagem, modelo
                        FROM produtos_standby 
                        WHERE ean = %s AND ativo = TRUE
                        LIMIT 1
                    """, (ean,))
                    produto_info = cursor.fetchone()
                
                # Se não encontrou, buscar na tabela produtos_unificados
                if not produto_info:
                    cursor.execute("""
                        SELECT ean, nome, cor, voltagem, modelo
                        FROM produtos_unificados 
                        WHERE ean = %s 
                        LIMIT 1
                    """, (ean,))
                    produto_info = cursor.fetchone()
                
                # Se ainda não encontrou, criar produto básico
                if not produto_info:
                    produto_info = {
                        'ean': ean,
                        'nome': f'Produto {ean}',
                        'cor': '',
                        'voltagem': '',
                        'modelo': ''
                    }
                else:
                    produto_info = dict(produto_info)
                
                # 3. Verificar se o produto já existe na rua
                cursor.execute("""
                    SELECT id, quantidade FROM produtos 
                    WHERE ean = %s AND rua_id = %s AND ativo = TRUE
                    ORDER BY quantidade DESC
                """, (ean, rua_id))
                
                produto_existente = cursor.fetchone()
                
                if produto_existente:
                    # Atualizar quantidade existente
                    nova_quantidade = produto_existente["quantidade"] + quantidade
                    cursor.execute("""
                        UPDATE produtos 
                        SET quantidade = %s 
                        WHERE id = %s
                    """, (nova_quantidade, produto_existente["id"]))
                    acao = f"Quantidade atualizada na rua para {nova_quantidade}"
                    produto_id = produto_existente["id"]
                else:
                    # Inserir novo produto na rua
                    cursor.execute("""
                        INSERT INTO produtos (ean, nome, cor, voltagem, modelo, quantidade, rua_id, usuario_id, timestamp, enviado, validado)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0) RETURNING id
                    """, (
                        produto_info['ean'],
                        produto_info['nome'],
                        produto_info['cor'],
                        produto_info['voltagem'],
                        produto_info['modelo'],
                        quantidade,
                        rua_id,
                        session["usuario_id"],
                        datetime.now()
                    ))
                    produto_id = cursor.fetchone()[0]
                    acao = f"Produto adicionado à rua {rua['nome']} com quantidade {quantidade}"
                
                # Registrar movimentação de entrada
                print(f"[DEBUG] Registrando movimentação - Usuario na sessão: {session.get('usuario_nome')} (ID: {session['usuario_id']})")
                try:
                    cursor.execute("""
                        INSERT INTO movimentacoes (
                            tipo_movimentacao, produto_id, ean, nome_produto, cor, voltagem, modelo, 
                            quantidade, rua_origem_id, rua_destino_id, usuario_id, observacoes, data_movimentacao
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW() - INTERVAL '3 hours')
                    """, (
                        'ENTRADA', 
                        None,  # produto_id = NULL para evitar foreign key error
                        produto_info['ean'], 
                        produto_info['nome'], 
                        produto_info['cor'], 
                        produto_info['voltagem'], 
                        produto_info['modelo'], 
                        quantidade, 
                        None,  # rua_origem_id
                        rua_id,  # rua_destino_id
                        session["usuario_id"], 
                        f"Entrada via sistema de estoque - {acao}"
                    ))
                    print(f"[DEBUG] Movimentação registrada com sucesso: ENTRADA, EAN={produto_info['ean']}")
                except Exception as mov_error:
                    print(f"[DEBUG] Erro ao registrar movimentação: {mov_error}")
                    # Continua mesmo se falhar o registro da movimentação
                
                # NOVA FUNCIONALIDADE: Remover produto do standby quando adicionado à rua
                cursor.execute("""
                    SELECT id, quantidade FROM produtos_standby 
                    WHERE ean = %s 
                    ORDER BY id 
                    LIMIT 1
                """, (ean,))
                
                produto_standby = cursor.fetchone()
                if produto_standby:
                    quantidade_standby = produto_standby["quantidade"]
                    quantidade_removida = min(quantidade_standby, quantidade)
                    
                    if quantidade_standby <= quantidade:
                        # Remove completamente do standby
                        cursor.execute("DELETE FROM produtos_standby WHERE id = %s", (produto_standby["id"],))
                        print(f"[DEBUG] Produto {ean} removido completamente do standby (quantidade: {quantidade_standby})")
                    else:
                        # Reduz quantidade no standby
                        nova_quantidade_standby = quantidade_standby - quantidade
                        cursor.execute("""
                            UPDATE produtos_standby 
                            SET quantidade = %s 
                            WHERE id = %s
                        """, (nova_quantidade_standby, produto_standby["id"]))
                        print(f"[DEBUG] Quantidade do produto {ean} reduzida no standby: {quantidade_standby} -> {nova_quantidade_standby}")
                
                conn.commit()
                
                return jsonify({
                    "success": True,
                    "message": "Produto adicionado à rua com sucesso",
                    "acao": acao,
                    "produto": {
                        "ean": produto_info['ean'],
                        "nome": produto_info['nome'],
                        "cor": produto_info['cor'],
                        "voltagem": produto_info['voltagem'],
                        "modelo": produto_info['modelo'],
                        "quantidade": quantidade
                    },
                    "rua": {
                        "id": rua['id'],
                        "nome": rua['nome']
                    }
                }), 200
                
    except Exception as e:
        print(f"Erro ao adicionar produto à rua: {e}")
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500

# API para saída de produto da rua
@app.route("/api/saida_produto_rua", methods=["POST"])
def api_saida_produto_rua():
    """
    API para remover produto da rua
    """
    if "usuario_id" not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        data = request.json
        ean = data.get("ean")
        rua_id = data.get("rua_id")
        quantidade = data.get("quantidade", 1)
        
        if not ean or not rua_id:
            return jsonify({"error": "EAN e rua_id são obrigatórios"}), 400
        
        if quantidade <= 0:
            return jsonify({"error": "Quantidade deve ser maior que zero"}), 400
        
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                
               # 1. Verificar se a rua existe
                cursor.execute("SELECT id, nome FROM ruas WHERE id = %s", (rua_id,))
                rua = cursor.fetchone()
                
                if not rua:
                    return jsonify({"error": "Rua não encontrada"}), 404
                
                # 2. Buscar produto na rua
                cursor.execute("""
                    SELECT id, ean, nome, cor, voltagem, modelo, quantidade 
                    FROM produtos 
                    WHERE ean = %s AND rua_id = %s AND ativo = TRUE
                """, (ean, rua_id))
                
                produto_na_rua = cursor.fetchone()
                
                if not produto_na_rua:
                    return jsonify({
                        "error": "Produto não encontrado nesta rua",
                        "message": f"O produto {ean} não está disponível na rua {rua['nome']}"
                    }), 404
                
                quantidade_disponivel = produto_na_rua["quantidade"]
                
                if quantidade > quantidade_disponivel:
                    return jsonify({
                        "error": f"Quantidade insuficiente na rua. Disponível: {quantidade_disponivel}"
                    }), 400
                
                # 3. Remover ou reduzir quantidade
                if quantidade == quantidade_disponivel:
                    # Remover produto completamente da rua
                    cursor.execute("DELETE FROM produtos WHERE id = %s", (produto_na_rua["id"],))
                    acao = f"Produto removido completamente da rua {rua['nome']}"
                    quantidade_restante = 0
                else:
                    # Reduzir quantidade na rua
                    nova_quantidade = quantidade_disponivel - quantidade
                    cursor.execute("""
                        UPDATE produtos 
                        SET quantidade = %s 
                        WHERE id = %s
                    """, (nova_quantidade, produto_na_rua["id"]))
                    acao = f"Quantidade na rua reduzida para {nova_quantidade}"
                    quantidade_restante = nova_quantidade
                
                 # Registrar movimentação de saida
                print(f"[DEBUG] Registrando movimentação - Usuario na sessão: {session.get('usuario_nome')} (ID: {session['usuario_id']})")
                try:

                    cursor.execute("""
                        INSERT INTO movimentacoes (
                            tipo_movimentacao, produto_id, ean, nome_produto, cor, voltagem, modelo, 
                            quantidade, rua_origem_id, rua_destino_id, usuario_id, observacoes, data_movimentacao
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW() - INTERVAL '3 hours')
                    """, (
                        'SAIDA', 
                        None,  # produto_id = NULL para evitar foreign key error
                        produto_na_rua['ean'], 
                        produto_na_rua['nome'], 
                        produto_na_rua['cor'], 
                        produto_na_rua['voltagem'], 
                        produto_na_rua['modelo'], 
                        quantidade, 
                        rua_id,  # rua_origem_id (produto SAI desta rua)
                        None,    # rua_destino_id (destino indefinido)
                        session["usuario_id"], 
                        f"Saída via sistema de estoque - {acao}"
                    ))
                    print(f"[DEBUG] Movimentação registrada com sucesso: SAIDA, EAN={produto_na_rua['ean']}")
                except Exception as mov_error:
                    print(f"[DEBUG] Erro ao registrar movimentação: {mov_error}")
                    # Continua mesmo se falhar o registro da movimentação
                
                conn.commit()
                
                return jsonify({
                    "success": True,
                    "message": "Produto removido da rua com sucesso",
                    "acao": acao,
                    "produto": {
                        "ean": produto_na_rua["ean"],
                        "nome": produto_na_rua["nome"],
                        "cor": produto_na_rua["cor"],
                        "voltagem": produto_na_rua["voltagem"],
                        "modelo": produto_na_rua["modelo"],
                        "quantidade_removida": quantidade,
                        "quantidade_restante": quantidade_restante
                    },
                    "rua": {
                        "id": rua["id"],
                        "nome": rua["nome"]
                    }
                }), 200
                
    except Exception as e:
        print(f"Erro ao remover produto da rua: {e}")
        return jsonify({"error": f"Erro interno: {str(e)}"}), 500

# Inicializar o banco de dados ao iniciar a aplicação
init_database()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")



def adicionar_rua(nome, descricao=None, qr_code_data=None):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("INSERT INTO ruas (nome, descricao, qr_code_data) VALUES (%s, %s, %s)",
                               (nome, descricao, qr_code_data))
        return True
    except psycopg2.errors.UniqueViolation:
        return False
    except psycopg2.Error as e:
        print(f"Erro ao adicionar rua: {e}")
        return False

def obter_ruas():
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, nome, descricao, qr_code_data FROM ruas ORDER BY nome")
                ruas = [dict(row) for row in cursor.fetchall()]
        return ruas
    except psycopg2.Error as e:
        print(f"Erro ao obter ruas: {e}")
        return []

def obter_rua_por_id(rua_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, nome, descricao, qr_code_data FROM ruas WHERE id = %s", (rua_id,))
                rua = cursor.fetchone()
        return dict(rua) if rua else None
    except psycopg2.Error as e:
        print(f"Erro ao obter rua por ID: {e}")
        return None

def obter_rua_por_qr_code_data(qr_code_data):
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Primeiro: buscar por qr_code_data
                cursor.execute("SELECT id, nome, descricao FROM ruas WHERE qr_code_data = %s", (qr_code_data,))
                rua = cursor.fetchone()
                
                # Se não encontrou, buscar por nome (fallback)
                if not rua:
                    cursor.execute("SELECT id, nome, descricao FROM ruas WHERE nome = %s", (qr_code_data,))
                    rua = cursor.fetchone()
                
        return dict(rua) if rua else None
    except psycopg2.Error as e:
        print(f"Erro ao obter rua por QR Code data: {e}")
        return None

def atualizar_rua(rua_id, nome, descricao, qr_code_data):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE ruas SET nome = %s, descricao = %s, qr_code_data = %s WHERE id = %s",
                               (nome, descricao, qr_code_data, rua_id))
        return True
    except psycopg2.errors.UniqueViolation:
        return False
    except psycopg2.Error as e:
        print(f"Erro ao atualizar rua: {e}")
        return False

def deletar_rua(rua_id):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM ruas WHERE id = %s", (rua_id,))
        return True
    except psycopg2.Error as e:
        print(f"Erro ao deletar rua: {e}")
        return False





@app.route("/estoque")
def estoque():
    if "usuario_id" not in session:
        flash("Você precisa estar logado para acessar esta página.", "danger")
        return redirect(url_for("login"))
    return render_template("estoque.html")





@app.route("/api/consulta_ean")
def api_consulta_ean():
    ean = request.args.get("ean")
    if not ean:
        return jsonify({"success": False, "message": "EAN não fornecido."}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # --- CORREÇÃO APLICADA AQUI ---
                # Consulta corrigida para buscar o nome da rua diretamente da tabela 'ruas'
                query = """
                    SELECT 
                        p.ean, p.nome, p.cor, p.voltagem, p.modelo, p.quantidade, 
                        r.nome as nome_rua,  -- Usar r.nome para obter o nome da rua
                        r.id as rua_id
                    FROM produtos p 
                    INNER JOIN ruas r ON p.rua_id = r.id 
                    WHERE p.ean = %s AND p.rua_id IS NOT NULL
                    ORDER BY r.nome
                """
                cursor.execute(query, (ean,))
                produtos_na_rua = cursor.fetchall()
                
                if produtos_na_rua:
                    # Agrupar informações do produto e suas localizações
                    produto_info = dict(produtos_na_rua[0])
                    ruas_info = []
                    quantidade_total = 0
                    
                    for produto in produtos_na_rua:
                        ruas_info.append({
                            "rua_id": produto["rua_id"],
                            "nome_rua": produto["nome_rua"], # Agora contém o nome correto (ex: "Sala")
                            "quantidade": produto["quantidade"]
                        })
                        quantidade_total += produto["quantidade"]
                    
                    resultado = {
                        "ean": produto_info["ean"],
                        "nome": produto_info["nome"],
                        "cor": produto_info["cor"],
                        "voltagem": produto_info["voltagem"],
                        "modelo": produto_info["modelo"],
                        "quantidade_total": quantidade_total,
                        "ruas": ruas_info, # Lista de todas as ruas e quantidades
                        "origem": "Estoque Local"
                    }
                    
                    return jsonify({"success": True, "produto": resultado}), 200
                else:
                    # Se não encontrou em nenhuma rua, pode procurar no estoque geral (opcional)
                    # (Mantendo a lógica original de fallback)
                    cursor.execute("""
                        SELECT ean, nome, cor, voltagem, modelo, SUM(quantidade) as quantidade_total
                        FROM produtos 
                        WHERE ean = %s AND rua_id IS NULL
                        GROUP BY ean, nome, cor, voltagem, modelo
                    """, (ean,))
                    produto_geral = cursor.fetchone()
                    
                    if produto_geral:
                        resultado = {
                            **dict(produto_geral),
                            "ruas": [],
                            "origem": "Estoque Geral",
                            "observacao": "Produto não alocado em rua específica."
                        }
                        return jsonify({"success": True, "produto": resultado}), 200
                    else:
                        return jsonify({"success": False, "message": "Produto não encontrado no estoque."}), 404
                        
    except psycopg2.Error as e:
        print(f"Erro ao consultar EAN: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor."}), 500





@app.route("/api/scan_qr_code_rua")
def api_scan_qr_code_rua():
    qr_code_data = request.args.get("qr_code_data")
    if not qr_code_data:
        return jsonify({"success": False, "message": "Dados do QR Code não fornecidos."}), 400

    try:
        rua = obter_rua_por_qr_code_data(qr_code_data)
        if rua:
            with get_db_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                    cursor.execute("SELECT ean, nome, quantidade FROM produtos WHERE rua_id = %s AND ativo = TRUE", (rua["id"],))
                    produtos_na_rua = [dict(row) for row in cursor.fetchall()]
            return jsonify({"success": True, "rua": rua, "produtos": produtos_na_rua}), 200
        else:
            return jsonify({"success": False, "message": "Rua não encontrada para o QR Code fornecido."}), 404
    except psycopg2.Error as e:
        print(f"Erro ao escanear QR Code de rua: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor."}), 500





@app.route("/api/entrada_produto", methods=["POST"])
def api_entrada_produto():
    print(f"[DEBUG] api_entrada_produto CHAMADA!")
    print(f"[DEBUG] Método: {request.method}")
    print(f"[DEBUG] URL: {request.url}")
    
    data = request.get_json()
    print(f"[DEBUG] Dados recebidos: {data}")
    
    ean = data.get("ean")
    quantidade = data.get("quantidade")
    rua_id = data.get("rua_id")
    
    print(f"[DEBUG] EAN: {ean}, Quantidade: {quantidade}, Rua ID: {rua_id}")

    if not all([ean, quantidade, rua_id]):
        return jsonify({"success": False, "message": "Dados incompletos."}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar se o produto já existe na rua
                cursor.execute("SELECT id, quantidade FROM produtos WHERE ean = %s AND rua_id = %s AND ativo = TRUE", (ean, rua_id))
                produto_existente = cursor.fetchone()

                if produto_existente:
                    # Atualizar quantidade
                    nova_quantidade = produto_existente[1] + quantidade
                    cursor.execute("UPDATE produtos SET quantidade = %s WHERE id = %s", (nova_quantidade, produto_existente[0]))
                    message = "Quantidade do produto atualizada com sucesso."
                else:
                    # Adicionar novo produto na rua
                    # Tentar buscar informações do produto de alguma fonte externa ou de produtos já cadastrados sem rua
                    # Por simplicidade, vamos assumir que o nome virá de uma busca ou será genérico por enquanto
                    # Em um cenário real, precisaríamos de uma lógica para obter nome, cor, voltagem, modelo
                    
                    # Busca por um produto com o mesmo EAN em qualquer rua para pegar os detalhes
                    cursor.execute("SELECT nome, cor, voltagem, modelo FROM produtos WHERE ean = %s AND ativo = TRUE LIMIT 1", (ean,))
                    info_produto = cursor.fetchone()
                    
                    nome = info_produto[0] if info_produto else "Produto Desconhecido"
                    cor = info_produto[1] if info_produto else None
                    voltagem = info_produto[2] if info_produto else None
                    modelo = info_produto[3] if info_produto else None

                    usuario_id = session.get("usuario_id") # Assumindo que o usuário está logado
                    if not usuario_id:
                        return jsonify({"success": False, "message": "Usuário não logado."}), 401

                    cursor.execute("INSERT INTO produtos (ean, nome, cor, voltagem, modelo, quantidade, usuario_id, timestamp, rua_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                   (ean, nome, cor, voltagem, modelo, quantidade, usuario_id, datetime.now(), rua_id))
                    message = "Produto adicionado à rua com sucesso."

            # Registrar movimentação de entrada
            registrar_movimentacao(
                tipo_movimentacao='ENTRADA', 
                ean=ean, 
                nome_produto=nome, 
                cor=cor, 
                voltagem=voltagem, 
                modelo=modelo, 
                quantidade=quantidade, 
                usuario_id=usuario_id, 
                rua_origem_id=None, 
                rua_destino_id=rua_id, 
                produto_id=None, # Não temos o produto_id aqui, mas podemos buscar se necessário
                observacoes=f'Entrada de {quantidade} unidades do produto {ean} na rua {rua_id}'
            )
            conn.commit()
        return jsonify({"success": True, "message": message}), 200
    except psycopg2.Error as e:
        print(f"Erro na entrada de produto: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor."}), 500


@app.route("/api/entrada_produtos_lote", methods=["POST"])
def api_entrada_produtos_lote():
    """API para processar entrada de múltiplos produtos em lote"""
    print(f"[DEBUG] api_entrada_produtos_lote INICIADA")
    try:
        data = request.get_json()
        produtos = data.get("produtos", [])
        rua_id = data.get("rua_id")
        
        print(f"[DEBUG] Dados recebidos: produtos={len(produtos) if produtos else 0}, rua_id={rua_id}")
        
        if not produtos or not rua_id:
            print(f"[DEBUG] ERRO: Dados incompletos - produtos={produtos}, rua_id={rua_id}")
            return jsonify({"success": False, "message": "Dados incompletos."}), 400
        
        usuario_id = session.get("usuario_id")
        print(f"[DEBUG] Usuario da sessão: {usuario_id}")
        if not usuario_id:
            print(f"[DEBUG] ERRO: Usuário não logado")
            return jsonify({"success": False, "message": "Usuário não logado."}), 401
        
        produtos_processados = 0
        produtos_com_erro = []
        
        print(f"[DEBUG] Iniciando processamento de {len(produtos)} produtos")
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                for i, produto in enumerate(produtos):
                    print(f"[DEBUG] Processando produto {i+1}/{len(produtos)}: {produto}")
                    try:
                        ean = produto.get("ean")
                        quantidade = produto.get("quantidade", 1)
                        
                        print(f"[DEBUG] EAN={ean}, Quantidade={quantidade}")
                        
                        if not ean:
                            print(f"[DEBUG] ERRO: EAN não informado para produto {i+1}")
                            produtos_com_erro.append({"ean": ean, "erro": "EAN não informado"})
                            continue
                        
                        # Verificar se o produto já existe na rua
                        print(f"[DEBUG] Verificando se produto {ean} já existe na rua {rua_id}")
                        cursor.execute("SELECT id, quantidade FROM produtos WHERE ean = %s AND rua_id = %s AND ativo = TRUE", (ean, rua_id))
                        produto_existente = cursor.fetchone()
                        
                        print(f"[DEBUG] Produto existente: {produto_existente}")
                        
                        if produto_existente:
                            print(f"[DEBUG] Produto existe - atualizando quantidade")
                            # Atualizar quantidade
                            nova_quantidade = produto_existente[1] + quantidade
                            cursor.execute("UPDATE produtos SET quantidade = %s WHERE id = %s", (nova_quantidade, produto_existente[0]))
                            
                            # Buscar informações do produto para registro de movimentação
                            cursor.execute("SELECT nome, cor, voltagem, modelo FROM produtos WHERE id = %s", (produto_existente[0],))
                            info_produto = cursor.fetchone()
                            nome = info_produto[0] if info_produto else "Produto Desconhecido"
                            cor = info_produto[1] if info_produto else None
                            voltagem = info_produto[2] if info_produto else None
                            modelo = info_produto[3] if info_produto else None
                            
                            print(f"[DEBUG] Chamando registrar_movimentacao para produto existente: EAN={ean}, Qtd={quantidade}, User={usuario_id}")
                            # Registrar movimentação de entrada para produto existente
                            registrar_movimentacao(
                                'ENTRADA', 
                                ean, 
                                nome, 
                                cor, 
                                voltagem, 
                                modelo, 
                                quantidade, 
                                usuario_id, 
                                None, 
                                rua_id, 
                                produto_existente[0], 
                                f"Entrada em lote via sistema de estoque - Quantidade atualizada para {nova_quantidade}"
                            )
                            print(f"[DEBUG] Movimentação registrada para produto existente")
                        else:
                            print(f"[DEBUG] Produto não existe - criando novo")
                            # Buscar informações do produto de produtos já cadastrados (priorizar estoque geral)
                            cursor.execute("SELECT nome, cor, voltagem, modelo FROM produtos WHERE ean = %s AND rua_id IS NULL AND ativo = TRUE LIMIT 1", (ean,))
                            info_produto = cursor.fetchone()
                            
                            # Se não encontrar no estoque geral, buscar em qualquer lugar
                            if not info_produto:
                                cursor.execute("SELECT nome, cor, voltagem, modelo FROM produtos WHERE ean = %s AND ativo = TRUE LIMIT 1", (ean,))
                                info_produto = cursor.fetchone()
                            
                            nome = info_produto[0] if info_produto else produto.get("nome", "Produto Desconhecido")
                            cor = info_produto[1] if info_produto else produto.get("cor")
                            voltagem = info_produto[2] if info_produto else produto.get("voltagem")
                            modelo = info_produto[3] if info_produto else produto.get("modelo")
                            
                            cursor.execute("""
                                INSERT INTO produtos (ean, nome, cor, voltagem, modelo, quantidade, usuario_id, timestamp, rua_id) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (ean, nome, cor, voltagem, modelo, quantidade, usuario_id, datetime.now(), rua_id))
                            
                            print(f"[DEBUG] Produto novo criado: EAN={ean}, Nome={nome}")
                            
                            print(f"[DEBUG] Chamando registrar_movimentacao para produto novo: EAN={ean}, Qtd={quantidade}, User={usuario_id}")
                            # Registrar movimentação de entrada para produto novo
                            registrar_movimentacao(
                                'ENTRADA', 
                                ean, 
                                nome, 
                                cor, 
                                voltagem, 
                                modelo, 
                                quantidade, 
                                usuario_id, 
                                None, 
                                rua_id, 
                                None, 
                                f"Entrada em lote via sistema de estoque - Produto novo criado com {quantidade} unidades"
                            )
                            print(f"[DEBUG] Movimentação registrada para produto novo")
                        
                        produtos_processados += 1
                        print(f"[DEBUG] Produto {i+1} processado com sucesso")
                        
                    except Exception as e:
                        print(f"[DEBUG] ERRO ao processar produto {i+1}: {e}")
                        produtos_com_erro.append({"ean": produto.get("ean"), "erro": str(e)})
                
                conn.commit()
                print(f"[DEBUG] Transação commitada - {produtos_processados} produtos processados")
        
        print(f"[DEBUG] Processamento concluído: {produtos_processados} sucessos, {len(produtos_com_erro)} erros")
        return jsonify({
            "success": True,
            "message": f"Processamento concluído: {produtos_processados} produtos processados com sucesso.",
            "produtos_processados": produtos_processados,
            "produtos_com_erro": produtos_com_erro
        })
        
    except Exception as e:
        print(f"[DEBUG] ERRO GERAL na api_entrada_produtos_lote: {e}")
        return jsonify({"success": False, "message": f"Erro interno: {str(e)}"}), 500


# API para obter estoque por rua
@app.route("/api/estoque_rua/<int:rua_id>", methods=["GET"])


@app.route("/api/saida_produto", methods=["POST"])
def api_saida_produto():
    data = request.get_json()
    ean = data.get("ean")
    quantidade = data.get("quantidade")
    rua_id = data.get("rua_id")

    if not all([ean, quantidade, rua_id]):
        return jsonify({"success": False, "message": "Dados incompletos."}), 400

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, quantidade FROM produtos WHERE ean = %s AND rua_id = %s AND ativo = TRUE", (ean, rua_id))
                produto_existente = cursor.fetchone()

                if produto_existente:
                    nova_quantidade = produto_existente[1] - quantidade
                    if nova_quantidade > 0:
                        cursor.execute("UPDATE produtos SET quantidade = %s WHERE id = %s", (nova_quantidade, produto_existente[0]))
                        message = "Quantidade do produto atualizada com sucesso."
                    else:
                        cursor.execute("DELETE FROM produtos WHERE id = %s", (produto_existente[0],))
                        message = "Produto removido da rua com sucesso (quantidade zerada)."
                else:
                    return jsonify({"success": False, "message": "Produto não encontrado nesta rua."}), 404

            # Registrar movimentação de saída
            # Obter detalhes do produto para o registro da movimentação
            cursor.execute("SELECT nome, cor, voltagem, modelo FROM produtos WHERE ean = %s AND ativo = TRUE LIMIT 1", (ean,))
            info_produto = cursor.fetchone()
            nome_prod = info_produto[0] if info_produto else "Produto Desconhecido"
            cor_prod = info_produto[1] if info_produto else None
            voltagem_prod = info_produto[2] if info_produto else None
            modelo_prod = info_produto[3] if info_produto else None

            usuario_id = session.get("usuario_id")
            if not usuario_id:
                return jsonify({"success": False, "message": "Usuário não logado."}), 401

            registrar_movimentacao(
                tipo_movimentacao='SAIDA',
                nome_produto=nome_prod,
                cor=cor_prod,
                voltagem=voltagem_prod,
                modelo=modelo_prod,
                quantidade=quantidade,
                usuario_id=usuario_id,
                rua_origem_id=rua_id,
                rua_destino_id=None,
                produto_id=produto_existente[0],
                observacoes=f'Saída de {quantidade} unidades do produto {ean} da rua {rua_id}'
            )

            conn.commit()
        return jsonify({"success": True, "message": message}), 200
    except psycopg2.Error as e:
        print(f"Erro na saída de produto: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor."}), 500



# ===== FUNÇÕES PARA ESTOQUE LOCAL =====

def obter_estoque_por_rua():
    """Retorna um dicionário com ruas e seus produtos. OTIMIZADO: consulta única com JOIN."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # OTIMIZAÇÃO: 1 consulta única com JOIN em vez de N+1 consultas
                cursor.execute("""
                    SELECT 
                        r.id as rua_id, 
                        r.nome as rua_nome, 
                        r.descricao as rua_descricao,
                        p.id as produto_id, 
                        p.ean, 
                        p.nome as produto_nome, 
                        p.cor, 
                        p.voltagem, 
                        p.modelo, 
                        p.quantidade
                    FROM ruas r
                    LEFT JOIN produtos p ON r.id = p.rua_id AND p.ativo = true
                    WHERE r.ativa = true
                    ORDER BY r.nome, p.nome
                """)
                
                resultados = cursor.fetchall()
                estoque_por_rua = {}
                
                # Agrupar resultados por rua
                for row in resultados:
                    rua_id = row['rua_id']
                    
                    # Inicializar rua se não existe
                    if rua_id not in estoque_por_rua:
                        estoque_por_rua[rua_id] = {
                            'rua_info': {
                                'id': rua_id,
                                'nome': row['rua_nome'],
                                'descricao': row['rua_descricao']
                            },
                            'produtos': []
                        }
                    
                    # Adicionar produto se existe (LEFT JOIN pode retornar ruas sem produtos)
                    if row['produto_id'] is not None:
                        produto = {
                            'id': row['produto_id'],
                            'ean': row['ean'],
                            'nome': row['produto_nome'],
                            'cor': row['cor'],
                            'voltagem': row['voltagem'],
                            'modelo': row['modelo'],
                            'quantidade': row['quantidade']
                        }
                        estoque_por_rua[rua_id]['produtos'].append(produto)
                
                return estoque_por_rua
                
    except psycopg2.Error as e:
        print(f"Erro ao obter estoque por rua: {e}")
        return {}

def obter_estoque_consolidado():
    """Retorna uma lista de produtos consolidados."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        p.ean, 
                        p.nome, 
                        p.cor, 
                        p.voltagem, 
                        p.modelo, 
                        SUM(p.quantidade) AS quantidade_total,
                        COUNT(DISTINCT p.rua_id) AS total_ruas,
                        STRING_AGG(DISTINCT r.nome, ', ' ORDER BY r.nome) AS ruas
                    FROM produtos p 
                    JOIN ruas r ON p.rua_id = r.id 
                    WHERE p.ativo = true AND r.ativa = true
                    GROUP BY p.ean, p.nome, p.cor, p.voltagem, p.modelo 
                    ORDER BY p.nome
                """)
                produtos = cursor.fetchall()
                return [dict(produto) for produto in produtos]
    except psycopg2.Error as e:
        print(f"Erro ao obter estoque consolidado: {e}")
        return []

def obter_indicadores_estoque():
    """Retorna indicadores agregados do estoque local."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Calcular quantidade total de produtos
                cursor.execute("""
                    SELECT COALESCE(SUM(quantidade), 0) AS quantidade_total
                    FROM produtos 
                    WHERE rua_id IS NOT NULL AND ativo = true
                """)
                resultado_quantidade = cursor.fetchone()
                quantidade_total = resultado_quantidade['quantidade_total'] if resultado_quantidade['quantidade_total'] else 0
                
                # Calcular quantidade de modelos únicos (baseado em EAN)
                cursor.execute("""
                    SELECT COUNT(DISTINCT ean) AS modelos_unicos
                    FROM produtos 
                    WHERE rua_id IS NOT NULL AND ativo = true
                """)
                resultado_modelos = cursor.fetchone()
                modelos_unicos = resultado_modelos['modelos_unicos'] if resultado_modelos['modelos_unicos'] else 0
                
                return {
                    'quantidade_total': quantidade_total,
                    'modelos_unicos': modelos_unicos
                }
    except psycopg2.Error as e:
        print(f"Erro ao obter indicadores do estoque: {e}")
        return {
            'quantidade_total': 0,
            'modelos_unicos': 0
        }

def adicionar_nova_rua(nome, descricao=None):
    """Insere uma nova rua."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO ruas (nome, descricao) VALUES (%s, %s) RETURNING id",
                    (nome, descricao)
                )
                rua_id = cursor.fetchone()[0]
                conn.commit()
                return rua_id
    except psycopg2.errors.UniqueViolation:
        return None  # Rua já existe
    except psycopg2.Error as e:
        print(f"Erro ao adicionar rua: {e}")
        return None

def verificar_produtos_em_rua(rua_id):
    """Verifica se há produtos em uma rua."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM produtos WHERE rua_id = %s AND ativo = TRUE", (rua_id,))
                count = cursor.fetchone()[0]
                return count > 0
    except psycopg2.Error as e:
        print(f"Erro ao verificar produtos em rua: {e}")
        return True  # Por segurança, assume que há produtos

def excluir_rua_db(rua_id):
    """Exclui uma rua do banco de dados."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM ruas WHERE id = %s", (rua_id,))
                conn.commit()
                return True
    except psycopg2.Error as e:
        print(f"Erro ao excluir rua: {e}")
        return False

def adicionar_produto_estoque(ean, nome, cor, voltagem, modelo, quantidade, usuario_id, rua_id):
    """Adiciona ou atualiza um produto no estoque."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar se o produto já existe na mesma rua
                cursor.execute("""
                    SELECT id, quantidade FROM produtos WHERE ativo = TRUE
                    WHERE ean = %s AND rua_id = %s AND nome = %s AND 
                          COALESCE(cor, \'\') = COALESCE(%s, \'\') AND 
                          COALESCE(voltagem, \'\') = COALESCE(%s, \'\') AND 
                          COALESCE(modelo, \'\') = COALESCE(%s, \'\') AND ativo = TRUE
                """, (ean, rua_id, nome, cor, voltagem, modelo))
                produto_existente = cursor.fetchone()
                
                if produto_existente:
                    # Atualizar quantidade
                    nova_quantidade = produto_existente[1] + quantidade
                    cursor.execute(
                        "UPDATE produtos SET quantidade = %s WHERE id = %s",
                        (nova_quantidade, produto_existente[0])
                    )
                    message = f"Quantidade atualizada. Nova quantidade: {nova_quantidade}"
                    produto_id = produto_existente[0]
                else:
                    # Inserir novo produto
                    cursor.execute("""
                        INSERT INTO produtos (ean, nome, cor, voltagem, modelo, quantidade, usuario_id, timestamp, rua_id) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                    """, (ean, nome, cor, voltagem, modelo, quantidade, usuario_id, datetime.now(), rua_id))
                    produto_id = cursor.fetchone()[0]
                    message = "Produto adicionado com sucesso"
                
                # Registrar movimentação de entrada
                registrar_movimentacao(
                    'ENTRADA', ean, nome, cor, voltagem, modelo, quantidade, 
                    usuario_id, None, rua_id, produto_id, 
                    f"Adição de produto ao estoque - {message}"
                )
                
                conn.commit()
                return True, message
    except psycopg2.Error as e:
        print(f"Erro ao adicionar produto ao estoque: {e}")
        return False, "Erro interno do servidor"

def registrar_movimentacao(tipo_movimentacao, ean, nome_produto, cor, voltagem, modelo, quantidade, usuario_id, rua_origem_id=None, rua_destino_id=None, produto_id=None, observacoes=None):
    """Registra uma movimentação de produto."""
    print(f"[DEBUG] Tentando registrar movimentação: Tipo={tipo_movimentacao}, EAN={ean}, Qtd={quantidade}, User={usuario_id}, Produto_ID={produto_id}")
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO movimentacoes (
                        tipo_movimentacao, produto_id, ean, nome_produto, cor, voltagem, modelo, 
                        quantidade, rua_origem_id, rua_destino_id, usuario_id, observacoes, data_movimentacao
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW() - INTERVAL '3 hours')
                """, (tipo_movimentacao, produto_id, ean, nome_produto, cor, voltagem, modelo, 
                      quantidade, rua_origem_id, rua_destino_id, usuario_id, observacoes))
                conn.commit()
                print(f"[DEBUG] Movimentação registrada com sucesso: Tipo={tipo_movimentacao}, EAN={ean}")
                return True
    except psycopg2.Error as e:
        print(f"[DEBUG] Erro ao registrar movimentação: {e}")
        return False

def consultar_movimentacoes(data_inicio=None, data_fim=None, usuario_id=None, tipo_movimentacao=None, ean=None, limit=100, offset=0):
    """Consulta movimentações com filtros opcionais."""
    print(f"[DEBUG] consultar_movimentacoes chamada com: data_inicio={data_inicio}, data_fim={data_fim}, usuario_id={usuario_id}, tipo={tipo_movimentacao}, ean={ean}")
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Primeiro, vamos verificar quantas movimentações existem no total
                cursor.execute("SELECT COUNT(*) FROM movimentacoes")
                total_movimentacoes = cursor.fetchone()[0]
                print(f"[DEBUG] Total de movimentações na tabela: {total_movimentacoes}")
                
                # Verificar movimentações de hoje sem filtro
                cursor.execute("""
                    SELECT COUNT(*), 
                           MIN(data_movimentacao) as primeira_data,
                           MAX(data_movimentacao) as ultima_data
                    FROM movimentacoes 
                    WHERE DATE(data_movimentacao - INTERVAL '3 hours') = CURRENT_DATE
                """)
                resultado_hoje = cursor.fetchone()
                print(f"[DEBUG] Movimentações de hoje: {resultado_hoje[0]}, primeira: {resultado_hoje[1]}, última: {resultado_hoje[2]}")
                
                # Mostrar todas as movimentações existentes para debug
                cursor.execute("""
                    SELECT data_movimentacao,
                           data_movimentacao - INTERVAL '3 hours' as data_local,
                           DATE(data_movimentacao - INTERVAL '3 hours') as data_apenas,
                           tipo_movimentacao, ean, usuario_id
                    FROM movimentacoes 
                    ORDER BY data_movimentacao DESC
                    LIMIT 10
                """)
                todas_movimentacoes = cursor.fetchall()
                print(f"[DEBUG] Últimas 10 movimentações:")
                for mov in todas_movimentacoes:
                    print(f"[DEBUG]   Data: {mov[0]} | Local: {mov[1]} | Data apenas: {mov[2]} | Tipo: {mov[3]} | EAN: {mov[4]} | User: {mov[5]}")
                
                # Verificar data atual do servidor
                cursor.execute("SELECT CURRENT_DATE, NOW() - INTERVAL '3 hours'")
                data_servidor = cursor.fetchone()
                print(f"[DEBUG] Data atual do servidor: {data_servidor[0]} | Hora local: {data_servidor[1]}")
                
                # Construir query dinamicamente baseada nos filtros
                where_conditions = []
                params = []
                
                # CORREÇÃO 1: Converter datas do formato brasileiro para formato SQL
                if data_inicio:
                    try:
                        print(f"[DEBUG] Processando data_inicio: '{data_inicio}' (tipo: {type(data_inicio)})")
                        # Converter de dd/mm/yyyy para yyyy-mm-dd
                        if '/' in data_inicio:
                            dia, mes, ano = data_inicio.split('/')
                            data_inicio_sql = f"{ano}-{mes.zfill(2)}-{dia.zfill(2)}"
                        else:
                            data_inicio_sql = data_inicio
                        
                        # Usar timezone local para comparação
                        where_conditions.append("DATE(m.data_movimentacao - INTERVAL '3 hours') >= %s")
                        params.append(data_inicio_sql)
                        print(f"[DEBUG] Data início convertida: '{data_inicio}' -> '{data_inicio_sql}'")
                        
                        # Testar a data convertida
                        cursor.execute("SELECT %s::date", (data_inicio_sql,))
                        data_teste = cursor.fetchone()[0]
                        print(f"[DEBUG] Data início como DATE: {data_teste}")
                        
                    except Exception as e:
                        print(f"[DEBUG] Erro ao converter data_inicio: {e}")
                
                if data_fim:
                    try:
                        print(f"[DEBUG] Processando data_fim: '{data_fim}' (tipo: {type(data_fim)})")
                        # Converter de dd/mm/yyyy para yyyy-mm-dd
                        if '/' in data_fim:
                            dia, mes, ano = data_fim.split('/')
                            data_fim_sql = f"{ano}-{mes.zfill(2)}-{dia.zfill(2)}"
                        else:
                            data_fim_sql = data_fim
                        
                        # Usar timezone local para comparação
                        where_conditions.append("DATE(m.data_movimentacao - INTERVAL '3 hours') <= %s")
                        params.append(data_fim_sql)
                        print(f"[DEBUG] Data fim convertida: '{data_fim}' -> '{data_fim_sql}'")
                        
                        # Testar a data convertida
                        cursor.execute("SELECT %s::date", (data_fim_sql,))
                        data_teste = cursor.fetchone()[0]
                        print(f"[DEBUG] Data fim como DATE: {data_teste}")
                        
                    except Exception as e:
                        print(f"[DEBUG] Erro ao converter data_fim: {e}")
                
                if usuario_id is not None and usuario_id != '':
                    where_conditions.append("m.usuario_id = %s")
                    params.append(usuario_id)
                
                # CORREÇÃO 2: Normalizar o tipo de movimentação para maiúsculo
                if tipo_movimentacao:
                    tipo_normalizado = tipo_movimentacao.upper()
                    where_conditions.append("m.tipo_movimentacao = %s")
                    params.append(tipo_normalizado)
                    print(f"[DEBUG] Tipo movimentação normalizado: {tipo_movimentacao} -> {tipo_normalizado}")
                
                if ean:
                    where_conditions.append("m.ean ILIKE %s")
                    params.append(f"%{ean}%")
                
                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                query = f"""
                    SELECT 
                        m.*,
                        u.nome as usuario_nome,
                        ro.nome as rua_origem_nome,
                        rd.nome as rua_destino_nome
                    FROM movimentacoes m
                    LEFT JOIN usuarios u ON m.usuario_id = u.id
                    LEFT JOIN ruas ro ON m.rua_origem_id = ro.id
                    LEFT JOIN ruas rd ON m.rua_destino_id = rd.id
                    {where_clause}
                    ORDER BY m.data_movimentacao DESC
                    LIMIT %s OFFSET %s
                """
                
                params.extend([limit, offset])
                print(f"[DEBUG] Query final: {query}")
                print(f"[DEBUG] Params finais: {params}")
                
                # Teste específico: verificar se existem movimentações com as datas filtradas
                if data_inicio or data_fim:
                    # Criar condições de teste excluindo apenas LIMIT e OFFSET
                    test_where_conditions = []
                    test_params = []
                    
                    # Recriar condições sem LIMIT e OFFSET
                    if data_inicio:
                        test_where_conditions.append("DATE(m.data_movimentacao - INTERVAL '3 hours') >= %s")
                        test_params.append(params[0])  # primeiro parâmetro é data_inicio
                    
                    if data_fim:
                        test_where_conditions.append("DATE(m.data_movimentacao - INTERVAL '3 hours') <= %s")
                        test_params.append(params[1] if data_inicio else params[0])  # segundo parâmetro é data_fim
                    
                    if usuario_id is not None and usuario_id != '':
                        test_where_conditions.append("m.usuario_id = %s")
                        # Encontrar posição do usuario_id nos params
                        for i, param in enumerate(params):
                            if param == usuario_id:
                                test_params.append(param)
                                break
                    
                    if tipo_movimentacao:
                        test_where_conditions.append("m.tipo_movimentacao = %s")
                        # Encontrar posição do tipo nos params
                        for i, param in enumerate(params):
                            if param == tipo_movimentacao.upper():
                                test_params.append(param)
                                break
                    
                    test_where = " AND ".join(test_where_conditions)
                    test_query = f"""
                        SELECT COUNT(*), 
                               MIN(data_movimentacao - INTERVAL '3 hours') as min_data,
                               MAX(data_movimentacao - INTERVAL '3 hours') as max_data
                        FROM movimentacoes m 
                        WHERE {test_where}
                    """ if test_where else "SELECT COUNT(*), MIN(data_movimentacao - INTERVAL '3 hours'), MAX(data_movimentacao - INTERVAL '3 hours') FROM movimentacoes m"
                    
                    if test_where:
                        cursor.execute(test_query, test_params)
                    else:
                        cursor.execute(test_query)
                    test_result = cursor.fetchone()
                    print(f"[DEBUG] Teste com filtros: {test_result[0]} registros, min: {test_result[1]}, max: {test_result[2]}")
                
                cursor.execute(query, params)
                movimentacoes = cursor.fetchall()
                
                # Contar total de registros para paginação
                count_query = f"""
                    SELECT COUNT(*) FROM movimentacoes m
                    LEFT JOIN usuarios u ON m.usuario_id = u.id
                    LEFT JOIN ruas ro ON m.rua_origem_id = ro.id
                    LEFT JOIN ruas rd ON m.rua_destino_id = rd.id
                    {where_clause}
                """
                cursor.execute(count_query, params[:-2])  # Remove limit e offset
                total_registros = cursor.fetchone()[0]
                
                print(f"[DEBUG] Encontradas {len(movimentacoes)} movimentações, total={total_registros}")
                return [dict(mov) for mov in movimentacoes], total_registros
    except psycopg2.Error as e:
        print(f"[DEBUG] Erro ao consultar movimentações: {e}")
        return [], 0

def obter_estatisticas_movimentacao(data_inicio=None, data_fim=None, usuario_id=None):
    """Obtém estatísticas de movimentação para um período."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                where_conditions = []
                params = []
                
                if data_inicio:
                    where_conditions.append("data_movimentacao >= %s")
                    params.append(data_inicio)
                
                if data_fim:
                    where_conditions.append("data_movimentacao <= %s")
                    params.append(data_fim)
                
                if usuario_id is not None and usuario_id != ":":
                    where_conditions.append("usuario_id = %s")
                    params.append(usuario_id)
                where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                
                # Estatísticas por tipo de movimentação
                cursor.execute(f"""
                    SELECT 
                        tipo_movimentacao,
                        COUNT(*) as total_movimentacoes,
                        SUM(quantidade) as total_quantidade
                    FROM movimentacoes
                    {where_clause}
                    GROUP BY tipo_movimentacao
                """, params)
                stats_por_tipo = cursor.fetchall()
                
                # Estatísticas por usuário e destino
                cursor.execute(f"""
                    SELECT 
                        u.nome as usuario_nome,
                        SUM(CASE WHEN p.destino = 'mercado_livre' THEN p.quantidade ELSE 0 END) as total_mercado_livre,
                        SUM(CASE WHEN p.destino = 'loja' THEN p.quantidade ELSE 0 END) as total_loja,
                        SUM(CASE WHEN p.destino = 'manutencao' THEN p.quantidade ELSE 0 END) as total_manutencao,
                        SUM(p.quantidade) as total_geral_enviado,
                        MAX(p.data_envio) as ultima_atividade
                    FROM produtos p
                    LEFT JOIN usuarios u ON p.usuario_id = u.id
                    WHERE p.enviado = 1
                    GROUP BY u.nome
                    ORDER BY total_geral_enviado DESC
                    LIMIT 10
                """, params)
                stats_por_usuario = cursor.fetchall()
                
                # Produtos mais movimentados
                cursor.execute(f"""
                    SELECT 
                        ean,
                        nome_produto,
                        COUNT(*) as total_movimentacoes,
                        SUM(quantidade) as total_quantidade
                    FROM movimentacoes
                    {where_clause}
                    GROUP BY ean, nome_produto
                    ORDER BY total_movimentacoes DESC
                    LIMIT 10
                """, params)
                produtos_mais_movimentados = cursor.fetchall()
                
                return {
                    'por_tipo': [dict(stat) for stat in stats_por_tipo],
                    'por_usuario': [dict(stat) for stat in stats_por_usuario],
                    'produtos_mais_movimentados': [dict(stat) for stat in produtos_mais_movimentados]
                }
    except psycopg2.Error as e:
        print(f"Erro ao obter estatísticas de movimentação: {e}")
        return {
            'por_tipo': [],
            'por_usuario': [],
            'produtos_mais_movimentados': []
        }

def excluir_produto_db(produto_id):
    """Exclui um produto."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE produtos SET ativo = FALSE WHERE id = %s", (produto_id,))
                conn.commit()
                return True
    except psycopg2.Error as e:
        print(f"Erro ao excluir produto: {e}")
        return False

def remover_quantidade_produto_db(produto_id, quantidade_remover):
    """Remove quantidade de produto."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Obter quantidade atual e detalhes do produto
                cursor.execute(
                    "SELECT quantidade, ean, nome, cor, voltagem, modelo, rua_id "
                    "FROM produtos WHERE id = %s", 
                    (produto_id,)
                )
                resultado = cursor.fetchone()
                
                if not resultado:
                    return (False, "Produto não encontrado")
                
                quantidade_atual, ean_prod, nome_prod, cor_prod, voltagem_prod, modelo_prod, rua_origem_id_prod = resultado
                nova_quantidade = quantidade_atual - quantidade_remover
                
                if nova_quantidade <= 0:
                    # Remover produto se quantidade for zero ou negativa
                    cursor.execute("UPDATE produtos SET ativo = FALSE WHERE id = %s", (produto_id,))
                    message = "Produto marcado como inativo (quantidade zerada)"
                else:
                    # Atualizar quantidade
                    cursor.execute(
                        "UPDATE produtos SET quantidade = %s WHERE id = %s", 
                        (nova_quantidade, produto_id)
                    )
                    message = f"Quantidade atualizada. Nova quantidade: {nova_quantidade}"
                
                conn.commit()

                # Registrar movimentação de saída
                registrar_movimentacao(
                    tipo_movimentacao='SAIDA', 
                    ean=ean_prod, 
                    nome_produto=nome_prod, 
                    cor=cor_prod, 
                    voltagem=voltagem_prod, 
                    modelo=modelo_prod, 
                    quantidade=quantidade_remover, 
                    usuario_id=session.get('usuario_id'), 
                    rua_origem_id=rua_origem_id_prod, 
                    rua_destino_id=None, 
                    produto_id=produto_id, 
                    observacoes=f'Remoção de {quantidade_remover} unidades do produto - {message}'
                )

                return True, message

    except psycopg2.Error as e:
        print(f"Erro ao remover quantidade: {e}")
        return (False, "Erro no banco de dados")


def obter_dados_para_exportacao():
    """Prepara os dados para exportação Excel."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        p.ean AS "EAN",
                        p.nome AS "Nome do Produto",
                        p.cor AS "Cor",
                        p.voltagem AS "Voltagem",
                        p.modelo AS "Modelo",
                        p.quantidade AS "Quantidade",
                        r.nome AS "Nome da Rua",
                        r.descricao AS "Descrição da Rua"
                    FROM produtos p 
                    JOIN ruas r ON p.rua_id = r.id 
                    ORDER BY r.nome, p.nome
                """)
                dados = cursor.fetchall()
                return [dict(row) for row in dados]
    except psycopg2.Error as e:
        print(f"Erro ao obter dados para exportação: {e}")
        return []

# ===== ROTAS PARA ESTOQUE LOCAL =====

@app.route("/estoque_local")
def estoque_local():
    """Renderiza o painel de estoque local com sistema de tags."""
    if not session.get("logado") or not session.get("admin"):
        flash("Acesso negado. Apenas administradores podem acessar esta área.", "error")
        return redirect(url_for("login"))
    
    # Sistema de tags ativado
    estoque_por_tag = obter_estoque_por_tag()
    estoque_consolidado = obter_estoque_consolidado()
    indicadores = obter_indicadores_estoque()
    ruas_sem_tag = obter_ruas_sem_tag()
    tags_disponiveis = obter_tags_ativas()
    
    # Sistema de tags ativado - template novo funcionando
    return render_template("estoque_local_template.html", 
                         estoque_por_tag=estoque_por_tag,
                         estoque_consolidado=estoque_consolidado,
                         indicadores=indicadores,
                         ruas_sem_tag=ruas_sem_tag,
                         tags_disponiveis=tags_disponiveis)

@app.route("/estoque_local/rua", methods=["POST"])
def adicionar_rua():
    """Adiciona uma nova rua."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    data = request.get_json()
    nome = data.get("nome", "").strip()
    descricao = data.get("descricao", "").strip()
    tag_id = data.get("tag_id")
    
    if not nome:
        return jsonify({"success": False, "message": "Nome da rua é obrigatório"}), 400
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar se já existe uma rua com este nome
                cursor.execute("SELECT id FROM ruas WHERE nome = %s", (nome,))
                if cursor.fetchone():
                    return jsonify({"success": False, "message": "Já existe uma rua com este nome"}), 400
                
                # Se tag_id foi fornecido, verificar se existe
                if tag_id:
                    cursor.execute("SELECT id FROM tags WHERE id = %s AND ativo = true", (tag_id,))
                    if not cursor.fetchone():
                        return jsonify({"success": False, "message": "Tag não encontrada"}), 400
                
                # Inserir nova rua
                cursor.execute("""
                    INSERT INTO ruas (nome, descricao, tag_id, ativa, data_criacao) 
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                """, (nome, descricao, tag_id, True, datetime.now()))
                
                rua_id = cursor.fetchone()[0]
                conn.commit()
                
                return jsonify({
                    "success": True, 
                    "message": "Rua criada com sucesso", 
                    "rua_id": rua_id
                })
                
    except Exception as e:
        print(f"Erro ao criar rua: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/estoque_local/rua/<int:rua_id>", methods=["DELETE"])
def excluir_rua(rua_id):
    """Exclui uma rua."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar se a rua existe
                cursor.execute("SELECT nome FROM ruas WHERE id = %s", (rua_id,))
                rua = cursor.fetchone()
                if not rua:
                    return jsonify({"success": False, "message": "Rua não encontrada"}), 404
                
                # Verificar se há produtos na rua
                cursor.execute("SELECT COUNT(*) FROM estoque_ruas WHERE rua_id = %s", (rua_id,))
                count = cursor.fetchone()[0]
                if count > 0:
                    return jsonify({
                        "success": False, 
                        "message": "Não é possível excluir a rua. Há produtos associados a ela"
                    }), 400
                
                # Excluir a rua
                cursor.execute("DELETE FROM ruas WHERE id = %s", (rua_id,))
                conn.commit()
                
                return jsonify({
                    "success": True, 
                    "message": f"Rua '{rua[0]}' excluída com sucesso"
                })
                
    except Exception as e:
        print(f"Erro ao excluir rua: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/estoque_local/rua/<int:rua_id>/mover", methods=["PUT"])
def mover_rua(rua_id):
    """Move uma rua para uma tag diferente."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    data = request.get_json()
    tag_id = data.get("tag_id")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar se a rua existe
                cursor.execute("SELECT nome FROM ruas WHERE id = %s", (rua_id,))
                rua = cursor.fetchone()
                if not rua:
                    return jsonify({"success": False, "message": "Rua não encontrada"}), 404
                
                # Se tag_id foi fornecido, verificar se existe
                if tag_id:
                    cursor.execute("SELECT nome FROM tags WHERE id = %s AND ativo = true", (tag_id,))
                    tag = cursor.fetchone()
                    if not tag:
                        return jsonify({"success": False, "message": "Tag não encontrada"}), 400
                    tag_nome = tag[0]
                else:
                    tag_nome = "sem tag"
                
                # Atualizar a rua
                cursor.execute("UPDATE ruas SET tag_id = %s WHERE id = %s", (tag_id, rua_id))
                conn.commit()
                
                return jsonify({
                    "success": True, 
                    "message": f"Rua '{rua[0]}' movida para '{tag_nome}' com sucesso"
                })
                
    except Exception as e:
        print(f"Erro ao mover rua: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

# ===== ROTAS PARA TAGS =====

@app.route("/estoque_local/tag", methods=["POST"])
def criar_tag():
    """Cria uma nova tag."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    data = request.get_json()
    nome = data.get("nome", "").strip()
    descricao = data.get("descricao", "").strip()
    cor = data.get("cor", "#007bff")
    
    if not nome:
        return jsonify({"success": False, "message": "Nome da tag é obrigatório"}), 400
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar se já existe uma tag com este nome
                cursor.execute("SELECT id FROM tags WHERE nome = %s", (nome,))
                if cursor.fetchone():
                    return jsonify({"success": False, "message": "Já existe uma tag com este nome"}), 400
                
                # Inserir nova tag
                cursor.execute("""
                    INSERT INTO tags (nome, descricao, cor, ativo, data_criacao) 
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                """, (nome, descricao, cor, True, datetime.now()))
                
                tag_id = cursor.fetchone()[0]
                conn.commit()
                
                return jsonify({
                    "success": True, 
                    "message": "Tag criada com sucesso", 
                    "tag_id": tag_id
                })
                
    except Exception as e:
        print(f"Erro ao criar tag: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/estoque_local/tag/<int:tag_id>", methods=["PUT"])
def editar_tag(tag_id):
    """Edita uma tag existente."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    data = request.get_json()
    nome = data.get("nome", "").strip()
    descricao = data.get("descricao", "").strip()
    cor = data.get("cor", "#007bff")
    
    if not nome:
        return jsonify({"success": False, "message": "Nome da tag é obrigatório"}), 400
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar se a tag existe
                cursor.execute("SELECT id FROM tags WHERE id = %s", (tag_id,))
                if not cursor.fetchone():
                    return jsonify({"success": False, "message": "Tag não encontrada"}), 404
                
                # Verificar se já existe outra tag com este nome
                cursor.execute("SELECT id FROM tags WHERE nome = %s AND id != %s", (nome, tag_id))
                if cursor.fetchone():
                    return jsonify({"success": False, "message": "Já existe uma tag com este nome"}), 400
                
                # Atualizar tag
                cursor.execute("""
                    UPDATE tags 
                    SET nome = %s, descricao = %s, cor = %s, data_atualizacao = %s 
                    WHERE id = %s
                """, (nome, descricao, cor, datetime.now(), tag_id))
                
                conn.commit()
                
                return jsonify({
                    "success": True, 
                    "message": "Tag atualizada com sucesso"
                })
                
    except Exception as e:
        print(f"Erro ao editar tag: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/estoque_local/tag/<int:tag_id>", methods=["DELETE"])
def excluir_tag(tag_id):
    """Exclui uma tag (ruas ficam sem tag)."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar se a tag existe
                cursor.execute("SELECT nome FROM tags WHERE id = %s", (tag_id,))
                tag = cursor.fetchone()
                if not tag:
                    return jsonify({"success": False, "message": "Tag não encontrada"}), 404
                
                # Remover associação das ruas com esta tag
                cursor.execute("UPDATE ruas SET tag_id = NULL WHERE tag_id = %s", (tag_id,))
                
                # Excluir a tag
                cursor.execute("DELETE FROM tags WHERE id = %s", (tag_id,))
                
                conn.commit()
                
                return jsonify({
                    "success": True, 
                    "message": f"Tag '{tag[0]}' excluída com sucesso"
                })
                
    except Exception as e:
        print(f"Erro ao excluir tag: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/estoque_local/produto", methods=["POST"])
def adicionar_produto_estoque_route():
    """Adiciona um produto ao estoque."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    data = request.get_json()
    ean = data.get("ean", "").strip()
    nome = data.get("nome", "").strip()
    cor = data.get("cor", "").strip()
    voltagem = data.get("voltagem", "").strip()
    modelo = data.get("modelo", "").strip()
    quantidade = data.get("quantidade", 0)
    rua_id = data.get("rua_id")
    
    if not all([ean, nome, quantidade, rua_id]):
        return jsonify({"success": False, "message": "Dados obrigatórios não fornecidos"}), 400
    
    try:
        quantidade = int(quantidade)
        if quantidade <= 0:
            return jsonify({"success": False, "message": "Quantidade deve ser maior que zero"}), 400
    except ValueError:
        return jsonify({"success": False, "message": "Quantidade deve ser um número válido"}), 400
    
    usuario_id = session.get("usuario_id")
    sucesso, message = adicionar_produto_estoque(ean, nome, cor, voltagem, modelo, quantidade, usuario_id, rua_id)
    
    if sucesso:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 500

@app.route("/estoque_local/produto/<int:produto_id>", methods=["DELETE"])
def excluir_produto_route(produto_id):
    """Exclui um produto."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    if excluir_produto_db(produto_id):
        return jsonify({"success": True, "message": "Produto excluído com sucesso"})
    else:
        return jsonify({"success": False, "message": "Erro ao excluir produto"}), 500

@app.route("/estoque_local/produto/remover_quantidade", methods=["POST"])
def remover_quantidade_produto_route():
    """Remove quantidade de um produto."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    data = request.get_json()
    produto_id = data.get("produto_id")
    quantidade = data.get("quantidade", 1)
    
    if not produto_id:
        return jsonify({"success": False, "message": "ID do produto é obrigatório"}), 400
    
    try:
        quantidade = int(quantidade)
        if quantidade <= 0:
            return jsonify({"success": False, "message": "Quantidade deve ser maior que zero"}), 400
    except ValueError:
        return jsonify({"success": False, "message": "Quantidade deve ser um número válido"}), 400
    
    sucesso, message = remover_quantidade_produto_db(produto_id, quantidade)
    
    if sucesso:
        return jsonify({"success": True, "message": message})
    else:
        return jsonify({"success": False, "message": message}), 500

@app.route("/estoque_local/exportar_excel")
def exportar_estoque_excel():
    """Exporta os dados do estoque para Excel."""
    if not session.get("logado") or not session.get("admin"):
        flash("Acesso negado. Apenas administradores podem acessar esta área.", "error")
        return redirect(url_for("login"))
    
    dados = obter_dados_para_exportacao()
    
    if not dados:
        flash("Não há dados para exportar", "warning")
        return redirect(url_for("estoque_local"))
    
    # Criar DataFrame
    df = pd.DataFrame(dados)
    
    # Criar arquivo Excel em memória
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Estoque Local', index=False)
        
        # Ajustar largura das colunas
        worksheet = writer.sheets['Estoque Local']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    
    # Gerar nome do arquivo com timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"estoque_local_{timestamp}.xlsx"
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

# ===== ROTAS PARA MOVIMENTAÇÕES =====

@app.route("/estoque_local/movimentacoes", methods=["GET"])
def consultar_movimentacoes_route():
    """Consulta movimentações com filtros."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        # Obter parâmetros de filtro
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        usuario_id = request.args.get('usuario_id', type=int)
        tipo_movimentacao = request.args.get('tipo_movimentacao')
        ean = request.args.get('ean')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        print(f"[DEBUG] Consulta movimentações - Filtros: data_inicio={data_inicio}, data_fim={data_fim}, usuario_id={usuario_id}, tipo={tipo_movimentacao}, ean={ean}")
        
        # Calcular offset
        offset = (page - 1) * per_page
        
        # Consultar movimentações
        movimentacoes, total = consultar_movimentacoes(
            data_inicio=data_inicio,
            data_fim=data_fim,
            usuario_id=usuario_id,
            tipo_movimentacao=tipo_movimentacao,
            ean=ean,
            limit=per_page,
            offset=offset
        )
        
        print(f"[DEBUG] Resultado consulta: {len(movimentacoes)} movimentações encontradas, total={total}")
        
        # Formatar datas para exibição
        for mov in movimentacoes:
            if mov['data_movimentacao']:
                mov['data_movimentacao_formatada'] = mov['data_movimentacao'].strftime('%d/%m/%Y %H:%M')
        
        return jsonify({
            "success": True,
            "movimentacoes": movimentacoes,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page
        })
        
    except Exception as e:
        print(f"[DEBUG] Erro ao consultar movimentações: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/estoque_local/movimentacoes/estatisticas", methods=["GET"])
def obter_estatisticas_movimentacao_route():
    """Obtém estatísticas de movimentação."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        # Obter parâmetros de filtro
        data_inicio = request.args.get('data_inicio')
        data_fim = request.args.get('data_fim')
        usuario_id = request.args.get('usuario_id', type=int)
        
        # Obter estatísticas
        estatisticas = obter_estatisticas_movimentacao(
            data_inicio=data_inicio,
            data_fim=data_fim,
            usuario_id=usuario_id
        )
        
        return jsonify({
            "success": True,
            "estatisticas": estatisticas
        })
        
    except Exception as e:
        print(f"Erro ao obter estatísticas: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

def obter_estatisticas_movimentacao_por_usuario(data_inicio_str, data_fim_str ):
    """
    Obtém estatísticas de entrada e saída de produtos por usuário para um período específico.
    data_inicio_str e data_fim_str devem ser strings no formato 'YYYY-MM-DD'.
    """
    print(f"[DEBUG] obter_estatisticas_movimentacao_por_usuario chamada com: data_inicio={data_inicio_str}, data_fim={data_fim_str}")
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                query = """
                    SELECT
                        u.id AS usuario_id,
                        u.nome AS usuario_nome,
                        COALESCE(SUM(CASE WHEN m.tipo_movimentacao = 'ENTRADA' THEN m.quantidade ELSE 0 END), 0) AS total_entrada,
                        COALESCE(SUM(CASE WHEN m.tipo_movimentacao = 'SAIDA' THEN m.quantidade ELSE 0 END), 0) AS total_saida
                    FROM movimentacoes m
                    JOIN usuarios u ON m.usuario_id = u.id
                    WHERE DATE(m.data_movimentacao - INTERVAL '3 hours') >= %s::date
                      AND DATE(m.data_movimentacao - INTERVAL '3 hours') <= %s::date
                    GROUP BY u.id, u.nome
                    HAVING SUM(m.quantidade) > 0 -- Garante que apenas usuários com movimentação no período apareçam
                    ORDER BY u.nome;
                """
                cursor.execute(query, (data_inicio_str, data_fim_str))
                resultados = cursor.fetchall()
                print(f"[DEBUG] Estatísticas por usuário encontradas: {len(resultados)}")
                return [dict(row) for row in resultados]
    except Exception as e:
        print(f"[DEBUG] Erro ao obter estatísticas de movimentação por usuário: {e}")
        return []


@app.route("/api/estoque_local/movimentacoes/estatisticas_por_usuario", methods=["GET"])
def api_estatisticas_movimentacao_por_usuario():
    """API para obter estatísticas de entrada e saída por usuário para um período."""
    print(f"[DEBUG] api_estatisticas_movimentacao_por_usuario CHAMADA!")
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403

    data_inicio = request.args.get("data_inicio")
    data_fim = request.args.get("data_fim")

    if not data_inicio or not data_fim:
        return jsonify({"success": False, "message": "Parâmetros data_inicio e data_fim são obrigatórios."}), 400

    try:
        datetime.strptime(data_inicio, '%Y-%m-%d')
        datetime.strptime(data_fim, '%Y-%m-%d')
    except ValueError:
        return jsonify({"success": False, "message": "Formato de data inválido. Use YYYY-MM-DD."}), 400

    try:
        estatisticas = obter_estatisticas_movimentacao_por_usuario(data_inicio, data_fim)
        return jsonify({"success": True, "estatisticas": estatisticas}), 200
    except Exception as e:
        print(f"[DEBUG] Erro interno na API de estatísticas por usuário: {e}")
        return jsonify({"success": False, "message": f"Erro interno do servidor: {str(e)}"}), 500


@app.route("/estoque_local/movimentacoes/registrar", methods=["POST"])
def registrar_movimentacao_manual():
    """Registra uma movimentação manual."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        data = request.get_json()
        
        # Validar dados obrigatórios
        required_fields = ['tipo_movimentacao', 'ean', 'nome_produto', 'quantidade']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"success": False, "message": f"Campo {field} é obrigatório"}), 400
        
        # Registrar movimentação
        sucesso = registrar_movimentacao(
            tipo_movimentacao=data['tipo_movimentacao'],
            ean=data['ean'],
            nome_produto=data['nome_produto'],
            cor=data.get('cor'),
            voltagem=data.get('voltagem'),
            modelo=data.get('modelo'),
            quantidade=data['quantidade'],
            usuario_id=session.get('usuario_id'),
            rua_origem_id=data.get('rua_origem_id'),
            rua_destino_id=data.get('rua_destino_id'),
            observacoes=data.get('observacoes')
        )
        
        if sucesso:
            return jsonify({"success": True, "message": "Movimentação registrada com sucesso"})
        else:
            return jsonify({"success": False, "message": "Erro ao registrar movimentação"}), 500
            
    except Exception as e:
        print(f"Erro ao registrar movimentação manual: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/estoque_local/usuarios", methods=["GET"])
def listar_usuarios_estoque():
    """Lista usuários para filtros de movimentação."""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("SELECT id, nome FROM usuarios WHERE admin = 0 ORDER BY nome")
                usuarios = cursor.fetchall()
                
                return jsonify({
                    "success": True,
                    "usuarios": [dict(usuario) for usuario in usuarios]
                })
                
    except Exception as e:
        print(f"Erro ao listar usuários: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500




# ============================================================================
# SISTEMA DE GERENCIAMENTO DE USUÁRIOS
# ============================================================================

# ============================================================================
# ROTA PRINCIPAL DO PAINEL
# ============================================================================

@app.route("/gerenciar_usuarios")
def gerenciar_usuarios():
    """Página do painel de gerenciamento de usuários"""
    if not session.get("logado"):
        return redirect("/")
    
    # Verificar se é administrador
    if not session.get("admin"):
        flash("Acesso negado. Apenas administradores podem gerenciar usuários.", "error")
        return redirect("/admin")
    
    return render_template("gerenciar_usuarios.html")

# ============================================================================
# APIs PARA GERENCIAMENTO DE USUÁRIOS
# ============================================================================

@app.route("/api/dev/usuarios", methods=["GET"])
def api_listar_usuarios():
    """Listar todos os usuários do sistema"""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT id, nome, admin
                    FROM usuarios
                    ORDER BY nome
                """)
                
                usuarios = []
                for row in cursor.fetchall():
                    usuario = dict(row)
                    
                    # Mapear admin para permissões para compatibilidade
                    if usuario['admin']:
                        usuario['permissoes'] = {
                            'admin_acesso': True,
                            'dev_acesso': True,
                            'dev_usuarios': True,
                            'estoque_acesso': True,
                            'estoque_consulta': True,
                            'estoque_entrada': True,
                            'estoque_saida': True,
                            'cadastro_acesso': True,
                            'cadastro_consulta': True,
                            'cadastro_envio': True
                        }
                    else:
                        usuario['permissoes'] = {
                            'estoque_acesso': True,
                            'estoque_consulta': True,
                            'estoque_entrada': True,
                            'estoque_saida': True
                        }
                    
                    usuarios.append(usuario)
                
        return jsonify({"success": True, "usuarios": usuarios})
    except Exception as e:
        print(f"Erro ao listar usuários: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/api/dev/usuarios/<int:usuario_id>", methods=["GET"])
def api_obter_usuario(usuario_id):
    """Obter dados de um usuário específico"""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT id, nome, admin
                    FROM usuarios
                    WHERE id = %s
                """, (usuario_id,))
                
                row = cursor.fetchone()
                if row:
                    usuario = dict(row)
                    
                    # Mapear admin para permissões
                    if usuario['admin']:
                        usuario['permissoes'] = {
                            'admin_acesso': True,
                            'dev_acesso': True,
                            'dev_usuarios': True,
                            'estoque_acesso': True,
                            'estoque_consulta': True,
                            'estoque_entrada': True,
                            'estoque_saida': True,
                            'cadastro_acesso': True,
                            'cadastro_consulta': True,
                            'cadastro_envio': True
                        }
                    else:
                        usuario['permissoes'] = {
                            'estoque_acesso': True,
                            'estoque_consulta': True,
                            'estoque_entrada': True,
                            'estoque_saida': True
                        }
                    
                    return jsonify({"success": True, "usuario": usuario})
                else:
                    return jsonify({"success": False, "message": "Usuário não encontrado"}), 404
    except Exception as e:
        print(f"Erro ao obter usuário: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/api/dev/usuarios", methods=["POST"])
def api_criar_usuario():
    """Criar novo usuário"""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        data = request.get_json()
        nome = data.get("nome", "").strip()
        senha = data.get("senha", "").strip()
        tipo = data.get("tipo", "").strip()
        ativo = data.get("ativo", True)
        
        if not nome or not senha:
            return jsonify({"success": False, "message": "Nome e senha são obrigatórios"}), 400
        
        if not tipo or tipo not in TIPOS_USUARIO:
            return jsonify({"success": False, "message": "Tipo de usuário inválido"}), 400
        
        # Validar dados
        if len(nome) < 3:
            return jsonify({"success": False, "message": "Nome deve ter pelo menos 3 caracteres"}), 400
        
        if len(senha) < 4:
            return jsonify({"success": False, "message": "Senha deve ter pelo menos 4 caracteres"}), 400
        
        # Verificar se usuário já existe
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM usuarios WHERE nome = %s", (nome,))
                if cursor.fetchone():
                    return jsonify({"success": False, "message": "Usuário já existe"}), 400
                
                # Converter tipo para flag admin
                is_admin = obter_admin_por_tipo(tipo)
                
                # Criar usuário
                senha_hash = generate_password_hash(senha)
                cursor.execute("""
                    INSERT INTO usuarios (nome, senha_hash, admin)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (nome, senha_hash, is_admin))
                
                usuario_id = cursor.fetchone()[0]
                conn.commit()
                
                # Log da ação
                print(f"Usuário '{nome}' criado por {session.get('nome')} (ID: {session.get('usuario_id')})")
                
        return jsonify({"success": True, "message": "Usuário criado com sucesso", "usuario_id": usuario_id})
    except Exception as e:
        print(f"Erro ao criar usuário: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/api/dev/usuarios/<int:usuario_id>", methods=["PUT"])
def api_atualizar_usuario(usuario_id):
    """Atualizar usuário existente"""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        data = request.get_json()
        nome = data.get("nome", "").strip()
        senha = data.get("senha", "").strip()
        tipo = data.get("tipo", "").strip()
        ativo = data.get("ativo", True)
        
        if not nome:
            return jsonify({"success": False, "message": "Nome é obrigatório"}), 400
        
        if not tipo or tipo not in TIPOS_USUARIO:
            return jsonify({"success": False, "message": "Tipo de usuário inválido"}), 400
        
        if len(nome) < 3:
            return jsonify({"success": False, "message": "Nome deve ter pelo menos 3 caracteres"}), 400
        
        if senha and len(senha) < 4:
            return jsonify({"success": False, "message": "Senha deve ter pelo menos 4 caracteres"}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar se usuário existe
                cursor.execute("SELECT nome FROM usuarios WHERE id = %s", (usuario_id,))
                usuario_atual = cursor.fetchone()
                if not usuario_atual:
                    return jsonify({"success": False, "message": "Usuário não encontrado"}), 404
                
                # Verificar se novo nome já existe (exceto para o próprio usuário)
                cursor.execute("SELECT id FROM usuarios WHERE nome = %s AND id != %s", (nome, usuario_id))
                if cursor.fetchone():
                    return jsonify({"success": False, "message": "Nome de usuário já existe"}), 400
                
                # Converter tipo para flag admin
                is_admin = obter_admin_por_tipo(tipo)
                
                # Atualizar usuário
                if senha:
                    senha_hash = generate_password_hash(senha)
                    cursor.execute("""
                        UPDATE usuarios 
                        SET nome = %s, senha_hash = %s, admin = %s
                        WHERE id = %s
                    """, (nome, senha_hash, is_admin, usuario_id))
                else:
                    cursor.execute("""
                        UPDATE usuarios 
                        SET nome = %s, admin = %s
                        WHERE id = %s
                    """, (nome, is_admin, usuario_id))
                
                conn.commit()
                
                # Atualizar sessão se for o próprio usuário
                if usuario_id == session.get("usuario_id"):
                    session["nome"] = nome
                    session["admin"] = is_admin
                
                # Log da ação
                print(f"Usuário '{nome}' (ID: {usuario_id}) atualizado por {session.get('nome')} (ID: {session.get('usuario_id')})")
                
        return jsonify({"success": True, "message": "Usuário atualizado com sucesso"})
    except Exception as e:
        print(f"Erro ao atualizar usuário: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/api/dev/usuarios/<int:usuario_id>", methods=["DELETE"])
def api_excluir_usuario(usuario_id):
    """Excluir usuário"""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        # Não permitir excluir o próprio usuário
        if usuario_id == session.get("usuario_id"):
            return jsonify({"success": False, "message": "Não é possível excluir seu próprio usuário"}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar se usuário existe
                cursor.execute("SELECT nome FROM usuarios WHERE id = %s", (usuario_id,))
                usuario = cursor.fetchone()
                if not usuario:
                    return jsonify({"success": False, "message": "Usuário não encontrado"}), 404
                
                # Verificar se há produtos associados ao usuário
                cursor.execute("SELECT COUNT(*) FROM produtos WHERE usuario_id = %s", (usuario_id,))
                count_produtos = cursor.fetchone()[0]
                
                if count_produtos > 0:
                    return jsonify({
                        "success": False, 
                        "message": f"Não é possível excluir o usuário '{usuario[0]}' pois há {count_produtos} produto(s) associado(s) a ele"
                    }), 400
                
                # Excluir usuário
                cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
                conn.commit()
                
                # Log da ação
                print(f"Usuário '{usuario[0]}' excluído por {session.get('nome')} (ID: {session.get('usuario_id')})")
                
        return jsonify({"success": True, "message": f"Usuário '{usuario[0]}' excluído com sucesso"})
    except Exception as e:
        print(f"Erro ao excluir usuário: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/api/usuarios", methods=["GET"])
def api_usuarios():
    """
    Retorna lista de usuários com admin = 0 para filtros.
    Usado no painel de estoque local para filtrar movimentações por usuário.
    """
    if not session.get("logado"):
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Buscar apenas usuários não-admin (admin = 0)
                cursor.execute("""
                    SELECT id, nome
                    FROM usuarios
                    WHERE admin = 0
                    ORDER BY nome ASC
                """)
                
                usuarios = []
                for row in cursor.fetchall():
                    usuarios.append({
                        "id": row["id"],
                        "nome": row["nome"]
                        
                    })
                
                return jsonify(usuarios)
                
    except psycopg2.Error as e:
        print(f"Erro ao buscar usuários: {e}")
        return jsonify({"error": "Erro no banco de dados"}), 500


# ============================================================================
# ROTAS DE NAVEGAÇÃO E COMPATIBILIDADE
# ============================================================================

@app.route("/admin/usuarios")
def admin_usuarios_redirect():
    """Redirecionar rota antiga para nova"""
    return redirect("/gerenciar_usuarios")

# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def mapear_tipo_para_permissoes(tipo):
    """Mapeia tipo de usuário para permissões"""
    permissoes_map = {
        'Consulta EAN': {
            'estoque_acesso': True,
            'estoque_consulta': True,
            'estoque_entrada': True,
            'estoque_saida': True
        },
        'Painel de Listas': {
            'cadastro_acesso': True,
            'cadastro_consulta': True,
            'cadastro_envio': True
        },
        'Administrador': {
            'admin_acesso': True,
            'dev_acesso': True,
            'dev_usuarios': True,
            'estoque_acesso': True,
            'estoque_consulta': True,
            'estoque_entrada': True,
            'estoque_saida': True,
            'cadastro_acesso': True,
            'cadastro_consulta': True,
            'cadastro_envio': True
        }
    }
    
    return permissoes_map.get(tipo, {})

def mapear_permissoes_para_tipo(permissoes):
    """Mapeia permissões para tipo de usuário"""
    if not permissoes:
        return 'Consulta EAN'
    
    if permissoes.get('admin_acesso') or permissoes.get('dev_acesso'):
        return 'Administrador'
    elif permissoes.get('cadastro_acesso'):
        return 'Painel de Listas'
    else:
        return 'Consulta EAN'

# ============================================================================
# CORREÇÃO DA API CONSULTA_EAN PARA ESTOQUE
# ============================================================================

@app.route("/api/consulta_ean_corrigida")
def api_consulta_ean_corrigida():
    """Consulta EAN corrigida para mostrar localização das ruas"""
    ean = request.args.get("ean")
    if not ean:
        return jsonify({"success": False, "message": "EAN não fornecido."}), 400

    if not session.get("logado"):
        return jsonify({"success": False, "message": "Usuário não está logado"}), 401

    usuario_id = session.get("usuario_id")
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Buscar produto com informações da rua
                cursor.execute("""
                    SELECT p.ean, p.nome, p.cor, p.voltagem, p.modelo,
                           SUM(p.quantidade) as quantidade_total,
                           STRING_AGG(DISTINCT r.nome_rua, ', ') as ruas,
                           COUNT(DISTINCT p.rua_id) as total_ruas
                    FROM produtos p 
                    LEFT JOIN ruas r ON p.rua_id = r.id 
                    WHERE p.ean = %s AND p.usuario_id = %s
                    GROUP BY p.ean, p.nome, p.cor, p.voltagem, p.modelo
                """, (ean, usuario_id))
                
                produto = cursor.fetchone()
                if produto:
                    produto_dict = dict(produto)
                    
                    # Formatar informação da rua
                    if produto_dict['ruas']:
                        if produto_dict['total_ruas'] == 1:
                            produto_dict['rua'] = produto_dict['ruas']
                        else:
                            produto_dict['rua'] = f"Múltiplas ruas: {produto_dict['ruas']}"
                    else:
                        produto_dict['rua'] = "Não especificada"
                    
                    produto_dict['quantidade'] = produto_dict['quantidade_total']
                    
                    return jsonify({"success": True, "produto": produto_dict}), 200
                else:
                    return jsonify({"success": False, "message": "Produto não encontrado no estoque."}), 404
                    
    except Exception as e:
        print(f"Erro ao consultar produto: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500


# ===== APIs DO PAINEL STAND-BY =====

@app.route("/api/listas_standby", methods=["GET"])
def api_listas_standby():
    """API para carregar listas em stand-by"""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Buscar listas em stand-by que ainda têm produtos
                cursor.execute("""
                    SELECT ls.id, ls.usuario_id, ls.data_envio, u.nome as usuario_nome
                    FROM listas_standby ls
                    INNER JOIN usuarios u ON ls.usuario_id = u.id
                    WHERE EXISTS (
                        SELECT 1 FROM produtos_standby ps 
                        WHERE ps.lista_standby_id = ls.id
                    )
                    ORDER BY ls.data_envio DESC
                """)
                
                listas = []
                for row in cursor.fetchall():
                    lista = dict(row)
                    
                    # Buscar produtos da lista
                    cursor.execute("""
                        SELECT ean, nome, cor, voltagem, modelo, quantidade
                        FROM produtos_standby
                        WHERE lista_standby_id = %s
                        ORDER BY nome
                    """, (lista['id'],))
                    
                    lista['produtos'] = [dict(produto) for produto in cursor.fetchall()]
                    listas.append(lista)
                
                return jsonify({"success": True, "listas": listas}), 200
                
    except Exception as e:
        print(f"Erro ao carregar listas stand-by: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/api/retirar_lista_standby", methods=["POST"])
def api_retirar_lista_standby():
    """API para retirar lista do stand-by"""
    if not session.get("logado") or not session.get("admin"):
        return jsonify({"success": False, "message": "Acesso negado"}), 403
    
    try:
        data = request.get_json()
        lista_id = data.get("lista_id")
        
        if not lista_id:
            return jsonify({"success": False, "message": "ID da lista não fornecido"}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar se a lista existe
                cursor.execute("SELECT id FROM listas_standby WHERE id = %s", (lista_id,))
                if not cursor.fetchone():
                    return jsonify({"success": False, "message": "Lista não encontrada"}), 404
                
                # Remover produtos da lista
                cursor.execute("DELETE FROM produtos_standby WHERE lista_standby_id = %s", (lista_id,))
                
                # Remover lista
                cursor.execute("DELETE FROM listas_standby WHERE id = %s", (lista_id,))
                
                conn.commit()
                
                return jsonify({"success": True, "message": "Lista retirada do stand-by com sucesso"}), 200
                
    except Exception as e:
        print(f"Erro ao retirar lista do stand-by: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

@app.route("/api/enviar_para_standby", methods=["POST"])
def api_enviar_para_standby():
    """API para enviar lista para stand-by (modificação da função de envio original)"""
    if not session.get("logado"):
        return jsonify({"success": False, "message": "Usuário não está logado"}), 401
    
    try:
        usuario_id = session.get("usuario_id")
        
        # Carregar produtos não enviados do usuário
        produtos = carregar_produtos_usuario(usuario_id, apenas_nao_enviados=True)
        
        if not produtos:
            return jsonify({"success": False, "message": "Nenhum produto para enviar"}), 400
        
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Criar entrada na tabela listas_standby
                cursor.execute("""
                    INSERT INTO listas_standby (usuario_id, data_envio)
                    VALUES (%s, %s)
                    RETURNING id
                """, (usuario_id, datetime.now()))
                
                lista_standby_id = cursor.fetchone()[0]
                
                # Copiar produtos para produtos_standby
                for produto in produtos:
                    cursor.execute("""
                        INSERT INTO produtos_standby (lista_standby_id, ean, nome, cor, voltagem, modelo, quantidade)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        lista_standby_id,
                        produto['ean'],
                        produto['nome'],
                        produto['cor'],
                        produto['voltagem'],
                        produto['modelo'],
                        produto['quantidade']
                    ))
                
                # Marcar produtos originais como enviados
                cursor.execute("""
                    UPDATE produtos 
                    SET enviado = 1, timestamp_envio = %s 
                    WHERE usuario_id = %s AND enviado = 0 AND rua_id IS NULL
                """, (datetime.now(), usuario_id))
                
                conn.commit()
                
                return jsonify({
                    "success": True, 
                    "message": f"Lista com {len(produtos)} produto(s) enviada para stand-by com sucesso!",
                    "lista_id": lista_standby_id
                }), 200
                
    except Exception as e:
        print(f"Erro ao enviar para stand-by: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500



# ===== FUNÇÕES AUXILIARES PARA SISTEMA DE TAGS =====

def obter_estoque_por_tag():
    """Obtém o estoque organizado por tags."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                # Buscar tags ativas
                cursor.execute("""
                    SELECT id, nome, descricao, cor 
                    FROM tags 
                    WHERE ativo = true 
                    ORDER BY nome
                """)
                tags = cursor.fetchall()
                
                estoque_por_tag = {}
                
                for tag in tags:
                    tag_id = tag['id']
                    
                    # Buscar ruas desta tag
                    cursor.execute("""
                        SELECT r.id, r.nome, r.descricao
                        FROM ruas r
                        WHERE r.tag_id = %s AND r.ativa = true
                        ORDER BY r.nome
                    """, (tag_id,))
                    ruas = cursor.fetchall()
                    
                    ruas_data = []
                    for rua in ruas:
                        rua_id = rua['id']
                        
                        # Buscar produtos desta rua
                        cursor.execute("""
                            SELECT p.id, p.ean, p.nome, p.cor, 
                                   p.voltagem, p.modelo, p.quantidade
                            FROM produtos p
                            WHERE p.rua_id = %s AND p.ativo = true
                            ORDER BY p.nome
                        """, (rua_id,))
                        produtos = cursor.fetchall()
                        
                        ruas_data.append({
                            'rua_info': dict(rua),
                            'produtos': [dict(p) for p in produtos]
                        })
                    
                    estoque_por_tag[tag_id] = {
                        'tag_info': dict(tag),
                        'ruas': ruas_data
                    }
                
                return estoque_por_tag
                
    except Exception as e:
        print(f"Erro ao obter estoque por tag: {e}")
        return {}

def obter_ruas_sem_tag():
    """Obtém ruas que não estão associadas a nenhuma tag."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT id, nome, descricao
                    FROM ruas
                    WHERE tag_id IS NULL AND ativa = true
                    ORDER BY nome
                """)
                return [dict(rua) for rua in cursor.fetchall()]
                
    except Exception as e:
        print(f"Erro ao obter ruas sem tag: {e}")
        return []

def obter_tags_ativas():
    """Obtém todas as tags ativas."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute("""
                    SELECT id, nome, descricao, cor
                    FROM tags
                    WHERE ativo = true
                    ORDER BY nome
                """)
                return [dict(tag) for tag in cursor.fetchall()]
                
    except Exception as e:
        print(f"Erro ao obter tags ativas: {e}")
        return []
