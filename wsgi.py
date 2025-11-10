"""
WSGI entry point para o Sistema de Gestão de Mercado
Usado pelo Gunicorn para iniciar a aplicação
"""

import os
import sys

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(__file__))

from src.main import app, db

# Criar tabelas se não existirem
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run()
