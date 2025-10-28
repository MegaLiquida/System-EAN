"""
Funções Utilitárias
Funções auxiliares reutilizáveis em todo o sistema
"""
from datetime import datetime, timedelta
import re
import hashlib


def validar_ean(ean):
    """
    Valida código EAN (8 ou 13 dígitos)
    
    Args:
        ean: Código EAN a validar
    
    Returns:
        True se válido, False caso contrário
    """
    if not ean:
        return False
    
    # Remover espaços e caracteres não numéricos
    ean = re.sub(r'\D', '', str(ean))
    
    # Verificar comprimento
    if len(ean) not in [8, 13]:
        return False
    
    # Validar dígito verificador
    try:
        digits = [int(d) for d in ean]
        check_digit = digits[-1]
        
        # Calcular dígito verificador
        if len(ean) == 13:
            # EAN-13
            odd_sum = sum(digits[::2][:-1])
            even_sum = sum(digits[1::2])
            total = odd_sum + (even_sum * 3)
        else:
            # EAN-8
            odd_sum = sum(digits[1::2])
            even_sum = sum(digits[::2][:-1])
            total = (odd_sum * 3) + even_sum
        
        calculated_check = (10 - (total % 10)) % 10
        
        return check_digit == calculated_check
    except (ValueError, IndexError):
        return False


def formatar_ean(ean):
    """
    Formata código EAN removendo caracteres não numéricos
    
    Args:
        ean: Código EAN a formatar
    
    Returns:
        EAN formatado (apenas dígitos)
    """
    if not ean:
        return None
    
    return re.sub(r'\D', '', str(ean))


def formatar_data(data, formato='%d/%m/%Y'):
    """
    Formata data para string
    
    Args:
        data: Objeto datetime ou string ISO
        formato: Formato de saída
    
    Returns:
        Data formatada como string
    """
    if not data:
        return None
    
    if isinstance(data, str):
        try:
            data = datetime.fromisoformat(data.replace('Z', '+00:00'))
        except ValueError:
            return data
    
    if isinstance(data, datetime):
        return data.strftime(formato)
    
    return str(data)


def formatar_data_hora(data, formato='%d/%m/%Y %H:%M'):
    """
    Formata data e hora para string
    
    Args:
        data: Objeto datetime ou string ISO
        formato: Formato de saída
    
    Returns:
        Data e hora formatadas como string
    """
    return formatar_data(data, formato)


def calcular_idade_dias(data):
    """
    Calcula idade em dias desde uma data
    
    Args:
        data: Data de referência
    
    Returns:
        Número de dias desde a data
    """
    if not data:
        return None
    
    if isinstance(data, str):
        try:
            data = datetime.fromisoformat(data.replace('Z', '+00:00'))
        except ValueError:
            return None
    
    if isinstance(data, datetime):
        delta = datetime.now() - data
        return delta.days
    
    return None


def gerar_hash(texto):
    """
    Gera hash SHA256 de um texto
    
    Args:
        texto: Texto a ser hasheado
    
    Returns:
        Hash SHA256 em hexadecimal
    """
    if not texto:
        return None
    
    return hashlib.sha256(str(texto).encode('utf-8')).hexdigest()


def truncar_texto(texto, max_length=100, sufixo='...'):
    """
    Trunca texto se exceder comprimento máximo
    
    Args:
        texto: Texto a truncar
        max_length: Comprimento máximo
        sufixo: Sufixo a adicionar se truncado
    
    Returns:
        Texto truncado
    """
    if not texto:
        return ''
    
    texto = str(texto)
    
    if len(texto) <= max_length:
        return texto
    
    return texto[:max_length - len(sufixo)] + sufixo


def sanitizar_nome_arquivo(nome):
    """
    Sanitiza nome de arquivo removendo caracteres inválidos
    
    Args:
        nome: Nome do arquivo
    
    Returns:
        Nome sanitizado
    """
    if not nome:
        return 'arquivo'
    
    # Remover caracteres não permitidos
    nome = re.sub(r'[<>:"/\\|?*]', '', nome)
    
    # Substituir espaços por underscores
    nome = nome.replace(' ', '_')
    
    # Limitar comprimento
    if len(nome) > 200:
        nome = nome[:200]
    
    return nome or 'arquivo'


def paginar(query_result, pagina=1, por_pagina=20):
    """
    Pagina resultados de query
    
    Args:
        query_result: Lista de resultados
        pagina: Número da página (1-indexed)
        por_pagina: Itens por página
    
    Returns:
        Dicionário com resultados paginados e metadados
    """
    total = len(query_result)
    total_paginas = (total + por_pagina - 1) // por_pagina
    
    # Validar página
    if pagina < 1:
        pagina = 1
    if pagina > total_paginas and total_paginas > 0:
        pagina = total_paginas
    
    # Calcular offset
    offset = (pagina - 1) * por_pagina
    
    # Fatiar resultados
    resultados = query_result[offset:offset + por_pagina]
    
    return {
        'resultados': resultados,
        'pagina_atual': pagina,
        'por_pagina': por_pagina,
        'total_itens': total,
        'total_paginas': total_paginas,
        'tem_anterior': pagina > 1,
        'tem_proximo': pagina < total_paginas
    }


def formatar_moeda(valor, simbolo='R$'):
    """
    Formata valor como moeda
    
    Args:
        valor: Valor numérico
        simbolo: Símbolo da moeda
    
    Returns:
        Valor formatado como string
    """
    if valor is None:
        return f"{simbolo} 0,00"
    
    try:
        valor = float(valor)
        return f"{simbolo} {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError):
        return f"{simbolo} 0,00"


def obter_iniciais(nome):
    """
    Obtém iniciais de um nome
    
    Args:
        nome: Nome completo
    
    Returns:
        Iniciais (máximo 2 letras)
    """
    if not nome:
        return '??'
    
    partes = nome.strip().split()
    
    if len(partes) == 1:
        return partes[0][:2].upper()
    else:
        return (partes[0][0] + partes[-1][0]).upper()


def validar_email(email):
    """
    Valida formato de email
    
    Args:
        email: Email a validar
    
    Returns:
        True se válido, False caso contrário
    """
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def gerar_slug(texto):
    """
    Gera slug a partir de texto
    
    Args:
        texto: Texto a converter
    
    Returns:
        Slug (texto-em-minusculas-com-hifens)
    """
    if not texto:
        return ''
    
    # Converter para minúsculas
    slug = texto.lower()
    
    # Remover acentos
    replacements = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a',
        'é': 'e', 'ê': 'e',
        'í': 'i',
        'ó': 'o', 'õ': 'o', 'ô': 'o',
        'ú': 'u', 'ü': 'u',
        'ç': 'c'
    }
    
    for old, new in replacements.items():
        slug = slug.replace(old, new)
    
    # Remover caracteres não alfanuméricos (exceto espaços e hífens)
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    
    # Substituir espaços por hífens
    slug = re.sub(r'\s+', '-', slug)
    
    # Remover hífens duplicados
    slug = re.sub(r'-+', '-', slug)
    
    # Remover hífens no início e fim
    slug = slug.strip('-')
    
    return slug

