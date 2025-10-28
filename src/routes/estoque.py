"""
Blueprint de Estoque
Gerencia estoque local, ruas, movimentações e entrada/saída de produtos
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, send_file
from src.repositories.estoque_repository import EstoqueRepository
from src.repositories.produto_repository import ProdutoRepository
from src.routes.auth import login_required
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Criar Blueprint
estoque_bp = Blueprint('estoque', __name__)

# Instanciar repositórios
estoque_repo = EstoqueRepository()
produto_repo = ProdutoRepository()


@estoque_bp.route("/")
@estoque_bp.route("/index")
@login_required
def index():
    """
    Página principal do sistema de estoque
    """
    try:
        ruas = estoque_repo.listar_ruas()
        return render_template("estoque.html", ruas=ruas)
    except Exception as e:
        logger.error(f"Erro ao carregar estoque: {e}")
        return render_template("estoque.html", ruas=[], error="Erro ao carregar estoque")


@estoque_bp.route("/local")
@login_required
def estoque_local():
    """
    Página de estoque local com ruas e produtos
    """
    try:
        ruas = estoque_repo.listar_ruas()
        
        # Adicionar produtos de cada rua
        for rua in ruas:
            rua['produtos'] = produto_repo.buscar_produtos_na_rua(rua['id'])
        
        return render_template("estoque_local_template.html", ruas=ruas)
    except Exception as e:
        logger.error(f"Erro ao carregar estoque local: {e}")
        return render_template("estoque_local_template.html", ruas=[], error="Erro ao carregar estoque")


# ========== API DE RUAS ==========

@estoque_bp.route("/api/ruas", methods=["GET"])
@login_required
def get_ruas():
    """
    API: Lista todas as ruas
    """
    try:
        ruas = estoque_repo.listar_ruas()
        return jsonify(ruas), 200
    except Exception as e:
        logger.error(f"Erro ao obter ruas: {e}")
        return jsonify({"error": "Erro ao carregar ruas"}), 500


@estoque_bp.route("/api/rua", methods=["POST"])
@login_required
def adicionar_rua():
    """
    API: Cria uma nova rua
    """
    try:
        data = request.json
        nome = data.get("nome", "").strip()
        
        if not nome:
            return jsonify({"success": False, "message": "Nome da rua é obrigatório"}), 400
        
        # Verificar se rua já existe
        rua_existente = estoque_repo.buscar_rua_por_nome(nome)
        if rua_existente:
            return jsonify({"success": False, "message": "Rua já existe"}), 400
        
        # Criar rua
        rua_id = estoque_repo.criar_rua(nome)
        
        if rua_id:
            logger.info(f"Rua criada: {nome} (ID: {rua_id})")
            return jsonify({"success": True, "message": "Rua criada com sucesso", "rua_id": rua_id}), 200
        else:
            return jsonify({"success": False, "message": "Erro ao criar rua"}), 500
            
    except Exception as e:
        logger.error(f"Erro ao criar rua: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500


@estoque_bp.route("/api/rua/<int:rua_id>", methods=["DELETE"])
@login_required
def excluir_rua(rua_id):
    """
    API: Deleta uma rua (se não tiver produtos)
    """
    try:
        # Verificar se há produtos na rua
        count = produto_repo.contar_produtos_na_rua(rua_id)
        
        if count > 0:
            return jsonify({
                "success": False, 
                "message": f"Não é possível excluir a rua. Existem {count} produto(s) nela."
            }), 400
        
        # Deletar rua
        if estoque_repo.deletar_rua(rua_id):
            logger.info(f"Rua {rua_id} deletada")
            return jsonify({"success": True, "message": "Rua excluída com sucesso"}), 200
        else:
            return jsonify({"success": False, "message": "Erro ao excluir rua"}), 500
            
    except Exception as e:
        logger.error(f"Erro ao excluir rua: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500


@estoque_bp.route("/api/rua/<int:rua_id>/mover", methods=["PUT"])
@login_required
def mover_rua(rua_id):
    """
    API: Move rua para nova posição
    """
    try:
        data = request.json
        nova_posicao = data.get("posicao")
        
        if nova_posicao is None:
            return jsonify({"success": False, "message": "Posição não fornecida"}), 400
        
        if estoque_repo.mover_rua(rua_id, nova_posicao):
            logger.info(f"Rua {rua_id} movida para posição {nova_posicao}")
            return jsonify({"success": True, "message": "Rua movida com sucesso"}), 200
        else:
            return jsonify({"success": False, "message": "Erro ao mover rua"}), 500
            
    except Exception as e:
        logger.error(f"Erro ao mover rua: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500


@estoque_bp.route("/api/scan_qr_code_rua", methods=["GET"])
@login_required
def api_scan_qr_code_rua():
    """
    API: Busca rua por nome (QR Code)
    """
    try:
        nome_rua = request.args.get("nome_rua")
        
        if not nome_rua:
            return jsonify({"success": False, "message": "Nome da rua não fornecido"}), 400
        
        rua = estoque_repo.buscar_rua_por_nome(nome_rua)
        
        if rua:
            # Buscar produtos da rua
            produtos = produto_repo.buscar_produtos_na_rua(rua["id"])
            return jsonify({"success": True, "rua": rua, "produtos": produtos}), 200
        else:
            return jsonify({"success": False, "message": "Rua não encontrada"}), 404
            
    except Exception as e:
        logger.error(f"Erro ao buscar rua por QR Code: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500


# ========== API DE ENTRADA/SAÍDA DE PRODUTOS ==========

@estoque_bp.route("/api/entrada_produto_rua", methods=["POST"])
@login_required
def api_entrada_produto_rua():
    """
    API: Adiciona produto a uma rua
    """
    usuario_id = session.get("usuario_id")
    
    try:
        data = request.json
        
        ean = data.get("ean")
        rua_id = data.get("rua_id")
        quantidade = data.get("quantidade", 1)
        
        # Validações
        if not ean or not rua_id:
            return jsonify({"success": False, "message": "EAN e rua são obrigatórios"}), 400
        
        try:
            quantidade = int(quantidade)
            if quantidade <= 0:
                return jsonify({"success": False, "message": "Quantidade deve ser maior que zero"}), 400
        except ValueError:
            return jsonify({"success": False, "message": "Quantidade inválida"}), 400
        
        # Buscar informações do produto
        produto_info = produto_repo.buscar_por_ean(ean)
        
        if not produto_info:
            return jsonify({"success": False, "message": "Produto não encontrado no banco de dados"}), 404
        
        # Adicionar produto à rua
        produto_id = produto_repo.adicionar_produto_rua(ean, rua_id, quantidade, produto_info, usuario_id)
        
        # Registrar movimentação
        rua = estoque_repo.find_by_id(rua_id)
        estoque_repo.registrar_movimentacao(
            tipo='entrada',
            ean=ean,
            nome=produto_info.get('nome'),
            quantidade=quantidade,
            rua_id=rua_id,
            usuario_id=usuario_id,
            cor=produto_info.get('cor'),
            voltagem=produto_info.get('voltagem'),
            modelo=produto_info.get('modelo'),
            observacao=f"Entrada na rua {rua['nome'] if rua else rua_id}"
        )
        
        logger.info(f"Produto {ean} adicionado à rua {rua_id} (quantidade: {quantidade})")
        
        return jsonify({
            "success": True,
            "message": "Produto adicionado à rua com sucesso",
            "produto_id": produto_id
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao adicionar produto à rua: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500


@estoque_bp.route("/api/saida_produto_rua", methods=["POST"])
@login_required
def api_saida_produto_rua():
    """
    API: Remove quantidade de produto de uma rua
    """
    usuario_id = session.get("usuario_id")
    
    try:
        data = request.json
        
        ean = data.get("ean")
        rua_id = data.get("rua_id")
        quantidade = data.get("quantidade", 1)
        
        # Validações
        if not ean or not rua_id:
            return jsonify({"success": False, "message": "EAN e rua são obrigatórios"}), 400
        
        try:
            quantidade = int(quantidade)
            if quantidade <= 0:
                return jsonify({"success": False, "message": "Quantidade deve ser maior que zero"}), 400
        except ValueError:
            return jsonify({"success": False, "message": "Quantidade inválida"}), 400
        
        # Remover produto da rua
        sucesso, quantidade_restante, acao = produto_repo.remover_produto_rua(ean, rua_id, quantidade)
        
        if sucesso:
            # Buscar informações do produto para movimentação
            produto_info = produto_repo.buscar_por_ean(ean)
            
            # Registrar movimentação
            rua = estoque_repo.find_by_id(rua_id)
            estoque_repo.registrar_movimentacao(
                tipo='saida',
                ean=ean,
                nome=produto_info.get('nome') if produto_info else 'Produto',
                quantidade=quantidade,
                rua_id=rua_id,
                usuario_id=usuario_id,
                cor=produto_info.get('cor') if produto_info else None,
                voltagem=produto_info.get('voltagem') if produto_info else None,
                modelo=produto_info.get('modelo') if produto_info else None,
                observacao=f"Saída da rua {rua['nome'] if rua else rua_id}"
            )
            
            logger.info(f"Produto {ean} removido da rua {rua_id} (quantidade: {quantidade})")
            
            return jsonify({
                "success": True,
                "message": acao,
                "quantidade_restante": quantidade_restante
            }), 200
        else:
            return jsonify({"success": False, "message": acao}), 400
            
    except Exception as e:
        logger.error(f"Erro ao remover produto da rua: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500


@estoque_bp.route("/api/estoque_rua/<int:rua_id>", methods=["GET"])
@login_required
def api_estoque_rua(rua_id):
    """
    API: Obtém produtos de uma rua específica
    """
    try:
        produtos = produto_repo.buscar_produtos_na_rua(rua_id)
        return jsonify(produtos), 200
    except Exception as e:
        logger.error(f"Erro ao obter estoque da rua {rua_id}: {e}")
        return jsonify({"error": "Erro ao carregar estoque"}), 500


# ========== API DE MOVIMENTAÇÕES ==========

@estoque_bp.route("/api/movimentacoes", methods=["GET"])
@login_required
def consultar_movimentacoes():
    """
    API: Lista movimentações com filtros
    """
    try:
        # Parâmetros de filtro
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))
        tipo = request.args.get("tipo")
        usuario_id = request.args.get("usuario_id")
        rua_id = request.args.get("rua_id")
        data_inicio = request.args.get("data_inicio")
        data_fim = request.args.get("data_fim")
        
        filtros = {}
        if tipo:
            filtros['tipo'] = tipo
        if usuario_id:
            filtros['usuario_id'] = int(usuario_id)
        if rua_id:
            filtros['rua_id'] = int(rua_id)
        if data_inicio:
            filtros['data_inicio'] = datetime.fromisoformat(data_inicio)
        if data_fim:
            filtros['data_fim'] = datetime.fromisoformat(data_fim)
        
        movimentacoes = estoque_repo.listar_movimentacoes(limit, offset, filtros)
        
        return jsonify(movimentacoes), 200
        
    except Exception as e:
        logger.error(f"Erro ao consultar movimentações: {e}")
        return jsonify({"error": "Erro ao consultar movimentações"}), 500


@estoque_bp.route("/api/movimentacoes/estatisticas", methods=["GET"])
@login_required
def obter_estatisticas_movimentacao():
    """
    API: Obtém estatísticas de movimentações
    """
    try:
        data_inicio = request.args.get("data_inicio")
        data_fim = request.args.get("data_fim")
        
        if data_inicio:
            data_inicio = datetime.fromisoformat(data_inicio)
        if data_fim:
            data_fim = datetime.fromisoformat(data_fim)
        
        estatisticas = estoque_repo.obter_estatisticas_movimentacoes(data_inicio, data_fim)
        
        return jsonify(estatisticas), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        return jsonify({"error": "Erro ao obter estatísticas"}), 500


@estoque_bp.route("/api/movimentacoes/estatisticas_por_usuario", methods=["GET"])
@login_required
def api_estatisticas_movimentacao_por_usuario():
    """
    API: Obtém estatísticas de movimentações por usuário
    """
    try:
        data_inicio = request.args.get("data_inicio")
        data_fim = request.args.get("data_fim")
        
        if data_inicio:
            data_inicio = datetime.fromisoformat(data_inicio)
        if data_fim:
            data_fim = datetime.fromisoformat(data_fim)
        
        estatisticas = estoque_repo.obter_estatisticas_por_usuario(data_inicio, data_fim)
        
        return jsonify(estatisticas), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas por usuário: {e}")
        return jsonify({"error": "Erro ao obter estatísticas"}), 500


@estoque_bp.route("/api/movimentacoes/registrar", methods=["POST"])
@login_required
def registrar_movimentacao_manual():
    """
    API: Registra movimentação manual
    """
    usuario_id = session.get("usuario_id")
    
    try:
        data = request.json
        
        tipo = data.get("tipo")
        ean = data.get("ean")
        nome = data.get("nome")
        quantidade = data.get("quantidade")
        rua_id = data.get("rua_id")
        observacao = data.get("observacao")
        
        # Validações
        if not all([tipo, ean, nome, quantidade, rua_id]):
            return jsonify({"success": False, "message": "Dados incompletos"}), 400
        
        if tipo not in ['entrada', 'saida']:
            return jsonify({"success": False, "message": "Tipo inválido (deve ser 'entrada' ou 'saida')"}), 400
        
        try:
            quantidade = int(quantidade)
            if quantidade <= 0:
                return jsonify({"success": False, "message": "Quantidade deve ser maior que zero"}), 400
        except ValueError:
            return jsonify({"success": False, "message": "Quantidade inválida"}), 400
        
        # Registrar movimentação
        movimentacao_id = estoque_repo.registrar_movimentacao(
            tipo=tipo,
            ean=ean,
            nome=nome,
            quantidade=quantidade,
            rua_id=rua_id,
            usuario_id=usuario_id,
            cor=data.get("cor"),
            voltagem=data.get("voltagem"),
            modelo=data.get("modelo"),
            observacao=observacao
        )
        
        logger.info(f"Movimentação manual registrada: {tipo} - {ean} (ID: {movimentacao_id})")
        
        return jsonify({
            "success": True,
            "message": "Movimentação registrada com sucesso",
            "movimentacao_id": movimentacao_id
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao registrar movimentação manual: {e}")
        return jsonify({"success": False, "message": "Erro interno do servidor"}), 500

