"""
Repositório de Produtos
Gerencia acesso aos dados de produtos no banco de dados
"""
import psycopg2
import psycopg2.extras
from datetime import datetime
from src.repositories.base_repository import BaseRepository
from src.extensions.database import get_db
import logging

logger = logging.getLogger(__name__)


class ProdutoRepository(BaseRepository):
    """Repositório para gerenciar produtos"""
    
    def __init__(self):
        super().__init__('produtos')
    
    def buscar_por_ean(self, ean, usuario_id=None):
        """
        Busca produto por EAN
        
        Args:
            ean: Código EAN do produto
            usuario_id: ID do usuário (opcional, para filtrar por usuário)
        
        Returns:
            Produto como dicionário ou None
        """
        if usuario_id:
            query = "SELECT * FROM produtos WHERE ean = %s AND usuario_id = %s AND ativo = TRUE LIMIT 1"
            params = (ean, usuario_id)
        else:
            query = "SELECT * FROM produtos WHERE ean = %s AND ativo = TRUE LIMIT 1"
            params = (ean,)
        
        return self.execute_custom_query(query, params, fetch_one=True)
    
    def buscar_por_ean_nao_enviado(self, ean, usuario_id):
        """
        Busca produto não enviado por EAN e usuário
        
        Args:
            ean: Código EAN do produto
            usuario_id: ID do usuário
        
        Returns:
            Produto como dicionário ou None
        """
        query = """
            SELECT * FROM produtos 
            WHERE ean = %s AND usuario_id = %s AND enviado = 0 AND ativo = TRUE 
            LIMIT 1
        """
        return self.execute_custom_query(query, (ean, usuario_id), fetch_one=True)
    
    def listar_produtos_usuario(self, usuario_id, apenas_nao_enviados=False):
        """
        Lista produtos de um usuário (estoque geral, sem rua)
        
        Args:
            usuario_id: ID do usuário
            apenas_nao_enviados: Se True, retorna apenas produtos não enviados
        
        Returns:
            Lista de produtos
        """
        if apenas_nao_enviados:
            query = """
                SELECT * FROM produtos 
                WHERE usuario_id = %s AND enviado = 0 AND rua_id IS NULL AND ativo = TRUE 
                ORDER BY timestamp DESC
            """
        else:
            query = """
                SELECT * FROM produtos 
                WHERE usuario_id = %s AND rua_id IS NULL AND ativo = TRUE 
                ORDER BY timestamp DESC
            """
        
        return self.execute_custom_query(query, (usuario_id,), fetch_all=True)
    
    def criar_ou_atualizar_produto(self, produto_data, usuario_id):
        """
        Cria um novo produto ou atualiza quantidade se já existe
        
        Args:
            produto_data: Dicionário com dados do produto (ean, nome, quantidade, etc)
            usuario_id: ID do usuário
        
        Returns:
            ID do produto criado/atualizado
        """
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Verificar se produto já existe
                cursor.execute("""
                    SELECT id FROM produtos 
                    WHERE ean = %s AND usuario_id = %s AND enviado = 0 AND ativo = TRUE AND destino = %s
                """, (produto_data['ean'], usuario_id, produto_data.get('destino', 'mercado_livre')))
                
                existing = cursor.fetchone()
                timestamp_obj = datetime.now()
                
                if existing:
                    # Atualizar quantidade
                    if produto_data.get('destino') == 'manutencao' and produto_data.get('motivo_manutencao'):
                        cursor.execute("""
                            UPDATE produtos 
                            SET quantidade = quantidade + %s, 
                                timestamp = %s,
                                motivo_manutencao = %s
                            WHERE ean = %s AND usuario_id = %s AND destino = %s
                        """, (produto_data['quantidade'], timestamp_obj, produto_data.get('motivo_manutencao'), 
                              produto_data['ean'], usuario_id, produto_data.get('destino', 'mercado_livre')))
                    else:
                        cursor.execute("""
                            UPDATE produtos 
                            SET quantidade = quantidade + %s, 
                                timestamp = %s 
                            WHERE ean = %s AND usuario_id = %s AND enviado = 0 AND destino = %s
                        """, (produto_data['quantidade'], timestamp_obj, produto_data['ean'], 
                              usuario_id, produto_data.get('destino', 'mercado_livre')))
                    
                    produto_id = existing[0]
                    logger.info(f"Produto {produto_data['ean']} atualizado (ID: {produto_id})")
                else:
                    # Inserir novo produto
                    cursor.execute("""
                        INSERT INTO produtos (ean, nome, cor, voltagem, modelo, quantidade, usuario_id, timestamp, enviado, destino, motivo_manutencao)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
                        RETURNING id
                    """, (
                        produto_data['ean'],
                        produto_data.get('nome'),
                        produto_data.get('cor'),
                        produto_data.get('voltagem'),
                        produto_data.get('modelo'),
                        produto_data['quantidade'],
                        usuario_id,
                        timestamp_obj,
                        produto_data.get('destino', 'mercado_livre'),
                        produto_data.get('motivo_manutencao')
                    ))
                    
                    produto_id = cursor.fetchone()[0]
                    logger.info(f"Produto {produto_data['ean']} criado (ID: {produto_id})")
                
                return produto_id
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao criar/atualizar produto: {e}")
            raise
    
    def marcar_como_enviado(self, usuario_id, data_envio, responsavel_id, pin, destino='mercado_livre'):
        """
        Marca produtos como enviados
        
        Args:
            usuario_id: ID do usuário
            data_envio: Data de envio
            responsavel_id: ID do responsável
            pin: PIN do responsável
            destino: Destino dos produtos
        
        Returns:
            Número de produtos marcados como enviados
        """
        query = """
            UPDATE produtos 
            SET enviado = 1, data_envio = %s, responsavel_id = %s, responsavel_pin = %s
            WHERE usuario_id = %s AND enviado = 0 AND ativo = TRUE AND destino = %s
        """
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (data_envio, responsavel_id, pin, usuario_id, destino))
                rowcount = cursor.rowcount
                logger.info(f"{rowcount} produtos marcados como enviados para {destino}")
                return rowcount
        except psycopg2.Error as e:
            logger.error(f"Erro ao marcar produtos como enviados: {e}")
            raise
    
    def marcar_como_validado(self, data_envio, validador_id):
        """
        Marca produtos como validados
        
        Args:
            data_envio: Data de envio dos produtos a validar
            validador_id: ID do validador
        
        Returns:
            Número de produtos validados
        """
        query = """
            UPDATE produtos 
            SET validado = 1, 
                validador_id = %s,
                data_validacao = %s
            WHERE data_envio = %s AND enviado = 1 AND validado = 0
        """
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (validador_id, datetime.now(), data_envio))
                rowcount = cursor.rowcount
                logger.info(f"{rowcount} produtos marcados como validados")
                return rowcount
        except psycopg2.Error as e:
            logger.error(f"Erro ao marcar produtos como validados: {e}")
            raise
    
    def deletar_produto(self, produto_id, usuario_id):
        """
        Deleta um produto (marca como inativo)
        
        Args:
            produto_id: ID do produto
            usuario_id: ID do usuário (para verificar permissão)
        
        Returns:
            True se deletado com sucesso, False caso contrário
        """
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Verificar se produto pertence ao usuário e não foi enviado
                cursor.execute("""
                    SELECT id FROM produtos 
                    WHERE id = %s AND usuario_id = %s AND enviado = 0 AND ativo = TRUE
                """, (produto_id, usuario_id))
                
                produto = cursor.fetchone()
                
                if not produto:
                    logger.warning(f"Tentativa de deletar produto inexistente ou sem permissão: {produto_id}")
                    return False
                
                # Deletar produto
                cursor.execute("DELETE FROM produtos WHERE id = %s", (produto_id,))
                logger.info(f"Produto {produto_id} deletado")
                return True
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao deletar produto {produto_id}: {e}")
            return False
    
    def buscar_produtos_na_rua(self, rua_id):
        """
        Busca todos os produtos em uma rua específica
        
        Args:
            rua_id: ID da rua
        
        Returns:
            Lista de produtos na rua
        """
        query = """
            SELECT ean, nome, cor, voltagem, modelo, quantidade 
            FROM produtos 
            WHERE rua_id = %s AND ativo = TRUE
            ORDER BY nome
        """
        return self.execute_custom_query(query, (rua_id,), fetch_all=True)
    
    def adicionar_produto_rua(self, ean, rua_id, quantidade, produto_info, usuario_id):
        """
        Adiciona produto a uma rua (ou atualiza quantidade se já existe)
        
        Args:
            ean: Código EAN
            rua_id: ID da rua
            quantidade: Quantidade a adicionar
            produto_info: Informações do produto (nome, cor, voltagem, modelo)
            usuario_id: ID do usuário
        
        Returns:
            ID do produto
        """
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Verificar se produto já existe na rua
                cursor.execute("""
                    SELECT id, quantidade FROM produtos 
                    WHERE ean = %s AND rua_id = %s AND ativo = TRUE
                    ORDER BY quantidade DESC
                """, (ean, rua_id))
                
                produto_existente = cursor.fetchone()
                
                if produto_existente:
                    # Atualizar quantidade
                    nova_quantidade = produto_existente[1] + quantidade
                    cursor.execute("""
                        UPDATE produtos 
                        SET quantidade = %s 
                        WHERE id = %s
                    """, (nova_quantidade, produto_existente[0]))
                    
                    produto_id = produto_existente[0]
                    logger.info(f"Quantidade atualizada na rua {rua_id}: produto {ean}")
                else:
                    # Inserir novo produto na rua
                    cursor.execute("""
                        INSERT INTO produtos (ean, nome, cor, voltagem, modelo, quantidade, rua_id, usuario_id, timestamp, enviado, validado)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0) 
                        RETURNING id
                    """, (
                        produto_info['ean'],
                        produto_info.get('nome'),
                        produto_info.get('cor'),
                        produto_info.get('voltagem'),
                        produto_info.get('modelo'),
                        quantidade,
                        rua_id,
                        usuario_id,
                        datetime.now()
                    ))
                    
                    produto_id = cursor.fetchone()[0]
                    logger.info(f"Produto {ean} adicionado à rua {rua_id}")
                
                return produto_id
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao adicionar produto à rua: {e}")
            raise
    
    def remover_produto_rua(self, ean, rua_id, quantidade):
        """
        Remove quantidade de produto de uma rua
        
        Args:
            ean: Código EAN
            rua_id: ID da rua
            quantidade: Quantidade a remover
        
        Returns:
            Tupla (sucesso, quantidade_restante, acao_realizada)
        """
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Buscar produto na rua
                cursor.execute("""
                    SELECT id, quantidade FROM produtos 
                    WHERE ean = %s AND rua_id = %s AND ativo = TRUE
                """, (ean, rua_id))
                
                produto = cursor.fetchone()
                
                if not produto:
                    return (False, 0, "Produto não encontrado na rua")
                
                quantidade_disponivel = produto[1]
                
                if quantidade > quantidade_disponivel:
                    return (False, quantidade_disponivel, f"Quantidade insuficiente (disponível: {quantidade_disponivel})")
                
                if quantidade == quantidade_disponivel:
                    # Remover completamente
                    cursor.execute("DELETE FROM produtos WHERE id = %s", (produto[0],))
                    logger.info(f"Produto {ean} removido completamente da rua {rua_id}")
                    return (True, 0, "Produto removido completamente")
                else:
                    # Reduzir quantidade
                    nova_quantidade = quantidade_disponivel - quantidade
                    cursor.execute("""
                        UPDATE produtos 
                        SET quantidade = %s 
                        WHERE id = %s
                    """, (nova_quantidade, produto[0]))
                    logger.info(f"Quantidade reduzida na rua {rua_id}: produto {ean}")
                    return (True, nova_quantidade, f"Quantidade atualizada (restante: {nova_quantidade})")
                    
        except psycopg2.Error as e:
            logger.error(f"Erro ao remover produto da rua: {e}")
            raise
    
    def contar_produtos_na_rua(self, rua_id):
        """
        Conta quantos produtos existem em uma rua
        
        Args:
            rua_id: ID da rua
        
        Returns:
            Número de produtos
        """
        return self.count(where_clause="rua_id = %s AND ativo = TRUE", params=(rua_id,))

