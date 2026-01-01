# ==============================================================================
# ASSET HARVESTER - SOURCE PACKAGE
# ==============================================================================
# Main package for Asset Harvester application.
#
# Subpackages:
#   - core: Database, hashing, comparison, cataloging, configuration
#   - extractors: Game-specific archive extractors
#   - gui: PyQt6 graphical user interface
#
# Entry points:
#   - main.py: GUI/CLI launcher
#   - src/cli.py: Command-line interface
#   - src/gui/main_window.py: GUI application
# ==============================================================================

__version__ = "1.0.0"
__author__ = "Crow"
__description__ = "Universal Private Server Asset Extraction & Cataloging System"

# Convenience imports
from .core import Database, FileHasher, AssetComparator, AssetCataloger
from .extractors import ExtractorRegistry, get_extractor

__all__ = [
    '__version__',
    '__author__',
    '__description__',
    
    # Core
    'Database',
    'FileHasher',
    'AssetComparator',
    'AssetCataloger',
    
    # Extractors
    'ExtractorRegistry',
    'get_extractor',
]
