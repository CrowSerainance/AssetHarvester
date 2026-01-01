# ==============================================================================
# CORE MODULE INIT
# ==============================================================================
# Core engine modules for Asset Harvester.
#
# This package contains the fundamental building blocks:
#   - Database: SQLite storage with SQLAlchemy ORM
#   - Hasher: File hashing utilities (MD5/SHA256)
#   - Comparator: Vanilla baseline comparison
#   - Cataloger: Asset organization and reporting
#   - Config: Application configuration management
#
# Usage:
#   from src.core import Database, FileHasher, AssetComparator, AssetCataloger
#   from src.core.config import get_config
# ==============================================================================

from .database import Database, Game, Server, Client, VanillaFile, Asset, AssetType
from .hasher import FileHasher
from .comparator import AssetComparator, ComparisonResult
from .cataloger import AssetCataloger, CategorizedAsset
from .config import Config, get_config
from .paths import Paths

__all__ = [
    # Database
    'Database',
    'Game',
    'Server', 
    'Client',
    'VanillaFile',
    'Asset',
    'AssetType',
    
    # Hashing
    'FileHasher',
    
    # Comparison
    'AssetComparator',
    'ComparisonResult',
    
    # Cataloging
    'AssetCataloger',
    'CategorizedAsset',
    
    # Configuration
    'Config',
    'get_config',
    
    # Paths
    'Paths',
]
