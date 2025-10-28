"""
Extensões do Sistema EAN
Exporta pool de conexões e outras extensões
"""
from src.extensions.database import (
    init_connection_pool,
    get_db_connection,
    release_db_connection,
    get_db,
    close_connection_pool,
    get_pool_status,
    execute_query,
    execute_query_dict
)

__all__ = [
    'init_connection_pool',
    'get_db_connection',
    'release_db_connection',
    'get_db',
    'close_connection_pool',
    'get_pool_status',
    'execute_query',
    'execute_query_dict'
]

