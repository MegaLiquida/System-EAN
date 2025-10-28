"""
Gerenciamento de Pool de Conexões ao Banco de Dados PostgreSQL
Implementa pool de conexões para melhor performance e gerenciamento de recursos
"""
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
import logging
import os

logger = logging.getLogger(__name__)

# Pool de conexões global
connection_pool = None


def init_connection_pool(min_conn=5, max_conn=20, database_url=None):
    """
    Inicializa o pool de conexões ao banco de dados
    
    Args:
        min_conn: Número mínimo de conexões no pool
        max_conn: Número máximo de conexões no pool
        database_url: URL de conexão ao banco (se None, usa variável de ambiente)
    
    Returns:
        Pool de conexões criado
    
    Raises:
        ValueError: Se database_url não for fornecida e DATABASE_URL não estiver definida
        psycopg2.Error: Se houver erro ao criar o pool
    """
    global connection_pool
    
    if database_url is None:
        database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL não definida. Configure a variável de ambiente.")
    
    try:
        connection_pool = pool.ThreadedConnectionPool(
            minconn=min_conn,
            maxconn=max_conn,
            dsn=database_url
        )
        
        logger.info(f"Pool de conexões criado: min={min_conn}, max={max_conn}")
        return connection_pool
        
    except psycopg2.Error as e:
        logger.error(f"Erro ao criar pool de conexões: {e}")
        raise


def get_db_connection():
    """
    Obtém uma conexão do pool
    
    Returns:
        Conexão ao banco de dados
    
    Raises:
        RuntimeError: Se o pool não foi inicializado
        psycopg2.Error: Se houver erro ao obter conexão
    """
    global connection_pool
    
    if connection_pool is None:
        raise RuntimeError("Pool de conexões não foi inicializado. Chame init_connection_pool() primeiro.")
    
    try:
        conn = connection_pool.getconn()
        
        if conn:
            logger.debug("Conexão obtida do pool")
            return conn
        else:
            raise psycopg2.Error("Não foi possível obter conexão do pool")
            
    except psycopg2.Error as e:
        logger.error(f"Erro ao obter conexão: {e}")
        raise


def release_db_connection(conn):
    """
    Devolve uma conexão ao pool
    
    Args:
        conn: Conexão a ser devolvida ao pool
    """
    global connection_pool
    
    if connection_pool and conn:
        try:
            connection_pool.putconn(conn)
            logger.debug("Conexão devolvida ao pool")
        except psycopg2.Error as e:
            logger.error(f"Erro ao devolver conexão: {e}")


@contextmanager
def get_db():
    """
    Context manager para uso seguro de conexões ao banco
    
    Uso:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tabela")
            # ...
    
    A conexão é automaticamente devolvida ao pool ao sair do contexto.
    Em caso de exceção, faz rollback automático.
    """
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Erro na transação, rollback executado: {e}")
        raise
    finally:
        release_db_connection(conn)


def close_connection_pool():
    """
    Fecha todas as conexões do pool
    Deve ser chamado ao encerrar a aplicação
    """
    global connection_pool
    
    if connection_pool:
        try:
            connection_pool.closeall()
            logger.info("Pool de conexões fechado")
            connection_pool = None
        except psycopg2.Error as e:
            logger.error(f"Erro ao fechar pool: {e}")


def get_pool_status():
    """
    Retorna informações sobre o status do pool
    
    Returns:
        dict: Dicionário com informações do pool
    """
    global connection_pool
    
    if connection_pool is None:
        return {
            'initialized': False,
            'message': 'Pool não inicializado'
        }
    
    # ThreadedConnectionPool não expõe estatísticas detalhadas
    # mas podemos verificar se está funcional
    try:
        # Tenta obter e devolver uma conexão para verificar saúde
        test_conn = connection_pool.getconn()
        if test_conn:
            connection_pool.putconn(test_conn)
            return {
                'initialized': True,
                'healthy': True,
                'message': 'Pool funcionando corretamente'
            }
    except Exception as e:
        return {
            'initialized': True,
            'healthy': False,
            'error': str(e)
        }


# Funções auxiliares para compatibilidade com código existente

def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    """
    Executa uma query SQL de forma simplificada
    
    Args:
        query: Query SQL a ser executada
        params: Parâmetros da query (tuple ou dict)
        fetch_one: Se True, retorna apenas um resultado
        fetch_all: Se True, retorna todos os resultados
    
    Returns:
        Resultado da query ou None
    """
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if fetch_one:
            return cursor.fetchone()
        elif fetch_all:
            return cursor.fetchall()
        else:
            return cursor.rowcount


def execute_query_dict(query, params=None, fetch_one=False, fetch_all=False):
    """
    Executa uma query SQL retornando resultados como dicionários
    
    Args:
        query: Query SQL a ser executada
        params: Parâmetros da query (tuple ou dict)
        fetch_one: Se True, retorna apenas um resultado
        fetch_all: Se True, retorna todos os resultados
    
    Returns:
        Resultado da query como dict ou lista de dicts
    """
    with get_db() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(query, params)
        
        if fetch_one:
            result = cursor.fetchone()
            return dict(result) if result else None
        elif fetch_all:
            results = cursor.fetchall()
            return [dict(row) for row in results]
        else:
            return cursor.rowcount

