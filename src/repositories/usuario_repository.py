"""
Repositório de Usuários
Gerencia acesso aos dados de usuários no banco de dados
"""
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash
from src.repositories.base_repository import BaseRepository
from src.extensions.database import get_db
import logging

logger = logging.getLogger(__name__)


class UsuarioRepository(BaseRepository):
    """Repositório para gerenciar usuários"""
    
    def __init__(self):
        super().__init__('usuarios')
    
    def find_by_nome(self, nome):
        """
        Busca usuário por nome
        
        Args:
            nome: Nome do usuário
        
        Returns:
            Usuário como dicionário ou None
        """
        return self.find_one_by_field('nome', nome)
    
    def verificar_credenciais(self, nome, senha):
        """
        Verifica credenciais de login
        
        Args:
            nome: Nome do usuário
            senha: Senha em texto plano
        
        Returns:
            Dicionário com dados do usuário se credenciais válidas, None caso contrário
        """
        try:
            query = "SELECT id, nome, senha_hash, admin, ativo FROM usuarios WHERE nome = %s"
            
            with get_db() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute(query, (nome,))
                usuario = cursor.fetchone()
            
            if usuario and check_password_hash(usuario['senha_hash'], senha):
                # Verificar se usuário está ativo
                if not usuario.get('ativo', True):
                    logger.warning(f"Tentativa de login de usuário inativo: {nome}")
                    return None
                
                return {
                    'id': usuario['id'],
                    'nome': usuario['nome'],
                    'admin': usuario['admin']
                }
            
            logger.warning(f"Credenciais inválidas para usuário: {nome}")
            return None
            
        except psycopg2.Error as e:
            logger.error(f"Erro ao verificar credenciais do usuário {nome}: {e}")
            return None
    
    def criar_usuario(self, nome, senha, admin=0, ativo=True):
        """
        Cria um novo usuário
        
        Args:
            nome: Nome do usuário
            senha: Senha em texto plano
            admin: Nível de admin (0=estoque, 1=admin, 2=cadastro)
            ativo: Se o usuário está ativo
        
        Returns:
            ID do usuário criado ou None se erro
        """
        try:
            senha_hash = generate_password_hash(senha)
            
            data = {
                'nome': nome,
                'senha_hash': senha_hash,
                'admin': admin,
                'ativo': ativo
            }
            
            usuario_id = self.create(data)
            logger.info(f"Usuário criado: {nome} (ID: {usuario_id})")
            return usuario_id
            
        except psycopg2.errors.UniqueViolation:
            logger.warning(f"Tentativa de criar usuário duplicado: {nome}")
            return None
        except psycopg2.Error as e:
            logger.error(f"Erro ao criar usuário {nome}: {e}")
            return None
    
    def atualizar_senha(self, usuario_id, nova_senha):
        """
        Atualiza a senha de um usuário
        
        Args:
            usuario_id: ID do usuário
            nova_senha: Nova senha em texto plano
        
        Returns:
            True se atualizado com sucesso, False caso contrário
        """
        try:
            senha_hash = generate_password_hash(nova_senha)
            
            data = {'senha_hash': senha_hash}
            rowcount = self.update(usuario_id, data)
            
            if rowcount > 0:
                logger.info(f"Senha atualizada para usuário ID {usuario_id}")
                return True
            return False
            
        except psycopg2.Error as e:
            logger.error(f"Erro ao atualizar senha do usuário {usuario_id}: {e}")
            return False
    
    def atualizar_nivel_admin(self, usuario_id, admin):
        """
        Atualiza o nível de admin de um usuário
        
        Args:
            usuario_id: ID do usuário
            admin: Novo nível de admin (0, 1 ou 2)
        
        Returns:
            True se atualizado com sucesso, False caso contrário
        """
        try:
            data = {'admin': admin}
            rowcount = self.update(usuario_id, data)
            
            if rowcount > 0:
                logger.info(f"Nível de admin atualizado para usuário ID {usuario_id}: {admin}")
                return True
            return False
            
        except psycopg2.Error as e:
            logger.error(f"Erro ao atualizar nível de admin do usuário {usuario_id}: {e}")
            return False
    
    def ativar_desativar_usuario(self, usuario_id, ativo):
        """
        Ativa ou desativa um usuário
        
        Args:
            usuario_id: ID do usuário
            ativo: True para ativar, False para desativar
        
        Returns:
            True se atualizado com sucesso, False caso contrário
        """
        try:
            data = {'ativo': ativo}
            rowcount = self.update(usuario_id, data)
            
            if rowcount > 0:
                status = "ativado" if ativo else "desativado"
                logger.info(f"Usuário ID {usuario_id} {status}")
                return True
            return False
            
        except psycopg2.Error as e:
            logger.error(f"Erro ao ativar/desativar usuário {usuario_id}: {e}")
            return False
    
    def listar_usuarios_ativos(self):
        """
        Lista todos os usuários ativos
        
        Returns:
            Lista de usuários ativos
        """
        query = "SELECT id, nome, admin, ativo, data_criacao FROM usuarios WHERE ativo = TRUE ORDER BY nome"
        return self.execute_custom_query(query, fetch_all=True)
    
    def listar_todos_usuarios(self):
        """
        Lista todos os usuários (ativos e inativos)
        
        Returns:
            Lista de todos os usuários
        """
        query = "SELECT id, nome, admin, ativo, data_criacao FROM usuarios ORDER BY nome"
        return self.execute_custom_query(query, fetch_all=True)
    
    def contar_usuarios_por_tipo(self):
        """
        Conta usuários por tipo (admin)
        
        Returns:
            Dicionário com contagem por tipo
        """
        query = """
            SELECT 
                admin,
                COUNT(*) as total
            FROM usuarios
            WHERE ativo = TRUE
            GROUP BY admin
        """
        
        resultados = self.execute_custom_query(query, fetch_all=True)
        
        contagem = {
            'estoque': 0,      # admin = 0
            'admin': 0,        # admin = 1
            'cadastro': 0      # admin = 2
        }
        
        for row in resultados:
            if row['admin'] == 0:
                contagem['estoque'] = row['total']
            elif row['admin'] == 1:
                contagem['admin'] = row['total']
            elif row['admin'] == 2:
                contagem['cadastro'] = row['total']
        
        return contagem
    
    def obter_nome_usuario(self, usuario_id):
        """
        Obtém o nome de um usuário pelo ID
        
        Args:
            usuario_id: ID do usuário
        
        Returns:
            Nome do usuário ou None
        """
        usuario = self.find_by_id(usuario_id)
        return usuario['nome'] if usuario else None

