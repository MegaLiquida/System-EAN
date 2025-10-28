"""
Configuração de Logging Estruturado
Configura logging para arquivo e console com rotação automática
"""
import logging
import logging.handlers
import os
from datetime import datetime


def setup_logging(app=None, log_level=None, log_file=None):
    """
    Configura logging para a aplicação
    
    Args:
        app: Aplicação Flask (opcional)
        log_level: Nível de log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Caminho do arquivo de log
    
    Returns:
        Logger configurado
    """
    # Obter configurações
    if app:
        log_level = log_level or app.config.get('LOG_LEVEL', 'INFO')
        log_file = log_file or app.config.get('LOG_FILE')
        max_bytes = app.config.get('LOG_MAX_BYTES', 10 * 1024 * 1024)  # 10MB
        backup_count = app.config.get('LOG_BACKUP_COUNT', 10)
    else:
        log_level = log_level or 'INFO'
        max_bytes = 10 * 1024 * 1024
        backup_count = 10
    
    # Converter string de nível para constante
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Configurar logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Limpar handlers existentes
    root_logger.handlers = []
    
    # Formato de log
    log_format = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # Handler para arquivo (com rotação)
    if log_file:
        # Criar diretório de logs se não existir
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(log_format)
        root_logger.addHandler(file_handler)
    
    # Configurar logger da aplicação Flask
    if app:
        app.logger.setLevel(numeric_level)
        app.logger.handlers = root_logger.handlers
    
    # Reduzir verbosidade de bibliotecas externas
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    logging.info(f"Logging configurado: nível={log_level}, arquivo={log_file}")
    
    return root_logger


def log_request(request, response_status=None):
    """
    Loga informações de uma requisição HTTP
    
    Args:
        request: Objeto request do Flask
        response_status: Status code da resposta (opcional)
    """
    logger = logging.getLogger('ean.requests')
    
    log_data = {
        'method': request.method,
        'path': request.path,
        'ip': request.remote_addr,
        'user_agent': request.user_agent.string[:100] if request.user_agent else None
    }
    
    if response_status:
        log_data['status'] = response_status
    
    logger.info(f"Request: {log_data}")


def log_error(error, context=None):
    """
    Loga um erro com contexto adicional
    
    Args:
        error: Exceção ou mensagem de erro
        context: Dicionário com contexto adicional
    """
    logger = logging.getLogger('ean.errors')
    
    error_msg = str(error)
    
    if context:
        error_msg += f" | Context: {context}"
    
    logger.error(error_msg, exc_info=True)


def log_database_operation(operation, table, details=None):
    """
    Loga operação de banco de dados
    
    Args:
        operation: Tipo de operação (SELECT, INSERT, UPDATE, DELETE)
        table: Nome da tabela
        details: Detalhes adicionais
    """
    logger = logging.getLogger('ean.database')
    
    log_msg = f"{operation} on {table}"
    
    if details:
        log_msg += f" | {details}"
    
    logger.debug(log_msg)


def log_user_action(user_id, action, details=None):
    """
    Loga ação de usuário para auditoria
    
    Args:
        user_id: ID do usuário
        action: Ação realizada
        details: Detalhes adicionais
    """
    logger = logging.getLogger('ean.audit')
    
    log_msg = f"User {user_id}: {action}"
    
    if details:
        log_msg += f" | {details}"
    
    logger.info(log_msg)

