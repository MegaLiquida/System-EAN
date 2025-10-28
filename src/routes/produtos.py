"""
Blueprint de Produtos
Gerencia cadastro, busca e gestão de produtos
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from src.repositories.produto_repository import ProdutoRepository
from src.routes.auth import login_required
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Criar Blueprint
produtos_bp = Blueprint('produtos', __name__)

# Instanciar repositório
produto_repo = ProdutoRepository()


@produtos_bp.route("/")
@produtos_bp.route("/index")
@login_required
def index():
    """
    Página principal do sistema de cadastro de produtos
    Exibe produtos não enviados do usuário
    """
    usuario_id = session.get("usuario_id")
    
    try:
        produtos = produto_repo.listar_produtos_usuario(usuario_id, apenas_nao_enviados=True)
        return render_template("index.html", produtos=produtos)
    except Exception as e:
        logger.error(f"Erro ao carregar produtos do usuário {usuario_id}: {e}")
        return render_template("index.html", produtos=[], error="Erro ao carregar produtos")


# ========== API DE PRODUTOS ==========

@produtos_bp.route("/api/produtos", methods=["GET"])
@login_required
def get_produtos():
    """
    API: Lista produtos do usuário logado (não enviados)
    """
    usuario_id = session.get("usuario_id")
    
    try:
        produtos = produto_repo.listar_produtos_usuario(usuario_id, apenas_nao_enviados=True)
        return jsonify(produtos), 200
    except Exception as e:
        logger.error(f"Erro ao obter produtos: {e}")
        return jsonify({"error": "Erro ao carregar produtos"}), 500


@produtos_bp.route("/api/produtos", methods=["POST"])
@login_required
def add_produto():
    """
    API: Adiciona novo produto ou atualiza quantidade se já existe
    """
    usuario_id = session.get("usuario_id")
    
    try:
        produto = request.json
        
        # Validações
        if not produto or not produto.get("ean") or not produto.get("nome"):
            return jsonify({"error": "Dados do produto incompletos (EAN e nome obrigatórios)"}), 400
        
        # Validar motivo de manutenção se destino for manutenção
        if produto.get("destino") == "manutencao":
            motivo_manutencao = produto.get("motivo_manutencao", "").strip()
            if not motivo_manutencao:
                return jsonify({"error": "Motivo da manutenção é obrigatório quando o destino for Manutenção"}), 400
            if len(motivo_manutencao) < 10:
                return jsonify({"error": "Motivo da manutenção deve ter pelo menos 10 caracteres"}), 400
        
        # Validar e converter quantidade
        try:
            produto["quantidade"] = int(produto.get("quantidade", 1))
            if produto["quantidade"] <= 0:
                return jsonify({"error": "Quantidade deve ser maior que zero"}), 400
        except ValueError:
            return jsonify({"error": "Quantidade inválida"}), 400
        
        # Criar ou atualizar produto
        produto_id = produto_repo.criar_ou_atualizar_produto(produto, usuario_id)
        
        if produto_id:
            logger.info(f"Produto {produto['ean']} adicionado/atualizado pelo usuário {usuario_id}")
            
            # Retornar lista atualizada
            produtos_atualizados = produto_repo.listar_produtos_usuario(usuario_id, apenas_nao_enviados=True)
            return jsonify(produtos_atualizados), 200
        else:
            return jsonify({"error": "Erro ao salvar produto"}), 500
            
    except Exception as e:
        logger.error(f"Erro ao adicionar produto: {e}")
        return jsonify({"error": f"Erro ao processar requisição: {str(e)}"}), 500


@produtos_bp.route("/api/produtos/<int:produto_id>", methods=["DELETE"])
@login_required
def delete_produto(produto_id):
    """
    API: Deleta um produto
    """
    usuario_id = session.get("usuario_id")
    
    try:
        if produto_repo.deletar_produto(produto_id, usuario_id):
            logger.info(f"Produto {produto_id} deletado pelo usuário {usuario_id}")
            return jsonify({"success": True, "message": "Produto excluído com sucesso"}), 200
        else:
            return jsonify({"error": "Erro ao excluir produto (não encontrado ou sem permissão)"}), 404
            
    except Exception as e:
        logger.error(f"Erro ao deletar produto {produto_id}: {e}")
        return jsonify({"error": "Erro ao excluir produto"}), 500


@produtos_bp.route("/api/buscar-ean/<ean>", methods=["GET"])
@login_required
def buscar_ean(ean):
    """
    API: Busca produto por EAN no banco de dados
    """
    usuario_id = session.get("usuario_id")
    
    try:
        # Buscar produto do usuário
        produto = produto_repo.buscar_por_ean(ean, usuario_id)
        
        if produto:
            return jsonify({
                "success": True,
                "produto": produto
            }), 200
        else:
            # Buscar produto de qualquer usuário (para pegar informações)
            produto_geral = produto_repo.buscar_por_ean(ean)
            
            if produto_geral:
                return jsonify({
                    "success": True,
                    "produto": {
                        "ean": produto_geral["ean"],
                        "nome": produto_geral.get("nome"),
                        "cor": produto_geral.get("cor"),
                        "voltagem": produto_geral.get("voltagem"),
                        "modelo": produto_geral.get("modelo")
                    },
                    "novo": True
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "message": "Produto não encontrado no banco de dados"
                }), 404
                
    except Exception as e:
        logger.error(f"Erro ao buscar EAN {ean}: {e}")
        return jsonify({"error": "Erro ao buscar produto"}), 500


@produtos_bp.route("/api/buscar-mercado-livre/<ean>", methods=["GET"])
@login_required
def buscar_mercado_livre(ean):
    """
    API: Busca produto no Mercado Livre por EAN
    """
    try:
        # Importar módulo de integração com Mercado Livre
        from src.mercado_livre import buscar_produto_mercado_livre
        
        resultado = buscar_produto_mercado_livre(ean)
        
        if resultado and resultado.get("success"):
            logger.info(f"Produto {ean} encontrado no Mercado Livre")
            return jsonify(resultado), 200
        else:
            logger.warning(f"Produto {ean} não encontrado no Mercado Livre")
            return jsonify({
                "success": False,
                "message": "Produto não encontrado no Mercado Livre"
            }), 404
            
    except Exception as e:
        logger.error(f"Erro ao buscar produto no Mercado Livre: {e}")
        return jsonify({
            "success": False,
            "error": "Erro ao buscar no Mercado Livre"
        }), 500


@produtos_bp.route("/api/enviar-produtos", methods=["POST"])
@login_required
def enviar_produtos():
    """
    API: Marca produtos como enviados
    """
    usuario_id = session.get("usuario_id")
    
    try:
        data = request.json
        
        # Validações
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        responsavel_id = data.get("responsavel_id")
        pin = data.get("pin")
        destino = data.get("destino", "mercado_livre")
        
        if not responsavel_id or not pin:
            return jsonify({"error": "Responsável e PIN são obrigatórios"}), 400
        
        # Marcar produtos como enviados
        data_envio = datetime.now()
        rowcount = produto_repo.marcar_como_enviado(
            usuario_id, 
            data_envio, 
            responsavel_id, 
            pin, 
            destino
        )
        
        if rowcount > 0:
            logger.info(f"{rowcount} produtos marcados como enviados pelo usuário {usuario_id}")
            return jsonify({
                "success": True,
                "message": f"{rowcount} produto(s) enviado(s) com sucesso",
                "total": rowcount
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Nenhum produto para enviar"
            }), 400
            
    except Exception as e:
        logger.error(f"Erro ao enviar produtos: {e}")
        return jsonify({"error": "Erro ao enviar produtos"}), 500


@produtos_bp.route("/api/produtos-loja", methods=["GET"])
@login_required
def api_produtos_loja():
    """
    API: Lista produtos com destino loja
    """
    usuario_id = session.get("usuario_id")
    
    try:
        # Query customizada para produtos de loja
        query = """
            SELECT * FROM produtos 
            WHERE usuario_id = %s AND destino = 'loja' AND enviado = 0 AND ativo = TRUE
            ORDER BY timestamp DESC
        """
        
        produtos = produto_repo.execute_custom_query(query, (usuario_id,), fetch_all=True)
        return jsonify(produtos), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter produtos de loja: {e}")
        return jsonify({"error": "Erro ao carregar produtos"}), 500


@produtos_bp.route("/api/produtos-manutencao", methods=["GET"])
@login_required
def api_produtos_manutencao():
    """
    API: Lista produtos com destino manutenção
    """
    usuario_id = session.get("usuario_id")
    
    try:
        # Query customizada para produtos de manutenção
        query = """
            SELECT * FROM produtos 
            WHERE usuario_id = %s AND destino = 'manutencao' AND enviado = 0 AND ativo = TRUE
            ORDER BY timestamp DESC
        """
        
        produtos = produto_repo.execute_custom_query(query, (usuario_id,), fetch_all=True)
        return jsonify(produtos), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter produtos de manutenção: {e}")
        return jsonify({"error": "Erro ao carregar produtos"}), 500


@produtos_bp.route("/api/produtos-assistencia", methods=["GET"])
@login_required
def api_produtos_assistencia():
    """
    API: Lista produtos com destino assistência técnica
    """
    usuario_id = session.get("usuario_id")
    
    try:
        # Query customizada para produtos de assistência
        query = """
            SELECT * FROM produtos 
            WHERE usuario_id = %s AND destino = 'assistencia_tecnica' AND enviado = 0 AND ativo = TRUE
            ORDER BY timestamp DESC
        """
        
        produtos = produto_repo.execute_custom_query(query, (usuario_id,), fetch_all=True)
        return jsonify(produtos), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter produtos de assistência: {e}")
        return jsonify({"error": "Erro ao carregar produtos"}), 500

