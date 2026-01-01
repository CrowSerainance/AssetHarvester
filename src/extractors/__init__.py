# ==============================================================================
# EXTRACTORS MODULE INIT
# ==============================================================================
# Game-specific archive extractors for Asset Harvester.
#
# This package contains extractors for various game formats:
#   - BaseExtractor: Abstract base class defining the interface
#   - ExtractorRegistry: Registry for managing available extractors
#   - GRFExtractor: Ragnarok Online GRF/GPF archives
#   - VFSExtractor: ROSE Online VFS archives
#   - GenericExtractor: QuickBMS-based fallback for other formats
#
# Adding a new extractor:
#   1. Create a new file (e.g., myformat_extractor.py)
#   2. Subclass BaseExtractor and implement all abstract methods
#   3. Call ExtractorRegistry.register(MyExtractor) at module level
#   4. Import the module here
#
# Usage:
#   from src.extractors import ExtractorRegistry
#   extractor = ExtractorRegistry.get_extractor_for_file("data.grf")
#   if extractor:
#       extractor.open("data.grf")
#       extractor.extract_all("output/")
#       extractor.close()
# ==============================================================================

# Import base classes first (required by other extractors)
from .base_extractor import BaseExtractor, ExtractorRegistry, FileEntry

# Import specific extractors (each one registers itself)
from .grf_extractor import GRFExtractor
from .vfs_extractor import VFSExtractor
from .generic_extractor import GenericExtractor

# Public exports
__all__ = [
    # Base classes
    'BaseExtractor',
    'ExtractorRegistry', 
    'FileEntry',
    
    # Game-specific extractors
    'GRFExtractor',      # Ragnarok Online
    'VFSExtractor',      # ROSE Online
    'GenericExtractor',  # QuickBMS fallback
]


# ==============================================================================
# CONVENIENCE FUNCTION
# ==============================================================================
def get_extractor(archive_path: str) -> BaseExtractor:
    """
    Get an appropriate extractor for the given archive.
    
    This is a convenience function that wraps ExtractorRegistry.
    
    Args:
        archive_path: Path to the archive file
        
    Returns:
        An initialized extractor, or None if no suitable extractor found
        
    Example:
        >>> extractor = get_extractor("data.grf")
        >>> if extractor:
        ...     extractor.extract_all("output/")
        ...     extractor.close()
    """
    return ExtractorRegistry.get_extractor_for_file(archive_path)


def list_supported_formats() -> dict:
    """
    Get a dictionary of supported archive formats.
    
    Returns:
        Dict mapping extensions to extractor names
        
    Example:
        >>> formats = list_supported_formats()
        >>> print(formats)
        {'.grf': 'Ragnarok Online', '.vfs': 'ROSE Online', ...}
    """
    result = {}
    for ext in ExtractorRegistry.list_supported_extensions():
        # Find which extractor handles this extension
        for name, extractor_class in ExtractorRegistry._extractors.items():
            instance = extractor_class()
            if ext in instance.supported_extensions:
                result[ext] = instance.game_name
                break
    return result
