"""
Aplicação Principal do Sistema EAN
Versão Refatorada com Arquitetura Modular
"""
from flask import Flask, session
from src.config.settings import get_config
from src.extensions.database import init_connection_pool, close_connection_pool
from src.utils.logger import setup_logging
from src.utils.error_handlers import register_error_handlers
import os
import logging

logger = logging.getLogger(__name__)


def create_app(config_name=None):
    """
    Factory function para criar aplicação Flask
    
    Args:
        config_name: Nome da configuração ('development', 'production', 'testing')
    
    Returns:
        Aplicação Flask configurada
    """
    # Criar aplicação
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')
    
    # Carregar configurações
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Configurar logging
    setup_logging(app)
    logger.info(f"Aplicação iniciada em modo {config_name}")
    
    # Inicializar pool de conexões ao banco (se DATABASE_URL estiver configurada)
    if app.config.get('DATABASE_URL'):
        try:
            init_connection_pool(database_url=app.config['DATABASE_URL'])
            logger.info("Pool de conexões ao banco inicializado")
        except Exception as e:
            logger.warning(f"Não foi possível inicializar pool de conexões: {e}")
            logger.warning("Aplicação inicializada sem conexão ao banco")
    else:
        logger.warning("DATABASE_URL não configurada. Pool de conexões não inicializado.")
    
    # Registrar error handlers (DESABILITADO TEMPORARIAMENTE)
    # register_error_handlers(app)
    logger.info("Error handlers desabilitados temporariamente")
    
    # Registrar Blueprints
    register_blueprints(app)
    
    # Registrar hooks
    register_hooks(app)
    
    # Context processors
    register_context_processors(app)
    
    # Registrar filtros de template
    register_template_filters(app)
    
    logger.info("Aplicação configurada com sucesso")
    
    return app


def register_blueprints(app):
    """
    Registra todos os Blueprints na aplicação
    
    Args:
        app: Aplicação Flask
    """
    from flask import redirect, url_for
    from src.routes.auth import auth_bp
    from src.routes.produtos import produtos_bp
    from src.routes.estoque import estoque_bp
    from src.routes.admin import admin_bp
    
    # Rota raiz - redireciona para login
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))
    
    # Blueprint de autenticação (sem prefixo)
    app.register_blueprint(auth_bp)
    logger.info("Blueprint 'auth' registrado")
    
    # Blueprint de produtos (prefixo /produtos)
    app.register_blueprint(produtos_bp, url_prefix='/produtos')
    logger.info("Blueprint 'produtos' registrado com prefixo /produtos")
    
    # Blueprint de estoque (prefixo /estoque)
    app.register_blueprint(estoque_bp, url_prefix='/estoque')
    logger.info("Blueprint 'estoque' registrado com prefixo /estoque")
    
    # Blueprint de administração (prefixo /admin)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    logger.info("Blueprint 'admin' registrado com prefixo /admin")


def register_hooks(app):
    """
    Registra hooks da aplicação (before_request, after_request, teardown)
    
    Args:
        app: Aplicação Flask
    """
    
    @app.before_request
    def before_request():
        """Executado antes de cada requisição"""
        # Pode adicionar logging, verificações, etc.
        pass
    
    @app.after_request
    def after_request(response):
        """Executado após cada requisição"""
        # Adicionar headers de segurança
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        return response
    
    @app.teardown_appcontext
    def teardown_db(exception=None):
        """Executado ao finalizar contexto da aplicação"""
        if exception:
            logger.error(f"Erro durante requisição: {exception}")
    
    logger.info("Hooks registrados")


def register_context_processors(app):
    """
    Registra context processors para templates
    
    Args:
        app: Aplicação Flask
    """
    
    @app.context_processor
    def inject_globals():
        """Injeta variáveis globais em todos os templates"""
        from datetime import datetime
        
        return {
            'now': datetime.now(),
            'app_name': app.config.get('APP_NAME', 'Sistema EAN'),
            'app_version': app.config.get('APP_VERSION', '2.0')
        }
    
    logger.info("Context processors registrados")


def register_template_filters(app):
    """
    Registra filtros customizados para templates Jinja2
    
    Args:
        app: Aplicação Flask
    """
    from datetime import datetime
    from decimal import Decimal
    
    @app.template_filter('data_brasileira')
    def data_brasileira_filter(data):
        """
        Formata data no padrão brasileiro DD/MM/YYYY HH:MM
        
        Args:
            data: datetime, date ou string ISO
        
        Returns:
            String formatada ou valor original se inválido
        """
        if data is None:
            return ''
        
        try:
            # Se for string, tentar converter
            if isinstance(data, str):
                # Tentar formato ISO
                if 'T' in data:
                    data = datetime.fromisoformat(data.replace('Z', '+00:00'))
                else:
                    data = datetime.strptime(data, '%Y-%m-%d %H:%M:%S')
            
            # Formatar data
            if isinstance(data, datetime):
                return data.strftime('%d/%m/%Y %H:%M')
            else:
                # Se for date (sem hora)
                return data.strftime('%d/%m/%Y')
        except Exception as e:
            logger.warning(f"Erro ao formatar data '{data}': {e}")
            return str(data)
    
    @app.template_filter('moeda')
    def moeda_filter(valor):
        """
        Formata valor numérico como moeda brasileira (R$ X.XXX,XX)
        
        Args:
            valor: float, int, Decimal ou string numérica
        
        Returns:
            String formatada como moeda
        """
        if valor is None:
            return 'R$ 0,00'
        
        try:
            # Converter para float se necessário
            if isinstance(valor, str):
                valor = float(valor.replace(',', '.'))
            elif isinstance(valor, Decimal):
                valor = float(valor)
            
            # Formatar com separadores brasileiros
            valor_formatado = f"{valor:,.2f}"
            # Trocar separadores (1,234.56 -> 1.234,56)
            valor_formatado = valor_formatado.replace(',', 'X').replace('.', ',').replace('X', '.')
            
            return f"R$ {valor_formatado}"
        except Exception as e:
            logger.warning(f"Erro ao formatar moeda '{valor}': {e}")
            return f"R$ {valor}"
    
    logger.info("Filtros de template registrados: data_brasileira, moeda")


def run_app(app, host='0.0.0.0', port=5000, debug=None):
    """
    Executa a aplicação
    
    Args:
        app: Aplicação Flask
        host: Host para bind
        port: Porta para bind
        debug: Modo debug (None = usar configuração)
    """
    if debug is None:
        debug = app.config.get('DEBUG', False)
    
    try:
        logger.info(f"Iniciando servidor em {host}:{port} (debug={debug})")
        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        logger.info("Servidor interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro ao iniciar servidor: {e}", exc_info=True)
    finally:
        # Fechar pool de conexões
        close_connection_pool()
        logger.info("Pool de conexões fechado")


# Criar aplicação para importação direta
app = create_app()


if __name__ == '__main__':
    # Executar aplicação se chamado diretamente
    run_app(app)

