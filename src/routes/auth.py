"""
Blueprint de Autenticação
Gerencia login, logout e registro de usuários
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from src.repositories.usuario_repository import UsuarioRepository
from src.config.settings import Config
import logging

logger = logging.getLogger(__name__)

# Criar Blueprint
auth_bp = Blueprint('auth', __name__)

# Instanciar repositório
usuario_repo = UsuarioRepository()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Rota de login
    GET: Exibe formulário de login
    POST: Processa autenticação
    """
    if request.method == "POST":
        nome = request.form.get("nome")
        senha = request.form.get("senha")
        
        # Validar entrada
        if not nome or not senha:
            flash("Nome de usuário e senha são obrigatórios")
            return render_template("login.html")
        
        # Verificar credenciais
        usuario = usuario_repo.verificar_credenciais(nome, senha)
        
        if usuario:
            # Criar sessão
            session["usuario_id"] = usuario["id"]
            session["usuario_nome"] = nome
            session["admin"] = usuario["admin"]
            session["logado"] = True
            
            logger.info(f"Login bem-sucedido: {nome} (ID: {usuario['id']})")
            
            # Redirecionar baseado no tipo de usuário
            if usuario["admin"] == 1:
                # Painel Administrativo
                return redirect(url_for("admin.dashboard"))
            elif usuario["admin"] == 2:
                # Sistema de Cadastro de Produtos
                return redirect(url_for("produtos.index"))
            else:
                # Sistema de Estoque (padrão para admin = 0)
                return redirect(url_for("estoque.index"))
        else:
            logger.warning(f"Tentativa de login falhou: {nome}")
            flash("Nome de usuário ou senha incorretos")
    
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """
    Rota de logout
    Limpa a sessão e redireciona para login
    """
    usuario_nome = session.get("usuario_nome", "Desconhecido")
    session.clear()
    
    logger.info(f"Logout: {usuario_nome}")
    flash("Você saiu do sistema com sucesso")
    
    return redirect(url_for("auth.login"))


@auth_bp.route("/registro", methods=["GET", "POST"])
def registro():
    """
    Rota de registro de novos usuários
    GET: Exibe formulário de registro
    POST: Processa criação de usuário
    """
    if request.method == "POST":
        nome = request.form.get("nome")
        senha = request.form.get("senha")
        senha_confirmacao = request.form.get("senha_confirmacao")
        
        # Validações
        if not nome or not senha:
            flash("Nome de usuário e senha são obrigatórios")
            return render_template("registro.html")
        
        if len(nome) < 3:
            flash("Nome de usuário deve ter pelo menos 3 caracteres")
            return render_template("registro.html")
        
        if len(senha) < 6:
            flash("Senha deve ter pelo menos 6 caracteres")
            return render_template("registro.html")
        
        if senha_confirmacao and senha != senha_confirmacao:
            flash("As senhas não coincidem")
            return render_template("registro.html")
        
        # Tentar criar usuário
        usuario_id = usuario_repo.criar_usuario(nome, senha, admin=0, ativo=True)
        
        if usuario_id:
            logger.info(f"Novo usuário registrado: {nome} (ID: {usuario_id})")
            flash("Usuário registrado com sucesso! Faça login.")
            return redirect(url_for("auth.login"))
        else:
            logger.warning(f"Falha ao registrar usuário: {nome} (nome já existe)")
            flash("Erro ao registrar usuário. Nome de usuário já existe.")
    
    return render_template("registro.html")


@auth_bp.route("/alterar-senha", methods=["GET", "POST"])
def alterar_senha():
    """
    Rota para alterar senha do usuário logado
    GET: Exibe formulário
    POST: Processa alteração
    """
    # Verificar se usuário está logado
    if not session.get("logado"):
        flash("Você precisa estar logado para alterar a senha")
        return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        senha_atual = request.form.get("senha_atual")
        senha_nova = request.form.get("senha_nova")
        senha_confirmacao = request.form.get("senha_confirmacao")
        
        usuario_id = session.get("usuario_id")
        usuario_nome = session.get("usuario_nome")
        
        # Validações
        if not senha_atual or not senha_nova:
            flash("Todos os campos são obrigatórios")
            return render_template("alterar_senha.html")
        
        if len(senha_nova) < 6:
            flash("Nova senha deve ter pelo menos 6 caracteres")
            return render_template("alterar_senha.html")
        
        if senha_confirmacao and senha_nova != senha_confirmacao:
            flash("As senhas não coincidem")
            return render_template("alterar_senha.html")
        
        # Verificar senha atual
        usuario = usuario_repo.verificar_credenciais(usuario_nome, senha_atual)
        
        if not usuario:
            flash("Senha atual incorreta")
            return render_template("alterar_senha.html")
        
        # Atualizar senha
        if usuario_repo.atualizar_senha(usuario_id, senha_nova):
            logger.info(f"Senha alterada: usuário {usuario_nome} (ID: {usuario_id})")
            flash("Senha alterada com sucesso!")
            return redirect(url_for("auth.logout"))  # Forçar novo login
        else:
            flash("Erro ao alterar senha. Tente novamente.")
    
    return render_template("alterar_senha.html")


# Decorador para proteger rotas que requerem autenticação
def login_required(f):
    """
    Decorador para proteger rotas que requerem autenticação
    
    Uso:
        @auth_bp.route("/rota-protegida")
        @login_required
        def rota_protegida():
            ...
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logado"):
            flash("Você precisa estar logado para acessar esta página")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    
    return decorated_function


# Decorador para proteger rotas que requerem nível admin
def admin_required(f):
    """
    Decorador para proteger rotas que requerem nível administrativo
    
    Uso:
        @auth_bp.route("/rota-admin")
        @admin_required
        def rota_admin():
            ...
    """
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logado"):
            flash("Você precisa estar logado para acessar esta página")
            return redirect(url_for("auth.login"))
        
        if session.get("admin") != 1:
            flash("Você não tem permissão para acessar esta página")
            logger.warning(f"Acesso negado: usuário {session.get('usuario_nome')} tentou acessar rota admin")
            return redirect(url_for("auth.login"))
        
        return f(*args, **kwargs)
    
    return decorated_function


# Função auxiliar para obter usuário da sessão
def get_current_user():
    """
    Obtém informações do usuário logado
    
    Returns:
        Dicionário com dados do usuário ou None se não logado
    """
    if session.get("logado"):
        return {
            "id": session.get("usuario_id"),
            "nome": session.get("usuario_nome"),
            "admin": session.get("admin")
        }
    return None


# Context processor para disponibilizar usuário em todos os templates
@auth_bp.app_context_processor
def inject_user():
    """
    Injeta informações do usuário em todos os templates
    Permite usar {{ current_user }} nos templates
    """
    return {
        "current_user": get_current_user(),
        "tipos_usuario": Config.TIPOS_USUARIO
    }

