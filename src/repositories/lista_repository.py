"""
Repositório de Listas
Gerencia listas de produtos (standby, loja, manutenção, unificadas)
"""
import psycopg2
import psycopg2.extras
from datetime import datetime
from src.repositories.base_repository import BaseRepository
from src.extensions.database import get_db
import logging

logger = logging.getLogger(__name__)


class ListaRepository(BaseRepository):
    """Repositório para gerenciar listas de produtos"""
    
    def __init__(self):
        super().__init__('listas_standby')  # Tabela padrão
    
    # ========== LISTAS STANDBY ==========
    
    def criar_lista_standby(self, usuario_id, data_envio, responsavel_id, pin):
        """
        Cria uma nova lista standby
        
        Args:
            usuario_id: ID do usuário
            data_envio: Data de envio
            responsavel_id: ID do responsável
            pin: PIN do responsável
        
        Returns:
            ID da lista criada
        """
        try:
            query = """
                INSERT INTO listas_standby (usuario_id, data_envio, responsavel_id, responsavel_pin)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (usuario_id, data_envio, responsavel_id, pin))
                lista_id = cursor.fetchone()[0]
                
                logger.info(f"Lista standby criada: ID {lista_id}")
                return lista_id
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao criar lista standby: {e}")
            raise
    
    def adicionar_produto_standby(self, lista_id, produto):
        """
        Adiciona produto à lista standby
        
        Args:
            lista_id: ID da lista
            produto: Dicionário com dados do produto
        
        Returns:
            ID do produto adicionado
        """
        try:
            query = """
                INSERT INTO produtos_standby (lista_standby_id, ean, nome, cor, voltagem, modelo, quantidade)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    lista_id,
                    produto['ean'],
                    produto.get('nome'),
                    produto.get('cor'),
                    produto.get('voltagem'),
                    produto.get('modelo'),
                    produto['quantidade']
                ))
                produto_id = cursor.fetchone()[0]
                
                return produto_id
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao adicionar produto à lista standby: {e}")
            raise
    
    def listar_listas_standby(self):
        """
        Lista todas as listas standby com informações do usuário
        
        Returns:
            Lista de listas standby
        """
        query = """
            SELECT ls.*, u.nome as usuario_nome
            FROM listas_standby ls
            INNER JOIN usuarios u ON ls.usuario_id = u.id
            WHERE EXISTS (
                SELECT 1 FROM produtos_standby ps 
                WHERE ps.lista_standby_id = ls.id
            )
            ORDER BY ls.data_envio DESC
        """
        
        return self.execute_custom_query(query, fetch_all=True)
    
    def obter_produtos_standby(self, lista_id):
        """
        Obtém produtos de uma lista standby
        
        Args:
            lista_id: ID da lista
        
        Returns:
            Lista de produtos
        """
        query = """
            SELECT * FROM produtos_standby 
            WHERE lista_standby_id = %s
            ORDER BY nome
        """
        
        return self.execute_custom_query(query, (lista_id,), fetch_all=True)
    
    def deletar_lista_standby(self, lista_id):
        """
        Deleta uma lista standby e seus produtos
        
        Args:
            lista_id: ID da lista
        
        Returns:
            True se deletada, False caso contrário
        """
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Deletar produtos
                cursor.execute("DELETE FROM produtos_standby WHERE lista_standby_id = %s", (lista_id,))
                
                # Deletar lista
                cursor.execute("DELETE FROM listas_standby WHERE id = %s", (lista_id,))
                
                logger.info(f"Lista standby {lista_id} deletada")
                return True
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao deletar lista standby: {e}")
            return False
    
    def buscar_produto_standby_por_ean(self, ean):
        """
        Busca produto no standby por EAN
        
        Args:
            ean: Código EAN
        
        Returns:
            Produto standby ou None
        """
        query = """
            SELECT id, quantidade FROM produtos_standby 
            WHERE ean = %s 
            ORDER BY id 
            LIMIT 1
        """
        
        return self.execute_custom_query(query, (ean,), fetch_one=True)
    
    def atualizar_quantidade_standby(self, produto_id, nova_quantidade):
        """
        Atualiza quantidade de produto no standby
        
        Args:
            produto_id: ID do produto
            nova_quantidade: Nova quantidade
        
        Returns:
            True se atualizado, False caso contrário
        """
        try:
            query = "UPDATE produtos_standby SET quantidade = %s WHERE id = %s"
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (nova_quantidade, produto_id))
                
                return cursor.rowcount > 0
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao atualizar quantidade standby: {e}")
            return False
    
    def deletar_produto_standby(self, produto_id):
        """
        Deleta produto do standby
        
        Args:
            produto_id: ID do produto
        
        Returns:
            True se deletado, False caso contrário
        """
        try:
            query = "DELETE FROM produtos_standby WHERE id = %s"
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (produto_id,))
                
                return cursor.rowcount > 0
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao deletar produto standby: {e}")
            return False
    
    # ========== LISTAS LOJA ==========
    
    def criar_lista_loja(self, usuario_id, data_envio, responsavel_id, pin):
        """
        Cria uma nova lista de loja
        
        Args:
            usuario_id: ID do usuário
            data_envio: Data de envio
            responsavel_id: ID do responsável
            pin: PIN do responsável
        
        Returns:
            ID da lista criada
        """
        try:
            query = """
                INSERT INTO listas_loja (usuario_id, data_envio, responsavel_id, responsavel_pin)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (usuario_id, data_envio, responsavel_id, pin))
                lista_id = cursor.fetchone()[0]
                
                logger.info(f"Lista loja criada: ID {lista_id}")
                return lista_id
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao criar lista loja: {e}")
            raise
    
    def adicionar_produto_loja(self, lista_id, produto, usuario_id):
        """
        Adiciona produto à lista de loja
        
        Args:
            lista_id: ID da lista
            produto: Dicionário com dados do produto
            usuario_id: ID do usuário
        
        Returns:
            ID do produto adicionado
        """
        try:
            query = """
                INSERT INTO produtos_loja (lista_loja_id, ean, nome, cor, voltagem, modelo, quantidade, usuario_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    lista_id,
                    produto['ean'],
                    produto.get('nome'),
                    produto.get('cor'),
                    produto.get('voltagem'),
                    produto.get('modelo'),
                    produto['quantidade'],
                    usuario_id
                ))
                produto_id = cursor.fetchone()[0]
                
                return produto_id
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao adicionar produto à lista loja: {e}")
            raise
    
    # ========== LISTAS MANUTENÇÃO ==========
    
    def criar_lista_manutencao(self, usuario_id, data_envio, responsavel_id, pin):
        """
        Cria uma nova lista de manutenção
        
        Args:
            usuario_id: ID do usuário
            data_envio: Data de envio
            responsavel_id: ID do responsável
            pin: PIN do responsável
        
        Returns:
            ID da lista criada
        """
        try:
            query = """
                INSERT INTO listas_manutencao (usuario_id, data_envio, responsavel_id, responsavel_pin)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (usuario_id, data_envio, responsavel_id, pin))
                lista_id = cursor.fetchone()[0]
                
                logger.info(f"Lista manutenção criada: ID {lista_id}")
                return lista_id
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao criar lista manutenção: {e}")
            raise
    
    def adicionar_produto_manutencao(self, lista_id, produto, usuario_id):
        """
        Adiciona produto à lista de manutenção
        
        Args:
            lista_id: ID da lista
            produto: Dicionário com dados do produto
            usuario_id: ID do usuário
        
        Returns:
            ID do produto adicionado
        """
        try:
            query = """
                INSERT INTO produtos_manutencao (lista_manutencao_id, ean, nome, cor, voltagem, modelo, quantidade, usuario_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    lista_id,
                    produto['ean'],
                    produto.get('nome'),
                    produto.get('cor'),
                    produto.get('voltagem'),
                    produto.get('modelo'),
                    produto['quantidade'],
                    usuario_id
                ))
                produto_id = cursor.fetchone()[0]
                
                return produto_id
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao adicionar produto à lista manutenção: {e}")
            raise
    
    # ========== LISTAS UNIFICADAS ==========
    
    def criar_lista_unificada(self, titulo, descricao, criador_id):
        """
        Cria uma nova lista unificada
        
        Args:
            titulo: Título da lista
            descricao: Descrição da lista
            criador_id: ID do criador
        
        Returns:
            ID da lista criada
        """
        try:
            query = """
                INSERT INTO listas_unificadas (titulo, descricao, criador_id, data_criacao)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (titulo, descricao, criador_id, datetime.now()))
                lista_id = cursor.fetchone()[0]
                
                logger.info(f"Lista unificada criada: ID {lista_id}")
                return lista_id
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao criar lista unificada: {e}")
            raise
    
    def adicionar_produto_unificado(self, lista_id, produto):
        """
        Adiciona produto à lista unificada
        
        Args:
            lista_id: ID da lista
            produto: Dicionário com dados do produto
        
        Returns:
            ID do produto adicionado
        """
        try:
            query = """
                INSERT INTO produtos_unificados 
                (lista_unificada_id, ean, nome, cor, voltagem, modelo, quantidade_total, listas_origem)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    lista_id,
                    produto['ean'],
                    produto.get('nome'),
                    produto.get('cor'),
                    produto.get('voltagem'),
                    produto.get('modelo'),
                    produto['quantidade_total'],
                    produto.get('listas_origem', '')
                ))
                produto_id = cursor.fetchone()[0]
                
                return produto_id
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao adicionar produto à lista unificada: {e}")
            raise
    
    def listar_listas_unificadas(self):
        """
        Lista todas as listas unificadas
        
        Returns:
            Lista de listas unificadas
        """
        query = """
            SELECT lu.*, u.nome as criador_nome
            FROM listas_unificadas lu
            LEFT JOIN usuarios u ON lu.criador_id = u.id
            ORDER BY lu.data_criacao DESC
        """
        
        return self.execute_custom_query(query, fetch_all=True)
    
    def obter_produtos_unificados(self, lista_id):
        """
        Obtém produtos de uma lista unificada
        
        Args:
            lista_id: ID da lista
        
        Returns:
            Lista de produtos
        """
        query = """
            SELECT * FROM produtos_unificados 
            WHERE lista_unificada_id = %s
            ORDER BY nome
        """
        
        return self.execute_custom_query(query, (lista_id,), fetch_all=True)

