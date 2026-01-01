# ==============================================================================
# BASE EXTRACTOR MODULE
# ==============================================================================
# Abstract base class that all game-specific extractors must implement.
# Also includes an ExtractorRegistry for managing available extractors.
#
# To add support for a new game:
#   1. Create a new extractor class that inherits from BaseExtractor
#   2. Implement all abstract methods
#   3. Register the extractor with ExtractorRegistry
#
# Example:
#   class MyGameExtractor(BaseExtractor):
#       @property
#       def game_name(self): return "My Game"
#       ...
#
#   ExtractorRegistry.register(MyGameExtractor)
# ==============================================================================

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Callable, Iterator
from dataclasses import dataclass


# ==============================================================================
# FILE ENTRY DATA CLASS
# ==============================================================================
@dataclass
class FileEntry:
    """
    Represents a file entry within an archive.
    
    Attributes:
        path (str):           Relative path within the archive
        size (int):           Uncompressed file size
        compressed_size (int): Compressed size (may equal size if not compressed)
        offset (int):         Byte offset within the archive file
        is_encrypted (bool):  Whether the file is encrypted
    """
    path: str
    size: int
    compressed_size: int = 0
    offset: int = 0
    is_encrypted: bool = False
    
    def __post_init__(self):
        # Default compressed_size to size if not specified
        if self.compressed_size == 0:
            self.compressed_size = self.size


# ==============================================================================
# BASE EXTRACTOR ABSTRACT CLASS
# ==============================================================================
class BaseExtractor(ABC):
    """
    Abstract base class for game-specific archive extractors.
    
    All extractors must inherit from this class and implement the abstract
    methods. This ensures a consistent interface across all game formats.
    
    The typical workflow is:
        1. Create extractor instance
        2. Open an archive with open()
        3. List files with list_files()
        4. Extract files with extract() or extract_file()
        5. Close with close()
    
    Or use as a context manager:
        with GRFExtractor("data.grf") as ext:
            files = ext.list_files()
            ext.extract_all("output/")
    """
    
    def __init__(self, archive_path: str = None):
        """
        Initialize the extractor.
        
        Args:
            archive_path: Optional path to archive to open immediately
        """
        self.archive_path = archive_path
        self._is_open = False
        self._file_list: List[FileEntry] = []
        
        # Open archive if path provided
        if archive_path:
            self.open(archive_path)
    
    # ==========================================================================
    # ABSTRACT PROPERTIES - Must be implemented by subclasses
    # ==========================================================================
    
    @property
    @abstractmethod
    def game_name(self) -> str:
        """
        Human-readable name of the game this extractor handles.
        
        Returns:
            Game name string (e.g., "Ragnarok Online")
        """
        pass
    
    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """
        List of file extensions this extractor can handle.
        
        Returns:
            List of extensions including the dot (e.g., ['.grf', '.gpf'])
        """
        pass
    
    @property
    @abstractmethod
    def extractor_id(self) -> str:
        """
        Unique identifier for this extractor.
        
        Returns:
            Short ID string (e.g., "grf", "vfs", "pak")
        """
        pass
    
    # ==========================================================================
    # ABSTRACT METHODS - Must be implemented by subclasses
    # ==========================================================================
    
    @abstractmethod
    def detect(self, path: str) -> bool:
        """
        Check if this extractor can handle the given file/directory.
        
        This method should check file signatures, extensions, or other
        indicators to determine if this extractor is appropriate.
        
        Args:
            path: Path to a file or directory to check
            
        Returns:
            True if this extractor can handle the path, False otherwise
        """
        pass
    
    @abstractmethod
    def open(self, archive_path: str) -> bool:
        """
        Open an archive for reading.
        
        This should:
        - Validate the archive format
        - Parse the file table/header
        - Populate self._file_list with FileEntry objects
        
        Args:
            archive_path: Path to the archive file
            
        Returns:
            True if successfully opened, False otherwise
        """
        pass
    
    @abstractmethod
    def close(self):
        """
        Close the archive and release resources.
        """
        pass
    
    @abstractmethod
    def list_files(self) -> List[FileEntry]:
        """
        Get a list of all files in the archive.
        
        Returns:
            List of FileEntry objects for all files in the archive
        """
        pass
    
    @abstractmethod
    def extract_file(self, file_path: str, output_path: str) -> bool:
        """
        Extract a single file from the archive.
        
        Args:
            file_path: Path of the file within the archive
            output_path: Destination path to write the extracted file
            
        Returns:
            True if extraction successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_file_data(self, file_path: str) -> Optional[bytes]:
        """
        Get the raw data of a file without writing to disk.
        
        This is useful for computing hashes or analyzing files in memory.
        
        Args:
            file_path: Path of the file within the archive
            
        Returns:
            File contents as bytes, or None if file not found
        """
        pass
    
    # ==========================================================================
    # COMMON METHODS - Can be overridden but have default implementations
    # ==========================================================================
    
    def extract_all(self, output_dir: str,
                    progress_callback: Callable[[int, int, str], None] = None,
                    file_filter: Callable[[FileEntry], bool] = None) -> int:
        """
        Extract all files from the archive.
        
        Args:
            output_dir: Directory to extract files to
            progress_callback: Optional callback(current, total, filename)
            file_filter: Optional function to filter which files to extract
                        Returns True to include file, False to skip
            
        Returns:
            Number of files successfully extracted
        """
        if not self._is_open:
            raise RuntimeError("Archive is not open")
        
        # Get file list
        files = self.list_files()
        
        # Apply filter if provided
        if file_filter:
            files = [f for f in files if file_filter(f)]
        
        total = len(files)
        extracted = 0
        
        for idx, entry in enumerate(files):
            # Report progress
            if progress_callback:
                progress_callback(idx + 1, total, entry.path)
            
            # Construct output path
            output_path = os.path.join(output_dir, entry.path)
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Extract file
            if self.extract_file(entry.path, output_path):
                extracted += 1
        
        return extracted
    
    def iter_files(self) -> Iterator[FileEntry]:
        """
        Iterate over all files in the archive.
        
        This is memory-efficient for large archives.
        
        Yields:
            FileEntry objects for each file
        """
        for entry in self.list_files():
            yield entry
    
    def find_files(self, pattern: str) -> List[FileEntry]:
        """
        Find files matching a glob pattern.
        
        Args:
            pattern: Glob pattern (e.g., "*.spr", "sprite/*.act")
            
        Returns:
            List of matching FileEntry objects
        """
        import fnmatch
        
        pattern_lower = pattern.lower()
        results = []
        
        for entry in self.list_files():
            if fnmatch.fnmatch(entry.path.lower(), pattern_lower):
                results.append(entry)
        
        return results
    
    def get_file_count(self) -> int:
        """Get the total number of files in the archive."""
        return len(self._file_list)
    
    def get_total_size(self) -> int:
        """Get the total uncompressed size of all files."""
        return sum(entry.size for entry in self._file_list)
    
    # ==========================================================================
    # CONTEXT MANAGER SUPPORT
    # ==========================================================================
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure archive is closed."""
        self.close()
        return False


# ==============================================================================
# EXTRACTOR REGISTRY
# ==============================================================================
class ExtractorRegistry:
    """
    Registry for managing available extractors.
    
    This class maintains a list of all registered extractors and provides
    methods for finding the appropriate extractor for a given file.
    
    Usage:
        # Register an extractor
        ExtractorRegistry.register(GRFExtractor)
        
        # Find extractor for a file
        extractor = ExtractorRegistry.get_extractor_for_file("data.grf")
        
        # Get all registered extractors
        extractors = ExtractorRegistry.get_all()
    """
    
    # Class-level storage for registered extractors
    _extractors: Dict[str, type] = {}
    
    @classmethod
    def register(cls, extractor_class: type):
        """
        Register an extractor class.
        
        Args:
            extractor_class: Class that inherits from BaseExtractor
        """
        # Create a temporary instance to get the extractor ID
        # (We need to instantiate because extractor_id is a property)
        try:
            temp = extractor_class.__new__(extractor_class)
            # Call __init__ without archive_path to avoid opening a file
            temp.archive_path = None
            temp._is_open = False
            temp._file_list = []
            
            extractor_id = temp.extractor_id
            cls._extractors[extractor_id] = extractor_class
            print(f"[INFO] Registered extractor: {extractor_class.__name__} ({extractor_id})")
        except Exception as e:
            print(f"[ERROR] Failed to register extractor {extractor_class.__name__}: {e}")
    
    @classmethod
    def get_extractor_for_file(cls, file_path: str) -> Optional[BaseExtractor]:
        """
        Find and instantiate an appropriate extractor for a file.
        
        This checks each registered extractor's detect() method to find
        one that can handle the given file.
        
        Args:
            file_path: Path to the archive file
            
        Returns:
            An extractor instance, or None if no extractor found
        """
        for extractor_id, extractor_class in cls._extractors.items():
            try:
                # Create instance
                extractor = extractor_class()
                
                # Check if it can handle this file
                if extractor.detect(file_path):
                    return extractor_class(file_path)
                    
            except Exception as e:
                print(f"[WARN] Error checking extractor {extractor_id}: {e}")
                continue
        
        return None
    
    @classmethod
    def get_extractor_by_id(cls, extractor_id: str) -> Optional[type]:
        """
        Get an extractor class by its ID.
        
        Args:
            extractor_id: Extractor ID (e.g., "grf", "vfs")
            
        Returns:
            Extractor class, or None if not found
        """
        return cls._extractors.get(extractor_id)
    
    @classmethod
    def get_all(cls) -> Dict[str, type]:
        """
        Get all registered extractors.
        
        Returns:
            Dictionary mapping extractor IDs to classes
        """
        return cls._extractors.copy()
    
    @classmethod
    def list_supported_extensions(cls) -> List[str]:
        """
        Get all file extensions supported by registered extractors.
        
        Returns:
            List of extensions (e.g., ['.grf', '.gpf', '.vfs'])
        """
        extensions = []
        for extractor_class in cls._extractors.values():
            try:
                temp = extractor_class.__new__(extractor_class)
                temp.archive_path = None
                temp._is_open = False
                temp._file_list = []
                extensions.extend(temp.supported_extensions)
            except:
                pass
        return list(set(extensions))
