"""
Script de Execução do Sistema EAN
Versão Refatorada
"""
import os
import sys

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import create_app, run_app


if __name__ == '__main__':
    # Obter configuração do ambiente
    config_name = os.getenv('FLASK_ENV', 'development')
    
    # Criar aplicação
    app = create_app(config_name)
    
    # Obter host e porta do ambiente ou usar padrões
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    
    # Executar aplicação
    run_app(app, host=host, port=port)

