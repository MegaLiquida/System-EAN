"""
Configurações do Sistema EAN
Centraliza todas as configurações da aplicação
"""
import os
from datetime import timedelta


class Config:
    """Configuração base"""
    
    # Configurações Flask
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'ean_app_secret_key_default'
    
    # Configurações de Banco de Dados
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # Configurações de Pool de Conexões
    DB_POOL_MIN_CONN = int(os.environ.get('DB_POOL_MIN_CONN', 5))
    DB_POOL_MAX_CONN = int(os.environ.get('DB_POOL_MAX_CONN', 20))
    
    # Configurações de Sessão
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    SESSION_COOKIE_SECURE = False  # True em produção com HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Configurações de Upload
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    
    # Configurações de Email (para futuro uso)
    SMTP_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USER = os.environ.get('SMTP_USER')
    SMTP_PASS = os.environ.get('SMTP_PASS')
    SMTP_USE_TLS = True
    
    # Configurações de Cache (para futuro uso com Redis)
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'simple')
    CACHE_REDIS_URL = os.environ.get('REDIS_URL')
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutos
    
    # Configurações de Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'logs', 'ean_sistema.log')
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 10
    
    # Configurações de API Mercado Livre
    MERCADO_LIVRE_API_URL = 'https://api.mercadolibre.com'
    MERCADO_LIVRE_TIMEOUT = 10  # segundos
    
    # Configurações de Paginação
    ITEMS_PER_PAGE = 20
    
    # Configurações de Segurança
    BCRYPT_LOG_ROUNDS = 12
    
    # Tipos de Usuário
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
    
    @staticmethod
    def obter_tipo_por_admin(admin_flag):
        """Mapear flag admin para tipo de usuário"""
        if admin_flag == 1:
            return "painel_administrativo"
        elif admin_flag == 2:
            return "sistema_cadastro"
        else:
            return "sistema_estoque"
    
    @staticmethod
    def obter_admin_por_tipo(tipo):
        """Mapear tipo de usuário para flag admin (retorna INTEGER para compatibilidade com banco)"""
        if tipo == "painel_administrativo":
            return 1  # Admin
        elif tipo == "sistema_cadastro":
            return 2  # Sistema de Cadastro
        else:
            return 0  # Sistema de Estoque (padrão)


class DevelopmentConfig(Config):
    """Configuração para ambiente de desenvolvimento"""
    DEBUG = True
    TESTING = False
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(Config):
    """Configuração para ambiente de produção"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True  # Requer HTTPS
    LOG_LEVEL = 'WARNING'
    
    # Validações adicionais para produção
    @classmethod
    def init_app(cls, app):
        # Verificar que SECRET_KEY não é a padrão
        if cls.SECRET_KEY == 'ean_app_secret_key_default':
            raise ValueError("SECRET_KEY deve ser definida em produção!")
        
        # Verificar que DATABASE_URL está definida
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL deve ser definida!")


class TestingConfig(Config):
    """Configuração para ambiente de testes"""
    TESTING = True
    DEBUG = True
    DATABASE_URL = os.environ.get('TEST_DATABASE_URL') or 'postgresql://localhost/ean_test'
    WTF_CSRF_ENABLED = False
    LOG_LEVEL = 'DEBUG'


# Dicionário de configurações disponíveis
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """
    Retorna a configuração apropriada baseada no ambiente
    
    Args:
        config_name: Nome da configuração ('development', 'production', 'testing')
                    Se None, usa a variável de ambiente FLASK_ENV
    
    Returns:
        Classe de configuração apropriada
    """
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    return config.get(config_name, DevelopmentConfig)

