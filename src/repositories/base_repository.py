"""
Repositório Base
Fornece operações CRUD genéricas para todos os repositórios
"""
import psycopg2
import psycopg2.extras
from src.extensions.database import get_db
import logging

logger = logging.getLogger(__name__)


class BaseRepository:
    """
    Classe base para repositórios
    Fornece métodos CRUD genéricos que podem ser reutilizados
    """
    
    def __init__(self, table_name):
        """
        Inicializa o repositório
        
        Args:
            table_name: Nome da tabela no banco de dados
        """
        self.table_name = table_name
    
    def find_all(self, order_by=None, limit=None):
        """
        Busca todos os registros da tabela
        
        Args:
            order_by: Coluna para ordenação (ex: 'id DESC')
            limit: Limite de registros a retornar
        
        Returns:
            Lista de registros como dicionários
        """
        query = f"SELECT * FROM {self.table_name}"
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        try:
            with get_db() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute(query)
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except psycopg2.Error as e:
            logger.error(f"Erro ao buscar todos os registros de {self.table_name}: {e}")
            raise
    
    def find_by_id(self, record_id):
        """
        Busca um registro por ID
        
        Args:
            record_id: ID do registro
        
        Returns:
            Registro como dicionário ou None se não encontrado
        """
        query = f"SELECT * FROM {self.table_name} WHERE id = %s"
        
        try:
            with get_db() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute(query, (record_id,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except psycopg2.Error as e:
            logger.error(f"Erro ao buscar registro {record_id} de {self.table_name}: {e}")
            raise
    
    def find_by_field(self, field_name, field_value):
        """
        Busca registros por um campo específico
        
        Args:
            field_name: Nome do campo
            field_value: Valor do campo
        
        Returns:
            Lista de registros como dicionários
        """
        query = f"SELECT * FROM {self.table_name} WHERE {field_name} = %s"
        
        try:
            with get_db() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute(query, (field_value,))
                results = cursor.fetchall()
                return [dict(row) for row in results]
        except psycopg2.Error as e:
            logger.error(f"Erro ao buscar por {field_name}={field_value} em {self.table_name}: {e}")
            raise
    
    def find_one_by_field(self, field_name, field_value):
        """
        Busca um único registro por um campo específico
        
        Args:
            field_name: Nome do campo
            field_value: Valor do campo
        
        Returns:
            Registro como dicionário ou None se não encontrado
        """
        query = f"SELECT * FROM {self.table_name} WHERE {field_name} = %s LIMIT 1"
        
        try:
            with get_db() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute(query, (field_value,))
                result = cursor.fetchone()
                return dict(result) if result else None
        except psycopg2.Error as e:
            logger.error(f"Erro ao buscar por {field_name}={field_value} em {self.table_name}: {e}")
            raise
    
    def create(self, data):
        """
        Cria um novo registro
        
        Args:
            data: Dicionário com os dados do registro
        
        Returns:
            ID do registro criado
        """
        fields = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO {self.table_name} ({fields}) VALUES ({placeholders}) RETURNING id"
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(data.values()))
                record_id = cursor.fetchone()[0]
                logger.info(f"Registro criado em {self.table_name} com ID {record_id}")
                return record_id
        except psycopg2.Error as e:
            logger.error(f"Erro ao criar registro em {self.table_name}: {e}")
            raise
    
    def update(self, record_id, data):
        """
        Atualiza um registro existente
        
        Args:
            record_id: ID do registro a atualizar
            data: Dicionário com os dados a atualizar
        
        Returns:
            Número de registros atualizados
        """
        set_clause = ', '.join([f"{key} = %s" for key in data.keys()])
        query = f"UPDATE {self.table_name} SET {set_clause} WHERE id = %s"
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, tuple(data.values()) + (record_id,))
                rowcount = cursor.rowcount
                logger.info(f"Registro {record_id} atualizado em {self.table_name}")
                return rowcount
        except psycopg2.Error as e:
            logger.error(f"Erro ao atualizar registro {record_id} em {self.table_name}: {e}")
            raise
    
    def delete(self, record_id):
        """
        Deleta um registro
        
        Args:
            record_id: ID do registro a deletar
        
        Returns:
            Número de registros deletados
        """
        query = f"DELETE FROM {self.table_name} WHERE id = %s"
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (record_id,))
                rowcount = cursor.rowcount
                logger.info(f"Registro {record_id} deletado de {self.table_name}")
                return rowcount
        except psycopg2.Error as e:
            logger.error(f"Erro ao deletar registro {record_id} de {self.table_name}: {e}")
            raise
    
    def count(self, where_clause=None, params=None):
        """
        Conta registros na tabela
        
        Args:
            where_clause: Cláusula WHERE opcional (ex: "ativo = %s")
            params: Parâmetros para a cláusula WHERE
        
        Returns:
            Número de registros
        """
        query = f"SELECT COUNT(*) FROM {self.table_name}"
        
        if where_clause:
            query += f" WHERE {where_clause}"
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                return cursor.fetchone()[0]
        except psycopg2.Error as e:
            logger.error(f"Erro ao contar registros em {self.table_name}: {e}")
            raise
    
    def execute_custom_query(self, query, params=None, fetch_one=False, fetch_all=False):
        """
        Executa uma query customizada
        
        Args:
            query: Query SQL a executar
            params: Parâmetros da query
            fetch_one: Se True, retorna apenas um resultado
            fetch_all: Se True, retorna todos os resultados
        
        Returns:
            Resultado da query
        """
        try:
            with get_db() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute(query, params or ())
                
                if fetch_one:
                    result = cursor.fetchone()
                    return dict(result) if result else None
                elif fetch_all:
                    results = cursor.fetchall()
                    return [dict(row) for row in results]
                else:
                    return cursor.rowcount
        except psycopg2.Error as e:
            logger.error(f"Erro ao executar query customizada: {e}")
            raise

