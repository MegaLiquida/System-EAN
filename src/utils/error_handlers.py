"""
Error Handlers
Tratamento centralizado de erros HTTP e exceções
"""
from flask import jsonify, render_template, request
import logging

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """
    Registra handlers de erro na aplicação Flask
    
    Args:
        app: Aplicação Flask
    """
    
    @app.errorhandler(400)
    def bad_request(error):
        """Handler para erro 400 - Bad Request"""
        logger.warning(f"Bad Request: {request.url} | {error}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                "error": "Requisição inválida",
                "message": str(error)
            }), 400
        
        return render_template('errors/400.html', error=error), 400
    
    @app.errorhandler(401)
    def unauthorized(error):
        """Handler para erro 401 - Unauthorized"""
        logger.warning(f"Unauthorized: {request.url} | {error}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                "error": "Não autorizado",
                "message": "Você precisa estar logado para acessar este recurso"
            }), 401
        
        return render_template('errors/401.html', error=error), 401
    
    @app.errorhandler(403)
    def forbidden(error):
        """Handler para erro 403 - Forbidden"""
        logger.warning(f"Forbidden: {request.url} | {error}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                "error": "Acesso negado",
                "message": "Você não tem permissão para acessar este recurso"
            }), 403
        
        return render_template('errors/403.html', error=error), 403
    
    @app.errorhandler(404)
    def not_found(error):
        """Handler para erro 404 - Not Found"""
        logger.info(f"Not Found: {request.url}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                "error": "Não encontrado",
                "message": "O recurso solicitado não foi encontrado"
            }), 404
        
        return render_template('errors/404.html', error=error), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handler para erro 405 - Method Not Allowed"""
        logger.warning(f"Method Not Allowed: {request.method} {request.url}")
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                "error": "Método não permitido",
                "message": f"O método {request.method} não é permitido para este recurso"
            }), 405
        
        return render_template('errors/405.html', error=error), 405
    
    @app.errorhandler(500)
    def internal_server_error(error):
        """Handler para erro 500 - Internal Server Error"""
        logger.error(f"Internal Server Error: {request.url} | {error}", exc_info=True)
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                "error": "Erro interno do servidor",
                "message": "Ocorreu um erro inesperado. Tente novamente mais tarde."
            }), 500
        
        return render_template('errors/500.html', error=error), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handler genérico para exceções não tratadas"""
        logger.error(f"Unhandled Exception: {request.url} | {type(error).__name__}: {error}", exc_info=True)
        
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({
                "error": "Erro interno do servidor",
                "message": "Ocorreu um erro inesperado"
            }), 500
        
        return render_template('errors/500.html', error=error), 500
    
    logger.info("Error handlers registrados")


def create_error_templates(templates_dir):
    """
    Cria templates básicos de erro se não existirem
    
    Args:
        templates_dir: Diretório de templates
    """
    import os
    
    errors_dir = os.path.join(templates_dir, 'errors')
    
    if not os.path.exists(errors_dir):
        os.makedirs(errors_dir)
    
    # Template 400
    template_400 = """<!DOCTYPE html>
<html>
<head>
    <title>400 - Requisição Inválida</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>400 - Requisição Inválida</h1>
    <p>A requisição enviada não pôde ser processada.</p>
    <p><a href="/">Voltar para a página inicial</a></p>
</body>
</html>"""
    
    # Template 401
    template_401 = """<!DOCTYPE html>
<html>
<head>
    <title>401 - Não Autorizado</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>401 - Não Autorizado</h1>
    <p>Você precisa estar logado para acessar esta página.</p>
    <p><a href="/login">Fazer login</a></p>
</body>
</html>"""
    
    # Template 403
    template_403 = """<!DOCTYPE html>
<html>
<head>
    <title>403 - Acesso Negado</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>403 - Acesso Negado</h1>
    <p>Você não tem permissão para acessar esta página.</p>
    <p><a href="/">Voltar para a página inicial</a></p>
</body>
</html>"""
    
    # Template 404
    template_404 = """<!DOCTYPE html>
<html>
<head>
    <title>404 - Página Não Encontrada</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>404 - Página Não Encontrada</h1>
    <p>A página que você está procurando não existe.</p>
    <p><a href="/">Voltar para a página inicial</a></p>
</body>
</html>"""
    
    # Template 405
    template_405 = """<!DOCTYPE html>
<html>
<head>
    <title>405 - Método Não Permitido</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>405 - Método Não Permitido</h1>
    <p>O método HTTP utilizado não é permitido para este recurso.</p>
    <p><a href="/">Voltar para a página inicial</a></p>
</body>
</html>"""
    
    # Template 500
    template_500 = """<!DOCTYPE html>
<html>
<head>
    <title>500 - Erro Interno</title>
    <meta charset="utf-8">
</head>
<body>
    <h1>500 - Erro Interno do Servidor</h1>
    <p>Ocorreu um erro inesperado. Tente novamente mais tarde.</p>
    <p><a href="/">Voltar para a página inicial</a></p>
</body>
</html>"""
    
    templates = {
        '400.html': template_400,
        '401.html': template_401,
        '403.html': template_403,
        '404.html': template_404,
        '405.html': template_405,
        '500.html': template_500
    }
    
    for filename, content in templates.items():
        filepath = os.path.join(errors_dir, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
    
    logger.info(f"Templates de erro criados em {errors_dir}")

