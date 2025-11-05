"""
Blueprint de Administração
Gerencia painel administrativo, usuários, validação de listas e estatísticas
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from src.repositories.usuario_repository import UsuarioRepository
from src.repositories.produto_repository import ProdutoRepository
from src.repositories.lista_repository import ListaRepository
from src.routes.auth import admin_required
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Criar Blueprint
admin_bp = Blueprint('admin', __name__)

# Instanciar repositórios
usuario_repo = UsuarioRepository()
produto_repo = ProdutoRepository()
lista_repo = ListaRepository()


@admin_bp.route("/")
@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    """
    Dashboard principal do painel administrativo
    Exibe listas enviadas aguardando validação
    """
    try:
        # Parâmetros de busca e paginação
        termo_pesquisa = request.args.get("pesquisa", "")
        pagina = request.args.get("pagina", 1, type=int)
        por_pagina = 40
        data_busca = request.args.get("data", "")
        data_inicio = request.args.get("data_inicio", "")
        data_fim = request.args.get("data_fim", "")
        criador_filtro = request.args.get("criador", "")
        
        # Query para buscar listas enviadas (produtos com enviado=1, validado=0)
        query = """
            SELECT 
                p.data_envio,
                p.responsavel_id,
                p.responsavel_pin,
                u.nome as criador_nome,
                COUNT(*) as total_produtos,
                SUM(p.quantidade) as quantidade_total
            FROM produtos p
            LEFT JOIN usuarios u ON p.usuario_id = u.id
            WHERE p.enviado = 1 AND p.validado = 0
        """
        
        params = []
        
        # Aplicar filtros
        if termo_pesquisa:
            query += " AND (p.ean LIKE %s OR p.nome LIKE %s)"
            params.extend([f"%{termo_pesquisa}%", f"%{termo_pesquisa}%"])
        
        if data_busca:
            query += " AND DATE(p.data_envio) = %s"
            params.append(data_busca)
        
        if data_inicio:
            query += " AND DATE(p.data_envio) >= %s"
            params.append(data_inicio)
        
        if data_fim:
            query += " AND DATE(p.data_envio) <= %s"
            params.append(data_fim)
        
        if criador_filtro:
            query += " AND u.nome = %s"
            params.append(criador_filtro)
        
        query += " GROUP BY p.data_envio, p.responsavel_id, p.responsavel_pin, u.nome"
        query += " ORDER BY p.data_envio DESC"
        
        # Paginação
        offset = (pagina - 1) * por_pagina
        query += f" LIMIT {por_pagina} OFFSET {offset}"
        
        listas_agrupadas = produto_repo.execute_custom_query(query, tuple(params) if params else None, fetch_all=True)
        
        # Contar total de listas
        count_query = """
            SELECT COUNT(DISTINCT (data_envio, responsavel_id, responsavel_pin))
            FROM produtos
            WHERE enviado = 1 AND validado = 0
        """
        total_listas = produto_repo.execute_custom_query(count_query, fetch_one=True)
        total_listas = total_listas.get('count', 0) if total_listas else 0
        
        paginacao = {
            'pagina_atual': pagina,
            'por_pagina': por_pagina,
            'total_listas': total_listas,
            'total_paginas': (total_listas + por_pagina - 1) // por_pagina
        }
        
        logger.info(f"Dashboard admin acessado: {len(listas_agrupadas)} listas exibidas")
        
        return render_template("admin.html",
                             listas_agrupadas=listas_agrupadas,
                             termo_pesquisa=termo_pesquisa,
                             paginacao=paginacao,
                             data_busca=data_busca,
                             data_inicio=data_inicio,
                             data_fim=data_fim,
                             criador_filtro=criador_filtro)
        
    except Exception as e:
        logger.error(f"Erro ao carregar dashboard admin: {e}")
        return render_template("admin.html", listas_agrupadas=[], error="Erro ao carregar dashboard")


# ========== GESTÃO DE USUÁRIOS ==========

@admin_bp.route("/usuarios")
@admin_required
def gerenciar_usuarios():
    """
    Página de gerenciamento de usuários
    """
    try:
        usuarios = usuario_repo.listar_todos_usuarios()
        return render_template("gerenciar_usuarios.html", usuarios=usuarios)
    except Exception as e:
        logger.error(f"Erro ao carregar usuários: {e}")
        return render_template("gerenciar_usuarios.html", usuarios=[], error="Erro ao carregar usuários")


@admin_bp.route("/api/usuarios", methods=["GET"])
@admin_required
def api_listar_usuarios():
    """
    API: Lista todos os usuários
    """
    try:
        usuarios = usuario_repo.listar_todos_usuarios()
        return jsonify(usuarios), 200
    except Exception as e:
        logger.error(f"Erro ao listar usuários: {e}")
        return jsonify({"error": "Erro ao carregar usuários"}), 500


@admin_bp.route("/api/usuarios/<int:usuario_id>", methods=["GET"])
@admin_required
def api_obter_usuario(usuario_id):
    """
    API: Obtém dados de um usuário específico
    """
    try:
        usuario = usuario_repo.find_by_id(usuario_id)
        
        if usuario:
            # Remover senha_hash por segurança
            usuario.pop('senha_hash', None)
            return jsonify(usuario), 200
        else:
            return jsonify({"error": "Usuário não encontrado"}), 404
            
    except Exception as e:
        logger.error(f"Erro ao obter usuário {usuario_id}: {e}")
        return jsonify({"error": "Erro ao carregar usuário"}), 500


@admin_bp.route("/api/usuarios", methods=["POST"])
@admin_required
def api_criar_usuario():
    """
    API: Cria um novo usuário
    """
    try:
        data = request.json
        
        nome = data.get("nome", "").strip()
        senha = data.get("senha", "").strip()
        admin = data.get("admin", 0)
        ativo = data.get("ativo", True)
        
        # Validações
        if not nome or not senha:
            return jsonify({"success": False, "message": "Nome e senha são obrigatórios"}), 400
        
        if len(nome) < 3:
            return jsonify({"success": False, "message": "Nome deve ter pelo menos 3 caracteres"}), 400
        
        if len(senha) < 6:
            return jsonify({"success": False, "message": "Senha deve ter pelo menos 6 caracteres"}), 400
        
        # Validar nível admin
        if admin not in [0, 1, 2]:
            return jsonify({"success": False, "message": "Nível de admin inválido"}), 400
        
        # Criar usuário
        usuario_id = usuario_repo.criar_usuario(nome, senha, admin, ativo)
        
        if usuario_id:
            logger.info(f"Usuário criado via admin: {nome} (ID: {usuario_id})")
            return jsonify({
                "success": True,
                "message": "Usuário criado com sucesso",
                "usuario_id": usuario_id
            }), 200
        else:
            return jsonify({"success": False, "message": "Usuário já existe"}), 400
            
    except Exception as e:
        logger.error(f"Erro ao criar usuário: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500


@admin_bp.route("/api/usuarios/<int:usuario_id>", methods=["PUT"])
@admin_required
def api_atualizar_usuario(usuario_id):
    """
    API: Atualiza dados de um usuário
    """
    try:
        data = request.json
        
        # Campos que podem ser atualizados
        updates = {}
        
        if "admin" in data:
            admin = data["admin"]
            if admin not in [0, 1, 2]:
                return jsonify({"success": False, "message": "Nível de admin inválido"}), 400
            
            if usuario_repo.atualizar_nivel_admin(usuario_id, admin):
                updates["admin"] = True
        
        if "ativo" in data:
            ativo = data["ativo"]
            if usuario_repo.ativar_desativar_usuario(usuario_id, ativo):
                updates["ativo"] = True
        
        if "senha" in data:
            senha = data["senha"].strip()
            if len(senha) < 6:
                return jsonify({"success": False, "message": "Senha deve ter pelo menos 6 caracteres"}), 400
            
            if usuario_repo.atualizar_senha(usuario_id, senha):
                updates["senha"] = True
        
        if updates:
            logger.info(f"Usuário {usuario_id} atualizado: {list(updates.keys())}")
            return jsonify({
                "success": True,
                "message": "Usuário atualizado com sucesso",
                "updates": list(updates.keys())
            }), 200
        else:
            return jsonify({"success": False, "message": "Nenhuma atualização realizada"}), 400
            
    except Exception as e:
        logger.error(f"Erro ao atualizar usuário {usuario_id}: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500


@admin_bp.route("/api/usuarios/<int:usuario_id>", methods=["DELETE"])
@admin_required
def api_excluir_usuario(usuario_id):
    """
    API: Deleta um usuário (marca como inativo)
    """
    try:
        # Verificar se há produtos associados
        query = "SELECT COUNT(*) as count FROM produtos WHERE usuario_id = %s"
        result = produto_repo.execute_custom_query(query, (usuario_id,), fetch_one=True)
        count_produtos = result.get('count', 0) if result else 0
        
        if count_produtos > 0:
            # Apenas desativar, não deletar
            if usuario_repo.ativar_desativar_usuario(usuario_id, False):
                logger.info(f"Usuário {usuario_id} desativado (tinha {count_produtos} produtos)")
                return jsonify({
                    "success": True,
                    "message": f"Usuário desativado (possui {count_produtos} produtos associados)"
                }), 200
            else:
                return jsonify({"success": False, "message": "Erro ao desativar usuário"}), 500
        else:
            # Deletar completamente
            if usuario_repo.delete(usuario_id):
                logger.info(f"Usuário {usuario_id} deletado")
                return jsonify({"success": True, "message": "Usuário excluído com sucesso"}), 200
            else:
                return jsonify({"success": False, "message": "Erro ao excluir usuário"}), 500
                
    except Exception as e:
        logger.error(f"Erro ao excluir usuário {usuario_id}: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500


# ========== VALIDAÇÃO DE LISTAS ==========

@admin_bp.route("/api/validar-lista", methods=["POST"])
@admin_required
def validar_lista_api():
    """
    API: Valida uma lista de produtos enviada
    """
    validador_id = session.get("usuario_id")
    
    try:
        data = request.json
        data_envio = data.get("data_envio")
        
        if not data_envio:
            return jsonify({"error": "Data de envio não fornecida"}), 400
        
        # Converter para datetime
        try:
            data_envio_obj = datetime.fromisoformat(data_envio.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({"error": "Formato de data inválido"}), 400
        
        # Marcar produtos como validados
        rowcount = produto_repo.marcar_como_validado(data_envio_obj, validador_id)
        
        if rowcount > 0:
            logger.info(f"{rowcount} produtos validados por usuário {validador_id}")
            return jsonify({
                "success": True,
                "message": f"{rowcount} produto(s) validado(s) com sucesso"
            }), 200
        else:
            return jsonify({"error": "Nenhum produto encontrado para validar"}), 404
            
    except Exception as e:
        logger.error(f"Erro ao validar lista: {e}")
        return jsonify({"error": f"Erro ao processar requisição: {str(e)}"}), 500


# ========== LISTAS UNIFICADAS ==========

@admin_bp.route("/listas-unificadas")
@admin_required
def listas_unificadas():
    """
    Página de listas unificadas
    """
    try:
        listas = lista_repo.listar_listas_unificadas()
        return render_template("listas_unificadas.html", listas=listas)
    except Exception as e:
        logger.error(f"Erro ao carregar listas unificadas: {e}")
        return render_template("listas_unificadas.html", listas=[], error="Erro ao carregar listas")


@admin_bp.route("/listas-unificadas/<int:lista_id>")
@admin_required
def detalhes_lista_unificada(lista_id):
    """
    Detalhes de uma lista unificada
    """
    try:
        lista = lista_repo.find_by_id(lista_id)
        
        if not lista:
            return redirect(url_for("admin.listas_unificadas"))
        
        produtos = lista_repo.obter_produtos_unificados(lista_id)
        
        return render_template("detalhes_lista_unificada.html", lista=lista, produtos=produtos)
    except Exception as e:
        logger.error(f"Erro ao carregar detalhes da lista {lista_id}: {e}")
        return redirect(url_for("admin.listas_unificadas"))


# ========== ESTATÍSTICAS ==========

@admin_bp.route("/api/estatisticas", methods=["GET"])
@admin_required
def api_estatisticas():
    """
    API: Retorna estatísticas gerais do sistema
    """
    try:
        # Estatísticas de usuários
        usuarios_por_tipo = usuario_repo.contar_usuarios_por_tipo()
        total_usuarios = sum(usuarios_por_tipo.values())
        
        # Estatísticas de produtos
        query_produtos = """
            SELECT 
                COUNT(*) as total_produtos,
                SUM(CASE WHEN enviado = 0 THEN 1 ELSE 0 END) as nao_enviados,
                SUM(CASE WHEN enviado = 1 AND validado = 0 THEN 1 ELSE 0 END) as aguardando_validacao,
                SUM(CASE WHEN validado = 1 THEN 1 ELSE 0 END) as validados
            FROM produtos
            WHERE ativo = TRUE
        """
        
        stats_produtos = produto_repo.execute_custom_query(query_produtos, fetch_one=True)
        
        estatisticas = {
            "usuarios": {
                "total": total_usuarios,
                "por_tipo": usuarios_por_tipo
            },
            "produtos": stats_produtos if stats_produtos else {}
        }
        
        return jsonify(estatisticas), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        return jsonify({"error": "Erro ao carregar estatísticas"}), 500

