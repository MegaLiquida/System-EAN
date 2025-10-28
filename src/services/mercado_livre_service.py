"""
Serviço de Integração com API do Mercado Livre
Gerencia autenticação, busca de produtos e operações com a API
"""
import requests
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class MercadoLivreService:
    """
    Serviço para integração com API do Mercado Livre
    """
    
    # URLs da API
    API_BASE_URL = "https://api.mercadolibre.com"
    AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
    TOKEN_URL = f"{API_BASE_URL}/oauth/token"
    
    def __init__(self):
        """
        Inicializa o serviço com credenciais das variáveis de ambiente
        """
        self.client_id = os.environ.get('MERCADO_LIVRE_CLIENT_ID')
        self.client_secret = os.environ.get('MERCADO_LIVRE_CLIENT_SECRET')
        self.redirect_uri = os.environ.get('MERCADO_LIVRE_REDIRECT_URI', 'https://system-ean.onrender.com/ml_callback')
        
        # Token de acesso (será obtido via OAuth)
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        if not self.client_id or not self.client_secret:
            logger.warning("Credenciais do Mercado Livre não configuradas")
    
    
    def is_configured(self) -> bool:
        """
        Verifica se as credenciais estão configuradas
        
        Returns:
            True se configurado, False caso contrário
        """
        return bool(self.client_id and self.client_secret)
    
    
    def get_authorization_url(self, state: str = None) -> str:
        """
        Gera URL para autorização OAuth do Mercado Livre
        
        Args:
            state: String opcional para validação de segurança
        
        Returns:
            URL de autorização
        """
        if not self.is_configured():
            raise ValueError("Credenciais do Mercado Livre não configuradas")
        
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri
        }
        
        if state:
            params['state'] = state
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        url = f"{self.AUTH_URL}?{query_string}"
        
        logger.info(f"URL de autorização gerada: {url}")
        return url
    
    
    def exchange_code_for_token(self, code: str) -> Dict:
        """
        Troca o código de autorização por token de acesso
        
        Args:
            code: Código de autorização recebido do callback
        
        Returns:
            Dicionário com informações do token
        
        Raises:
            requests.RequestException: Se houver erro na requisição
        """
        if not self.is_configured():
            raise ValueError("Credenciais do Mercado Livre não configuradas")
        
        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': self.redirect_uri
        }
        
        try:
            response = requests.post(self.TOKEN_URL, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Armazenar tokens
            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            
            # Calcular expiração (geralmente 6 horas)
            expires_in = token_data.get('expires_in', 21600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            logger.info("Token de acesso obtido com sucesso")
            return token_data
            
        except requests.RequestException as e:
            logger.error(f"Erro ao obter token: {e}")
            raise
    
    
    def refresh_access_token(self) -> Dict:
        """
        Renova o token de acesso usando refresh token
        
        Returns:
            Dicionário com informações do novo token
        
        Raises:
            requests.RequestException: Se houver erro na requisição
        """
        if not self.refresh_token:
            raise ValueError("Refresh token não disponível")
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token
        }
        
        try:
            response = requests.post(self.TOKEN_URL, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Atualizar tokens
            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            
            expires_in = token_data.get('expires_in', 21600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            logger.info("Token renovado com sucesso")
            return token_data
            
        except requests.RequestException as e:
            logger.error(f"Erro ao renovar token: {e}")
            raise
    
    
    def is_token_valid(self) -> bool:
        """
        Verifica se o token atual ainda é válido
        
        Returns:
            True se válido, False caso contrário
        """
        if not self.access_token or not self.token_expires_at:
            return False
        
        # Considerar inválido se faltar menos de 5 minutos para expirar
        return datetime.now() < (self.token_expires_at - timedelta(minutes=5))
    
    
    def ensure_valid_token(self):
        """
        Garante que há um token válido, renovando se necessário
        
        Raises:
            ValueError: Se não houver refresh token disponível
        """
        if not self.is_token_valid():
            if self.refresh_token:
                self.refresh_access_token()
            else:
                raise ValueError("Token inválido e sem refresh token disponível")
    
    
    def search_product_by_ean(self, ean: str) -> Optional[Dict]:
        """
        Busca produto no Mercado Livre pelo código EAN
        
        Args:
            ean: Código EAN do produto (8 ou 13 dígitos)
        
        Returns:
            Dicionário com informações do produto ou None se não encontrado
        """
        if not self.is_configured():
            logger.warning("API do Mercado Livre não configurada")
            return None
        
        try:
            # Buscar por EAN (não requer autenticação)
            url = f"{self.API_BASE_URL}/sites/MLB/search"
            params = {
                'q': ean,
                'limit': 1
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            if results:
                product = results[0]
                logger.info(f"Produto encontrado: {product.get('title')}")
                
                return {
                    'id': product.get('id'),
                    'title': product.get('title'),
                    'price': product.get('price'),
                    'currency_id': product.get('currency_id'),
                    'thumbnail': product.get('thumbnail'),
                    'permalink': product.get('permalink'),
                    'condition': product.get('condition'),
                    'available_quantity': product.get('available_quantity'),
                    'sold_quantity': product.get('sold_quantity')
                }
            else:
                logger.info(f"Nenhum produto encontrado para EAN: {ean}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Erro ao buscar produto: {e}")
            return None
    
    
    def get_product_details(self, product_id: str) -> Optional[Dict]:
        """
        Obtém detalhes completos de um produto
        
        Args:
            product_id: ID do produto no Mercado Livre
        
        Returns:
            Dicionário com detalhes do produto ou None se erro
        """
        try:
            url = f"{self.API_BASE_URL}/items/{product_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            product = response.json()
            
            # Extrair atributos relevantes
            attributes = {}
            for attr in product.get('attributes', []):
                attributes[attr.get('id')] = attr.get('value_name')
            
            return {
                'id': product.get('id'),
                'title': product.get('title'),
                'price': product.get('price'),
                'currency_id': product.get('currency_id'),
                'condition': product.get('condition'),
                'thumbnail': product.get('thumbnail'),
                'pictures': [p.get('url') for p in product.get('pictures', [])],
                'permalink': product.get('permalink'),
                'available_quantity': product.get('available_quantity'),
                'sold_quantity': product.get('sold_quantity'),
                'attributes': attributes,
                'warranty': product.get('warranty'),
                'shipping': product.get('shipping')
            }
            
        except requests.RequestException as e:
            logger.error(f"Erro ao obter detalhes do produto: {e}")
            return None
    
    
    def extract_product_info(self, ean: str) -> Optional[Dict]:
        """
        Busca e extrai informações úteis do produto para cadastro
        
        Args:
            ean: Código EAN do produto
        
        Returns:
            Dicionário com informações extraídas ou None
        """
        # Buscar produto
        product = self.search_product_by_ean(ean)
        
        if not product:
            return None
        
        # Obter detalhes completos
        details = self.get_product_details(product['id'])
        
        if not details:
            return product  # Retornar informações básicas
        
        # Extrair informações úteis dos atributos
        attributes = details.get('attributes', {})
        
        return {
            'ean': ean,
            'nome': details.get('title'),
            'cor': attributes.get('COLOR') or attributes.get('MAIN_COLOR'),
            'voltagem': attributes.get('VOLTAGE') or attributes.get('POWER_SUPPLY_TYPE'),
            'modelo': attributes.get('MODEL') or attributes.get('ALPHANUMERIC_MODEL'),
            'marca': attributes.get('BRAND'),
            'preco_referencia': details.get('price'),
            'condicao': details.get('condition'),
            'thumbnail': details.get('thumbnail'),
            'link': details.get('permalink')
        }


# Instância global do serviço
mercado_livre_service = MercadoLivreService()


# Funções auxiliares para uso simplificado

def buscar_produto_por_ean(ean: str) -> Optional[Dict]:
    """
    Função auxiliar para buscar produto por EAN
    
    Args:
        ean: Código EAN do produto
    
    Returns:
        Informações do produto ou None
    """
    return mercado_livre_service.extract_product_info(ean)


def is_mercado_livre_configured() -> bool:
    """
    Verifica se a integração com Mercado Livre está configurada
    
    Returns:
        True se configurado, False caso contrário
    """
    return mercado_livre_service.is_configured()

