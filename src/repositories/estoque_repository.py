"""
Repositório de Estoque
Gerencia ruas, movimentações e estoque local
"""
import psycopg2
import psycopg2.extras
from datetime import datetime
from src.repositories.base_repository import BaseRepository
from src.extensions.database import get_db
import logging

logger = logging.getLogger(__name__)


class EstoqueRepository(BaseRepository):
    """Repositório para gerenciar estoque e movimentações"""
    
    def __init__(self):
        super().__init__('ruas')
    
    # ========== RUAS ==========
    
    def listar_ruas(self):
        """
        Lista todas as ruas ordenadas por posição
        
        Returns:
            Lista de ruas
        """
        query = "SELECT * FROM ruas ORDER BY posicao, nome"
        return self.execute_custom_query(query, fetch_all=True)
    
    def buscar_rua_por_nome(self, nome):
        """
        Busca rua por nome
        
        Args:
            nome: Nome da rua
        
        Returns:
            Rua como dicionário ou None
        """
        return self.find_one_by_field('nome', nome)
    
    def criar_rua(self, nome, posicao=None):
        """
        Cria uma nova rua
        
        Args:
            nome: Nome da rua
            posicao: Posição da rua (opcional)
        
        Returns:
            ID da rua criada
        """
        try:
            if posicao is None:
                # Obter próxima posição disponível
                query = "SELECT COALESCE(MAX(posicao), 0) + 1 FROM ruas"
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(query)
                    posicao = cursor.fetchone()[0]
            
            data = {'nome': nome, 'posicao': posicao}
            rua_id = self.create(data)
            logger.info(f"Rua criada: {nome} (posição {posicao})")
            return rua_id
            
        except psycopg2.errors.UniqueViolation:
            logger.warning(f"Tentativa de criar rua duplicada: {nome}")
            return None
        except psycopg2.Error as e:
            logger.error(f"Erro ao criar rua: {e}")
            raise
    
    def deletar_rua(self, rua_id):
        """
        Deleta uma rua
        
        Args:
            rua_id: ID da rua
        
        Returns:
            True se deletada, False caso contrário
        """
        try:
            # Verificar se há produtos na rua
            query = "SELECT COUNT(*) FROM produtos WHERE rua_id = %s AND ativo = TRUE"
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (rua_id,))
                count = cursor.fetchone()[0]
                
                if count > 0:
                    logger.warning(f"Tentativa de deletar rua {rua_id} com produtos")
                    return False
                
                # Deletar rua
                rowcount = self.delete(rua_id)
                if rowcount > 0:
                    logger.info(f"Rua {rua_id} deletada")
                    return True
                return False
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao deletar rua: {e}")
            return False
    
    def mover_rua(self, rua_id, nova_posicao):
        """
        Move uma rua para nova posição
        
        Args:
            rua_id: ID da rua
            nova_posicao: Nova posição
        
        Returns:
            True se movida, False caso contrário
        """
        try:
            data = {'posicao': nova_posicao}
            rowcount = self.update(rua_id, data)
            
            if rowcount > 0:
                logger.info(f"Rua {rua_id} movida para posição {nova_posicao}")
                return True
            return False
            
        except psycopg2.Error as e:
            logger.error(f"Erro ao mover rua: {e}")
            return False
    
    # ========== MOVIMENTAÇÕES ==========
    
    def registrar_movimentacao(self, tipo, ean, nome, quantidade, rua_id, usuario_id, 
                               cor=None, voltagem=None, modelo=None, observacao=None):
        """
        Registra uma movimentação de estoque
        
        Args:
            tipo: Tipo de movimentação ('entrada' ou 'saida')
            ean: Código EAN do produto
            nome: Nome do produto
            quantidade: Quantidade movimentada
            rua_id: ID da rua
            usuario_id: ID do usuário
            cor, voltagem, modelo: Atributos do produto (opcionais)
            observacao: Observação adicional (opcional)
        
        Returns:
            ID da movimentação registrada
        """
        try:
            query = """
                INSERT INTO movimentacoes 
                (tipo, ean, nome, cor, voltagem, modelo, quantidade, rua_id, usuario_id, data_movimentacao, observacao)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    tipo, ean, nome, cor, voltagem, modelo, 
                    quantidade, rua_id, usuario_id, datetime.now(), observacao
                ))
                movimentacao_id = cursor.fetchone()[0]
                
                logger.info(f"Movimentação registrada: {tipo} - {ean} - quantidade {quantidade}")
                return movimentacao_id
                
        except psycopg2.Error as e:
            logger.error(f"Erro ao registrar movimentação: {e}")
            raise
    
    def listar_movimentacoes(self, limit=100, offset=0, filtros=None):
        """
        Lista movimentações com filtros opcionais
        
        Args:
            limit: Limite de registros
            offset: Offset para paginação
            filtros: Dicionário com filtros (tipo, usuario_id, rua_id, data_inicio, data_fim)
        
        Returns:
            Lista de movimentações
        """
        query = """
            SELECT m.*, u.nome as usuario_nome, r.nome as rua_nome
            FROM movimentacoes m
            LEFT JOIN usuarios u ON m.usuario_id = u.id
            LEFT JOIN ruas r ON m.rua_id = r.id
            WHERE 1=1
        """
        
        params = []
        
        if filtros:
            if filtros.get('tipo'):
                query += " AND m.tipo = %s"
                params.append(filtros['tipo'])
            
            if filtros.get('usuario_id'):
                query += " AND m.usuario_id = %s"
                params.append(filtros['usuario_id'])
            
            if filtros.get('rua_id'):
                query += " AND m.rua_id = %s"
                params.append(filtros['rua_id'])
            
            if filtros.get('data_inicio'):
                query += " AND m.data_movimentacao >= %s"
                params.append(filtros['data_inicio'])
            
            if filtros.get('data_fim'):
                query += " AND m.data_movimentacao <= %s"
                params.append(filtros['data_fim'])
        
        query += " ORDER BY m.data_movimentacao DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        return self.execute_custom_query(query, tuple(params), fetch_all=True)
    
    def obter_estatisticas_movimentacoes(self, data_inicio=None, data_fim=None):
        """
        Obtém estatísticas de movimentações
        
        Args:
            data_inicio: Data inicial do período (opcional)
            data_fim: Data final do período (opcional)
        
        Returns:
            Dicionário com estatísticas
        """
        query = """
            SELECT 
                tipo,
                COUNT(*) as total_movimentacoes,
                SUM(quantidade) as total_quantidade
            FROM movimentacoes
            WHERE 1=1
        """
        
        params = []
        
        if data_inicio:
            query += " AND data_movimentacao >= %s"
            params.append(data_inicio)
        
        if data_fim:
            query += " AND data_movimentacao <= %s"
            params.append(data_fim)
        
        query += " GROUP BY tipo"
        
        resultados = self.execute_custom_query(query, tuple(params) if params else None, fetch_all=True)
        
        estatisticas = {
            'entrada': {'total_movimentacoes': 0, 'total_quantidade': 0},
            'saida': {'total_movimentacoes': 0, 'total_quantidade': 0}
        }
        
        for row in resultados:
            estatisticas[row['tipo']] = {
                'total_movimentacoes': row['total_movimentacoes'],
                'total_quantidade': row['total_quantidade']
            }
        
        return estatisticas
    
    def obter_estatisticas_por_usuario(self, data_inicio=None, data_fim=None):
        """
        Obtém estatísticas de movimentações por usuário
        
        Args:
            data_inicio: Data inicial do período (opcional)
            data_fim: Data final do período (opcional)
        
        Returns:
            Lista de estatísticas por usuário
        """
        query = """
            SELECT 
                u.id as usuario_id,
                u.nome as usuario_nome,
                m.tipo,
                COUNT(*) as total_movimentacoes,
                SUM(m.quantidade) as total_quantidade
            FROM movimentacoes m
            JOIN usuarios u ON m.usuario_id = u.id
            WHERE 1=1
        """
        
        params = []
        
        if data_inicio:
            query += " AND m.data_movimentacao >= %s"
            params.append(data_inicio)
        
        if data_fim:
            query += " AND m.data_movimentacao <= %s"
            params.append(data_fim)
        
        query += " GROUP BY u.id, u.nome, m.tipo ORDER BY u.nome, m.tipo"
        
        return self.execute_custom_query(query, tuple(params) if params else None, fetch_all=True)

