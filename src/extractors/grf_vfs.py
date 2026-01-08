# ==============================================================================
# GRF VIRTUAL FILE SYSTEM MODULE
# ==============================================================================
# Virtual File System for reading GRF archives without extraction.
#
# This module provides a virtual file system interface to GRF archives,
# allowing tools to read files directly from GRF files without extracting
# them to disk. Supports multiple GRF files with priority (later GRFs
# override earlier ones, similar to how RO loads data.grf + rdata.grf).
#
# Features:
#   - Load multiple GRF files with priority
#   - Unified file index across all loaded GRFs
#   - Memory cache for recently accessed files (LRU)
#   - Support for all GRF compression types
#   - Graceful error handling
#
# Usage:
#   vfs = GRFVirtualFileSystem(cache_size_mb=100)
#   vfs.load_grf("data.grf", priority=0)
#   vfs.load_grf("rdata.grf", priority=1)  # Higher priority
#   data = vfs.read_file("data/sprite/몬스터.spr")
# ==============================================================================

import os
import struct
import zlib
import lzma
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from collections import OrderedDict

# Import GRF constants and crypto
from .grf_extractor import (
    GRF_SIGNATURE, GRF_HEADER_SIZE, GRF_VERSION_200,
    GRF_FILE_FLAG_FILE, GRF_FILE_FLAG_MIXCRYPT, GRF_FILE_FLAG_DES
)

try:
    from .grf_crypto import grf_des_decrypt
    DES_AVAILABLE = True
except ImportError:
    DES_AVAILABLE = False
    print("[WARN] DES decryption not available")


# ==============================================================================
# GRF FILE ENTRY
# ==============================================================================

@dataclass
class GRFFileEntry:
    """
    Represents a file entry within a GRF archive.
    
    Attributes:
        path (str): Normalized path (forward slashes, lowercase)
        original_path (str): Original path from GRF
        compressed_size (int): Compressed size in bytes
        uncompressed_size (int): Uncompressed size in bytes
        offset (int): Byte offset in GRF file (after header)
        flags (int): File flags byte
        compression_type (int): Compression type (0=raw, 1=zlib, 2=DES+zlib, 3=DES, 4=LZMA)
        grf_path (str): Path to the GRF file containing this entry
        priority (int): Priority of the GRF (higher = overrides lower)
    """
    path: str
    original_path: str
    compressed_size: int
    uncompressed_size: int
    offset: int
    flags: int
    compression_type: int
    grf_path: str
    priority: int = 0
    
    def is_encrypted(self) -> bool:
        """Check if file is encrypted."""
        return bool(self.flags & (GRF_FILE_FLAG_MIXCRYPT | GRF_FILE_FLAG_DES))
    
    def is_compressed(self) -> bool:
        """Check if file is compressed."""
        # Compression type determines compression
        return self.compression_type in (1, 2, 4)


# ==============================================================================
# GRF ARCHIVE CLASS
# ==============================================================================

class GRFArchive:
    """
    Handles a single GRF file archive.
    
    Parses GRF header and file table, provides access to individual files.
    """
    
    def __init__(self, grf_path: str, priority: int = 0):
        """
        Initialize GRF archive.
        
        Args:
            grf_path: Path to GRF file
            priority: Priority level (higher = overrides lower priority GRFs)
        """
        self.grf_path = grf_path
        self.priority = priority
        self.version = 0
        self.file_count = 0
        self._file_handle = None
        self._file_table_offset = 0
        self._entries: Dict[str, GRFFileEntry] = {}  # Normalized path -> entry
        
    def open(self) -> bool:
        """
        Open and parse the GRF file.
        
        Returns:
            True if successful, False otherwise
        """
        if self._file_handle:
            self.close()
        
        try:
            # Open file
            self._file_handle = open(self.grf_path, 'rb')
            
            # Read header
            if not self._read_header():
                self.close()
                return False
            
            # Read file table
            if not self._read_file_table():
                self.close()
                return False
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to open GRF {self.grf_path}: {e}")
            self.close()
            return False
    
    def close(self):
        """Close the GRF file."""
        if self._file_handle:
            try:
                self._file_handle.close()
            except:
                pass
            self._file_handle = None
    
    def get_entry(self, normalized_path: str) -> Optional[GRFFileEntry]:
        """
        Get file entry by normalized path.
        
        Args:
            normalized_path: Normalized path (lowercase, forward slashes)
            
        Returns:
            GRFFileEntry if found, None otherwise
        """
        return self._entries.get(normalized_path)
    
    def list_entries(self) -> List[GRFFileEntry]:
        """Get all file entries."""
        return list(self._entries.values())
    
    def read_file_data(self, entry: GRFFileEntry) -> Optional[bytes]:
        """
        Read raw file data from GRF.
        
        Args:
            entry: GRFFileEntry for the file
            
        Returns:
            Raw compressed/encrypted data bytes, or None on error
        """
        if not self._file_handle:
            return None
        
        try:
            # Seek to file data (offset is relative to start of file after header)
            self._file_handle.seek(GRF_HEADER_SIZE + entry.offset)
            
            # Read compressed data
            compressed_data = self._file_handle.read(entry.compressed_size)
            
            if len(compressed_data) != entry.compressed_size:
                print(f"[WARN] Read {len(compressed_data)} bytes, expected {entry.compressed_size} for {entry.path}")
                return None
            
            return compressed_data
            
        except Exception as e:
            print(f"[ERROR] Failed to read {entry.path} from GRF: {e}")
            return None
    
    def _read_header(self) -> bool:
        """Read and validate GRF header."""
        try:
            # Read signature (15 bytes)
            signature = self._file_handle.read(15)
            if signature != GRF_SIGNATURE:
                print(f"[ERROR] Invalid GRF signature in {self.grf_path}")
                return False
            
            # Skip encryption key (15 bytes)
            self._file_handle.read(15)
            
            # Read file table offset (4 bytes, uint32)
            self._file_table_offset = struct.unpack('<I', self._file_handle.read(4))[0]
            
            # Skip seed (4 bytes)
            self._file_handle.read(4)
            
            # Read file count (4 bytes, uint32) - stored as count + 7
            raw_count = struct.unpack('<I', self._file_handle.read(4))[0]
            self.file_count = raw_count - 7
            
            # Read version (4 bytes, uint32)
            self.version = struct.unpack('<I', self._file_handle.read(4))[0]
            
            # Validate version
            if self.version != GRF_VERSION_200:
                print(f"[WARN] Unsupported GRF version: 0x{self.version:X} (expected 0x{GRF_VERSION_200:X})")
                # Continue anyway - might still work
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to read GRF header: {e}")
            return False
    
    def _read_file_table(self) -> bool:
        """Read and parse file table."""
        try:
            # Seek to file table (at end of file)
            self._file_handle.seek(GRF_HEADER_SIZE + self._file_table_offset)
            
            # Read compressed table size and uncompressed size
            compressed_size = struct.unpack('<I', self._file_handle.read(4))[0]
            uncompressed_size = struct.unpack('<I', self._file_handle.read(4))[0]
            
            # Read compressed file table
            compressed_table = self._file_handle.read(compressed_size)
            
            if len(compressed_table) != compressed_size:
                print(f"[ERROR] Failed to read complete file table")
                return False
            
            # Decompress file table
            try:
                table_data = zlib.decompress(compressed_table)
            except zlib.error as e:
                print(f"[ERROR] Failed to decompress file table: {e}")
                return False
            
            # Parse file entries with error handling
            self._entries = {}
            offset = 0
            entry_count = 0
            max_entries = 1000000  # Safety limit to prevent crashes
            
            while offset < len(table_data) and entry_count < max_entries:
                try:
                    # Read filename (null-terminated string)
                    name_end = table_data.find(b'\x00', offset)
                    if name_end == -1 or name_end >= len(table_data):
                        break
                    
                    filename_bytes = table_data[offset:name_end]
                    offset = name_end + 1
                    
                    # Validate filename length (sanity check)
                    if len(filename_bytes) > 260:  # MAX_PATH in Windows
                        # Skip corrupted entry
                        continue
                    
                    # Decode filename (EUC-KR encoding for Korean RO)
                    try:
                        original_path = filename_bytes.decode('euc-kr', errors='replace')
                    except:
                        try:
                            original_path = filename_bytes.decode('latin-1', errors='replace')
                        except:
                            original_path = filename_bytes.decode('utf-8', errors='replace')
                    
                    # Check if enough data for entry info (17 bytes)
                    if offset + 17 > len(table_data):
                        break
                    
                    # Read entry info
                    try:
                        compressed_size = struct.unpack('<I', table_data[offset:offset+4])[0]
                        offset += 4
                        
                        compressed_size_aligned = struct.unpack('<I', table_data[offset:offset+4])[0]
                        offset += 4
                        
                        uncompressed_size = struct.unpack('<I', table_data[offset:offset+4])[0]
                        offset += 4
                        
                        flags = table_data[offset]
                        offset += 1
                        
                        file_offset = struct.unpack('<I', table_data[offset:offset+4])[0]
                        offset += 4
                        
                        # Validate sizes (sanity checks)
                        if compressed_size_aligned > 100 * 1024 * 1024:  # 100 MB max
                            continue  # Skip suspiciously large file
                        if uncompressed_size > 500 * 1024 * 1024:  # 500 MB max
                            continue  # Skip suspiciously large file
                        if file_offset < 0 or file_offset > 2 * 1024 * 1024 * 1024:  # 2 GB max
                            continue  # Skip invalid offset
                        
                    except struct.error:
                        # Corrupted entry data
                        break
                    
                    # Skip directories (flag 0)
                    if flags == 0:
                        continue
                    
                    # Determine compression type from flags
                    compression_type = 0  # Raw/uncompressed
                    if flags & GRF_FILE_FLAG_MIXCRYPT:
                        # Mixed encryption - first 20 bytes encrypted
                        compression_type = 3  # DES only (for header)
                    elif flags & GRF_FILE_FLAG_DES:
                        if compressed_size_aligned != uncompressed_size:
                            compression_type = 2  # DES + zlib
                        else:
                            compression_type = 3  # DES only
                    elif compressed_size_aligned != uncompressed_size:
                        # Try to detect compression
                        compression_type = 1  # zlib (default)
                        # Could check for LZMA signature here
                    
                    # Normalize path for lookup (lowercase, forward slashes)
                    normalized_path = original_path.lower().replace('\\', '/')
                    
                    # Validate normalized path
                    if not normalized_path or len(normalized_path) > 260:
                        continue  # Skip invalid paths
                    
                    # Create entry
                    entry = GRFFileEntry(
                        path=normalized_path,
                        original_path=original_path,
                        compressed_size=compressed_size_aligned,
                        uncompressed_size=uncompressed_size,
                        offset=file_offset,
                        flags=flags,
                        compression_type=compression_type,
                        grf_path=self.grf_path,
                        priority=self.priority
                    )
                    
                    # Store entry (higher priority overrides)
                    if normalized_path not in self._entries:
                        self._entries[normalized_path] = entry
                        entry_count += 1
                    elif self.priority > self._entries[normalized_path].priority:
                        self._entries[normalized_path] = entry
                    
                except Exception as e:
                    # Skip corrupted entry and continue
                    print(f"[WARN] Skipping corrupted entry at offset {offset}: {e}")
                    # Try to recover by finding next null terminator
                    next_null = table_data.find(b'\x00', offset)
                    if next_null == -1:
                        break
                    offset = next_null + 1
                    continue
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to read file table: {e}")
            import traceback
            traceback.print_exc()
            return False


# ==============================================================================
# GRF VIRTUAL FILE SYSTEM
# ==============================================================================

class GRFVirtualFileSystem:
    """
    Virtual File System for GRF archives.
    
    Manages multiple GRF files with priority, provides unified file access
    with caching and decompression.
    """
    
    def __init__(self, cache_size_mb: int = 100):
        """
        Initialize GRF Virtual File System.
        
        Args:
            cache_size_mb: Maximum cache size in megabytes
        """
        self._archives: List[GRFArchive] = []
        self._file_index: Dict[str, GRFFileEntry] = {}  # Normalized path -> entry
        self._cache: OrderedDict[str, bytes] = OrderedDict()  # LRU cache
        self._cache_size_limit = cache_size_mb * 1024 * 1024  # Convert to bytes
        self._cache_size_current = 0
        
        # Statistics
        self._stats = {
            'files_read': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'decompression_failures': 0,
            'decompression_fallbacks': 0
        }
    
    def load_grf(self, grf_path: str, priority: int = 0, rebuild_index: bool = True) -> bool:
        """
        Load a GRF file into the virtual file system.
        
        Args:
            grf_path: Path to GRF file
            priority: Priority level (higher priority overrides lower for duplicate files)
            rebuild_index: If True, rebuild unified index immediately (False for async indexing)
            
        Returns:
            True if successful, False otherwise
        """
        if not os.path.isfile(grf_path):
            print(f"[ERROR] GRF file not found: {grf_path}")
            return False
        
        # Create and open archive
        archive = GRFArchive(grf_path, priority)
        if not archive.open():
            return False
        
        # Add to archives list (sorted by priority)
        self._archives.append(archive)
        self._archives.sort(key=lambda a: a.priority)
        
        # Rebuild unified index if requested (higher priority overrides)
        if rebuild_index:
            self._rebuild_index()
        
        print(f"[INFO] Loaded GRF: {os.path.basename(grf_path)} (priority {priority}, {len(archive._entries)} files)")
        return True
    
    def set_file_index(self, new_index: dict):
        """
        Set the file index (thread-safe - call from UI thread after background indexing).
        
        Args:
            new_index: New file index dictionary
        """
        self._file_index = new_index
    
    def merge_file_index(self, new_index: dict):
        """
        Merge a new index into the existing one (for adding GRFs).
        
        Args:
            new_index: New file index dictionary to merge
        """
        for path, entry in new_index.items():
            # Higher priority overrides lower
            if path not in self._file_index:
                self._file_index[path] = entry
            elif entry.priority > self._file_index[path].priority:
                self._file_index[path] = entry
    
    def _rebuild_index(self):
        """Rebuild unified file index from all archives."""
        try:
            self._file_index = {}
            
            # Process archives in priority order (lower first, then higher overrides)
            archives_sorted = sorted(self._archives, key=lambda a: a.priority)
            
            for archive in archives_sorted:
                try:
                    entries = archive.list_entries()
                    for entry in entries:
                        try:
                            normalized_path = entry.path
                            
                            # Higher priority overrides lower
                            if normalized_path not in self._file_index:
                                self._file_index[normalized_path] = entry
                            elif entry.priority > self._file_index[normalized_path].priority:
                                self._file_index[normalized_path] = entry
                        except Exception as e:
                            # Skip invalid entry
                            print(f"[WARN] Invalid entry skipped: {e}")
                            continue
                except Exception as e:
                    print(f"[ERROR] Failed to process archive {archive.grf_path}: {e}")
                    continue
                    
        except Exception as e:
            print(f"[ERROR] Failed to rebuild index: {e}")
            import traceback
            traceback.print_exc()
            # Keep existing index if rebuild fails
    
    def list_files(self, pattern: str = "*") -> List[str]:
        """
        List all files, optionally filtered by glob pattern.
        
        Args:
            pattern: Glob pattern (e.g., "*.spr", "data/sprite/**")
            
        Returns:
            List of normalized file paths
        """
        import fnmatch
        
        if pattern == "*":
            return list(self._file_index.keys())
        
        pattern_lower = pattern.lower().replace('\\', '/')
        return [path for path in self._file_index.keys() if fnmatch.fnmatch(path, pattern_lower)]
    
    def list_directory(self, path: str) -> List[str]:
        """
        List files in a virtual directory.
        
        Args:
            path: Directory path (normalized or original format)
            
        Returns:
            List of file/directory names in that directory
        """
        # Normalize path
        normalized_dir = path.lower().replace('\\', '/')
        if not normalized_dir.endswith('/'):
            normalized_dir += '/'
        
        # Find all files in this directory
        items = set()
        for file_path in self._file_index.keys():
            if file_path.startswith(normalized_dir):
                # Get relative path
                rel_path = file_path[len(normalized_dir):]
                # Get first component (file or subdirectory)
                first_part = rel_path.split('/')[0]
                if first_part:
                    items.add(first_part)
        
        return sorted(items)
    
    def file_exists(self, path: str) -> bool:
        """
        Check if file exists in any loaded GRF.
        
        Args:
            path: File path (normalized or original format)
            
        Returns:
            True if file exists, False otherwise
        """
        normalized_path = path.lower().replace('\\', '/')
        return normalized_path in self._file_index
    
    def read_file(self, path: str) -> Optional[bytes]:
        """
        Read and decompress a file, using cache if available.
        
        Args:
            path: File path (normalized or original format)
            
        Returns:
            Decompressed file data as bytes, or None if not found/error
        """
        # Normalize path
        normalized_path = path.lower().replace('\\', '/')
        
        # Check cache first
        if normalized_path in self._cache:
            # Move to end (most recently used)
            data = self._cache.pop(normalized_path)
            self._cache[normalized_path] = data
            self._stats['cache_hits'] += 1
            return data
        
        self._stats['cache_misses'] += 1
        
        # Get file entry
        entry = self._file_index.get(normalized_path)
        if not entry:
            return None
        
        # Find archive containing this file
        archive = None
        for arch in self._archives:
            if arch.grf_path == entry.grf_path:
                archive = arch
                break
        
        if not archive:
            return None
        
        # Read raw data from GRF
        raw_data = archive.read_file_data(entry)
        if not raw_data:
            return None
        
        # Decompress
        data = self._decompress_file(entry, raw_data)
        if not data:
            return None
        
        # Validate decompressed data size
        if entry.uncompressed_size > 0:
            # Allow small size differences (some GRF files have incorrect size in header)
            size_diff = abs(len(data) - entry.uncompressed_size)
            size_tolerance = max(entry.uncompressed_size * 0.01, 1024)  # 1% or 1KB tolerance
            
            if size_diff > size_tolerance:
                # Significant size mismatch - might be corrupted
                # But still return data if it's close enough (within 10%)
                if size_diff > entry.uncompressed_size * 0.1:
                    # Too large a difference - likely corrupted
                    return None
        
        # Add to cache
        self._cache_file(normalized_path, data)
        
        self._stats['files_read'] += 1
        return data
    
    def get_file_info(self, path: str) -> Optional[GRFFileEntry]:
        """
        Get metadata about a file without reading it.
        
        Args:
            path: File path (normalized or original format)
            
        Returns:
            GRFFileEntry if found, None otherwise
        """
        normalized_path = path.lower().replace('\\', '/')
        return self._file_index.get(normalized_path)
    
    def search_files(self, query: str) -> List[str]:
        """
        Search files by partial name match.
        
        Args:
            query: Search query (case-insensitive substring match)
            
        Returns:
            List of matching file paths
        """
        query_lower = query.lower()
        results = []
        
        for path in self._file_index.keys():
            if query_lower in path:
                results.append(path)
        
        return sorted(results)
    
    def get_statistics(self) -> dict:
        """
        Return cache and operation statistics.
        
        Returns:
            Dictionary with statistics
        """
        stats = self._stats.copy()
        stats['cache_size_mb'] = self._cache_size_current / (1024 * 1024)
        stats['cache_entries'] = len(self._cache)
        stats['total_files'] = len(self._file_index)
        stats['loaded_grfs'] = len(self._archives)
        return stats
    
    def clear_cache(self):
        """Clear the memory cache."""
        self._cache.clear()
        self._cache_size_current = 0
    
    def _cache_file(self, path: str, data: bytes):
        """Add file to cache, evicting old entries if needed."""
        data_size = len(data)
        
        # Check if file is too large for cache
        if data_size > self._cache_size_limit:
            return  # Don't cache huge files
        
        # Evict old entries until we have space
        while self._cache_size_current + data_size > self._cache_size_limit and self._cache:
            # Remove oldest entry (first in OrderedDict)
            oldest_path, oldest_data = self._cache.popitem(last=False)
            self._cache_size_current -= len(oldest_data)
        
        # Add new entry
        self._cache[path] = data
        self._cache_size_current += data_size
    
    def _decompress_zlib_multiple_strategies(self, raw_data: bytes, entry: GRFFileEntry) -> Optional[bytes]:
        """
        Decompress zlib data with multiple fallback strategies.
        
        First tries primary strategies, then falls back to GRFEditor algorithms.
        """
        # Try primary strategies first
        result = self._decompress_zlib_primary(raw_data, entry)
        if result:
            return result
        
        # Try GRFEditor fallback strategies
        try:
            from src.extractors.grf_decompression_fallback import decompress_with_grfeditor_fallback
            result = decompress_with_grfeditor_fallback(
                raw_data,
                entry.uncompressed_size,
                entry.compression_type
            )
            if result:
                self._stats['decompression_fallbacks'] += 1
                return result
        except ImportError:
            # Fallback module not available - continue
            pass
        except Exception:
            # Fallback failed - continue
            pass
        
        # All strategies failed
        self._stats['decompression_failures'] += 1
        return None
    
    def _decompress_zlib_primary(self, raw_data: bytes, entry: GRFFileEntry) -> Optional[bytes]:
        """
        Decompress zlib data with multiple fallback strategies.
        
        Handles:
        - Standard zlib compression
        - Raw deflate (no header)
        - Uncompressed data
        - Private server variations
        
        Args:
            raw_data: Compressed data
            entry: File entry with size info
            
        Returns:
            Decompressed data or None
        """
        # Strategy 1: Standard zlib
        try:
            decompressed = zlib.decompress(raw_data)
            # Validate size
            if entry.uncompressed_size > 0:
                size_diff = abs(len(decompressed) - entry.uncompressed_size)
                size_tolerance = max(entry.uncompressed_size * 0.1, 1024)
                if size_diff <= size_tolerance:
                    return decompressed
                # Even if size differs, accept if close enough (20% tolerance)
                elif size_diff <= entry.uncompressed_size * 0.2:
                    return decompressed
            else:
                # Size unknown - accept decompressed data
                return decompressed
        except zlib.error:
            pass
        
        # Strategy 2: Raw deflate (no zlib header)
        try:
            decompressed = zlib.decompress(raw_data, -zlib.MAX_WBITS)
            if entry.uncompressed_size == 0:
                return decompressed
            size_diff = abs(len(decompressed) - entry.uncompressed_size)
            if size_diff <= entry.uncompressed_size * 0.2:
                return decompressed
        except zlib.error:
            pass
        
        # Strategy 3: Try with different window sizes
        for wbits in [15, -15, 31, 47]:
            try:
                decompressed = zlib.decompress(raw_data, wbits)
                if entry.uncompressed_size == 0:
                    return decompressed
                size_diff = abs(len(decompressed) - entry.uncompressed_size)
                if size_diff <= entry.uncompressed_size * 0.2:
                    return decompressed
            except zlib.error:
                continue
        
        # Strategy 4: Skip first 2 bytes (some servers add custom header)
        if len(raw_data) > 2:
            try:
                decompressed = zlib.decompress(raw_data[2:])
                if entry.uncompressed_size == 0 or abs(len(decompressed) - entry.uncompressed_size) <= entry.uncompressed_size * 0.2:
                    return decompressed
            except zlib.error:
                pass
            try:
                decompressed = zlib.decompress(raw_data[2:], -zlib.MAX_WBITS)
                if entry.uncompressed_size == 0 or abs(len(decompressed) - entry.uncompressed_size) <= entry.uncompressed_size * 0.2:
                    return decompressed
            except zlib.error:
                pass
        
        # Strategy 5: Data might already be uncompressed despite flags
        # Return as-is if it's close to expected size
        if entry.uncompressed_size > 0:
            size_ratio = len(raw_data) / entry.uncompressed_size
            if 0.8 <= size_ratio <= 1.2:
                # Sizes are close - might be uncompressed
                self._stats['decompression_fallbacks'] += 1
                return raw_data
        
        # All strategies failed
        self._stats['decompression_failures'] += 1
        return None
    
    def _decompress_file(self, entry: GRFFileEntry, raw_data: bytes) -> Optional[bytes]:
        """
        Decompress file data based on compression type.
        
        Handles multiple fallback strategies for problematic files.
        
        Args:
            entry: GRFFileEntry with compression info
            raw_data: Raw compressed/encrypted data
            
        Returns:
            Decompressed data, or None on error
        """
        try:
            if entry.compression_type == 0:
                # Raw data, no compression
                return raw_data
            
            elif entry.compression_type == 1:
                # Standard zlib - try multiple strategies
                return self._decompress_zlib_multiple_strategies(raw_data, entry)
            
            elif entry.compression_type == 2:
                # DES encrypted + zlib
                if not DES_AVAILABLE:
                    print(f"[WARN] DES decryption not available for {entry.path}")
                    return None
                
                try:
                    decrypted = grf_des_decrypt(raw_data, 0)  # TODO: Use actual table position
                    return zlib.decompress(decrypted)
                except Exception as e:
                    print(f"[WARN] DES+zlib decompression failed for {entry.path}: {e}")
                    self._stats['decompression_failures'] += 1
                    return None
            
            elif entry.compression_type == 3:
                # DES encrypted only
                if not DES_AVAILABLE:
                    print(f"[WARN] DES decryption not available for {entry.path}")
                    return None
                
                try:
                    return grf_des_decrypt(raw_data, 0)  # TODO: Use actual table position
                except Exception as e:
                    print(f"[WARN] DES decryption failed for {entry.path}: {e}")
                    self._stats['decompression_failures'] += 1
                    return None
            
            elif entry.compression_type == 4:
                # LZMA
                try:
                    return lzma.decompress(raw_data)
                except Exception as e:
                    print(f"[WARN] LZMA decompression failed for {entry.path}: {e}")
                    self._stats['decompression_failures'] += 1
                    # Fallback: check if it's raw
                    if len(raw_data) == entry.uncompressed_size:
                        self._stats['decompression_fallbacks'] += 1
                        return raw_data
                    return None
            
            else:
                # Unknown compression type - try zlib first, then raw
                try:
                    return zlib.decompress(raw_data)
                except:
                    if len(raw_data) == entry.uncompressed_size:
                        self._stats['decompression_fallbacks'] += 1
                        return raw_data
                    self._stats['decompression_failures'] += 1
                    return None
            
        except Exception as e:
            print(f"[ERROR] Failed to decompress {entry.path}: {e}")
            self._stats['decompression_failures'] += 1
            # Last resort: return raw data if size matches
            if len(raw_data) == entry.uncompressed_size:
                self._stats['decompression_fallbacks'] += 1
                return raw_data
            return None

