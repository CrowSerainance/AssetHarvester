# ==============================================================================
# GRF EXTRACTOR MODULE
# ==============================================================================
# Extractor for Ragnarok Online GRF (Gravity Resource File) archives.
# Supports GRF version 0x200 which is used by all modern clients.
#
# GRF Format Overview:
#   - Header: 46 bytes with signature "Master of Magic"
#   - File table: Compressed list of file entries at end of file
#   - File data: Individual files, each potentially compressed (zlib) and encrypted (DES)
#
# References:
#   - https://ragnarokresearchlab.github.io/file-formats/grf/
#   - https://github.com/vthibault/grf-loader
#   - https://github.com/bmeinka/pygrf
#
# Usage:
#   with GRFExtractor("data.grf") as grf:
#       files = grf.list_files()
#       grf.extract_all("output/")
# ==============================================================================

import os
import struct
import zlib
from typing import List, Optional
from .base_extractor import BaseExtractor, FileEntry, ExtractorRegistry


# ==============================================================================
# GRF CONSTANTS
# ==============================================================================

# GRF file signature (first 15 bytes of header)
GRF_SIGNATURE = b"Master of Magic"

# GRF header size
GRF_HEADER_SIZE = 46

# GRF version 0x200 (the version used by modern clients)
GRF_VERSION_200 = 0x200

# File entry flags
GRF_FILE_FLAG_FILE = 0x01       # Entry is a file (not directory)
GRF_FILE_FLAG_MIXCRYPT = 0x02  # Uses mixed encryption
GRF_FILE_FLAG_DES = 0x04       # Uses DES encryption


# ==============================================================================
# DES DECRYPTION (Simplified for GRF)
# ==============================================================================
# GRF uses a variant of DES encryption for some files.
# This is a simplified implementation that handles the common cases.

# DES tables and helper functions would go here
# For now, we'll handle unencrypted files and note that encrypted files
# need the full DES implementation

def des_decrypt_block(data: bytes, key: bytes = None) -> bytes:
    """
    Decrypt a DES-encrypted block from GRF.
    
    Note: Full DES implementation is complex. For now, this is a placeholder
    that returns data unchanged. Files that require DES decryption will be
    skipped with a warning.
    
    Args:
        data: Encrypted data
        key: DES key (GRF uses a fixed key)
        
    Returns:
        Decrypted data
    """
    # TODO: Implement full DES decryption
    # For now, return data unchanged
    return data


# ==============================================================================
# GRF EXTRACTOR CLASS
# ==============================================================================
class GRFExtractor(BaseExtractor):
    """
    Extractor for Ragnarok Online GRF/GPF archives.
    
    GRF (Gravity Resource File) is the archive format used by Ragnarok Online
    to store game assets. This extractor handles:
    - GRF version 0x200 (modern format)
    - Zlib-compressed files
    - Basic file extraction
    
    Note: DES-encrypted files are currently not fully supported and will be
    skipped with a warning.
    
    Attributes:
        archive_path (str): Path to the currently open GRF file
        version (int): GRF version number
        file_count (int): Number of files in the archive
    """
    
    def __init__(self, archive_path: str = None):
        """
        Initialize the GRF extractor.
        
        Args:
            archive_path: Optional path to GRF file to open immediately
        """
        self.version = 0
        self.file_count = 0
        self._file_handle = None
        self._file_table_offset = 0
        
        # Call parent init (will open archive if path provided)
        super().__init__(archive_path)
    
    # ==========================================================================
    # ABSTRACT PROPERTY IMPLEMENTATIONS
    # ==========================================================================
    
    @property
    def game_name(self) -> str:
        return "Ragnarok Online"
    
    @property
    def supported_extensions(self) -> List[str]:
        return ['.grf', '.gpf']
    
    @property
    def extractor_id(self) -> str:
        return "grf"
    
    # ==========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ==========================================================================
    
    def detect(self, path: str) -> bool:
        """
        Check if this is a GRF/GPF file.
        
        Checks both the file extension and the file signature.
        """
        # Check extension first (fast check)
        ext = os.path.splitext(path)[1].lower()
        if ext not in self.supported_extensions:
            return False
        
        # Check file exists and is readable
        if not os.path.isfile(path):
            return False
        
        # Check file signature
        try:
            with open(path, 'rb') as f:
                signature = f.read(len(GRF_SIGNATURE))
                return signature == GRF_SIGNATURE
        except:
            return False
    
    def open(self, archive_path: str) -> bool:
        """
        Open a GRF archive for reading.
        
        This parses the GRF header and file table, populating
        the internal file list.
        """
        if self._is_open:
            self.close()
        
        self.archive_path = archive_path
        
        try:
            # Open file handle
            self._file_handle = open(archive_path, 'rb')
            
            # Read and validate header
            if not self._read_header():
                self.close()
                return False
            
            # Read file table
            if not self._read_file_table():
                self.close()
                return False
            
            self._is_open = True
            print(f"[INFO] Opened GRF: {archive_path}")
            print(f"[INFO] Version: 0x{self.version:X}, Files: {self.file_count}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to open GRF {archive_path}: {e}")
            self.close()
            return False
    
    def close(self):
        """Close the GRF archive and release resources."""
        if self._file_handle:
            try:
                self._file_handle.close()
            except:
                pass
            self._file_handle = None
        
        self._is_open = False
        self._file_list = []
        self.version = 0
        self.file_count = 0
    
    def list_files(self) -> List[FileEntry]:
        """Get list of all files in the GRF."""
        if not self._is_open:
            return []
        return self._file_list.copy()
    
    def extract_file(self, file_path: str, output_path: str) -> bool:
        """
        Extract a single file from the GRF.
        
        Args:
            file_path: Path within the GRF (e.g., "data\\sprite\\monster.spr")
            output_path: Destination path on disk
        """
        if not self._is_open:
            return False
        
        # Get file data
        data = self.get_file_data(file_path)
        if data is None:
            return False
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Write file
        try:
            with open(output_path, 'wb') as f:
                f.write(data)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to write {output_path}: {e}")
            return False
    
    def get_file_data(self, file_path: str) -> Optional[bytes]:
        """
        Get the raw data of a file from the GRF.
        
        Args:
            file_path: Path within the GRF
            
        Returns:
            File contents as bytes, or None if not found
        """
        if not self._is_open:
            return None
        
        # Find the file entry (case-insensitive search)
        path_lower = file_path.lower().replace('/', '\\')
        entry = None
        
        for e in self._file_list:
            if e.path.lower().replace('/', '\\') == path_lower:
                entry = e
                break
        
        if entry is None:
            return None
        
        try:
            # Seek to file data
            self._file_handle.seek(entry.offset)
            
            # Read compressed data
            compressed_data = self._file_handle.read(entry.compressed_size)
            
            # Determine compression type from flags
            flags = 0
            # We need to get flags from entry - for now, infer from encrypted flag
            # TODO: Store flags in FileEntry for better compression detection
            
            # Decompress with improved error handling
            data = self._decompress_file_data(entry, compressed_data, file_path)
            
            if data is None:
                return None
            
            # Validate final data size
            if len(data) == 0:
                print(f"[WARN] Empty file data for {file_path}")
                return None
            
            return data
            
        except Exception as e:
            print(f"[ERROR] Failed to read {file_path}: {e}")
            return None
    
    # ==========================================================================
    # PRIVATE HELPER METHODS
    # ==========================================================================
    
    def _decompress_file_data(self, entry: FileEntry, raw_data: bytes, file_path: str) -> Optional[bytes]:
        """
        Decompress file data based on compression type.
        
        Handles multiple fallback strategies for problematic files.
        
        Args:
            entry: FileEntry with size information
            raw_data: Raw compressed/encrypted data
            file_path: File path for error messages
            
        Returns:
            Decompressed data, or None on error
        """
        try:
            # Check if encrypted (based on entry flag)
            if entry.is_encrypted:
                # Try DES decryption
                try:
                    from .grf_crypto import grf_des_decrypt
                    raw_data = grf_des_decrypt(raw_data, 0)  # TODO: Use actual table position
                except ImportError:
                    print(f"[WARN] DES decryption not available for {file_path}")
                    return None
                except Exception as e:
                    print(f"[WARN] DES decryption failed for {file_path}: {e}")
                    # Continue - might still be compressed
            
            # Determine compression type
            # If sizes differ, assume zlib compression (most common)
            if entry.compressed_size != entry.size and entry.compressed_size > 0:
                # Try standard zlib decompression
                try:
                    data = zlib.decompress(raw_data)
                    # Verify decompressed size matches expected
                    if len(data) == entry.size:
                        return data
                    elif abs(len(data) - entry.size) < 10:  # Allow small differences
                        print(f"[WARN] Size mismatch for {file_path}: expected {entry.size}, got {len(data)} (using anyway)")
                        return data
                    else:
                        # Size mismatch - might be wrong compression type
                        print(f"[WARN] Size mismatch for {file_path}: expected {entry.size}, got {len(data)}")
                except zlib.error as e:
                    error_str = str(e).lower()
                    
                    # Try without header (raw deflate)
                    if "incorrect header check" in error_str:
                        try:
                            data = zlib.decompress(raw_data, -zlib.MAX_WBITS)
                            if len(data) == entry.size or abs(len(data) - entry.size) < 10:
                                return data
                        except:
                            pass
                    
                    # Check if data is already uncompressed
                    if "unknown compression method" in error_str or "incorrect header check" in error_str:
                        if len(raw_data) == entry.size:
                            # Data is not compressed despite size difference
                            return raw_data
                    
                    # Final fallback: return raw data if size matches
                    if len(raw_data) == entry.size:
                        print(f"[WARN] Decompression failed for {file_path}, using raw data")
                        return raw_data
                    
                    print(f"[WARN] Decompression failed for {file_path}: {e}")
                    return None
            else:
                # No compression (sizes match) - return raw data
                return raw_data
                
        except Exception as e:
            print(f"[ERROR] Failed to decompress {file_path}: {e}")
            # Last resort: return raw data if size matches
            if len(raw_data) == entry.size:
                return raw_data
            return None
    
    def _read_header(self) -> bool:
        """
        Read and validate the GRF header.
        
        GRF Header Structure (46 bytes):
            - Signature: 15 bytes "Master of Magic"
            - Encryption key: 15 bytes (usually null)
            - File table offset: 4 bytes (uint32)
            - Seed: 4 bytes
            - File count: 4 bytes (uint32)
            - Version: 4 bytes (uint32)
        """
        try:
            # Read signature
            signature = self._file_handle.read(15)
            if signature != GRF_SIGNATURE:
                print(f"[ERROR] Invalid GRF signature")
                return False
            
            # Skip encryption key (15 bytes)
            self._file_handle.read(15)
            
            # Read file table offset
            self._file_table_offset = struct.unpack('<I', self._file_handle.read(4))[0]
            
            # Skip seed (4 bytes)
            self._file_handle.read(4)
            
            # Read file count (stored as count + 7 in the header)
            raw_count = struct.unpack('<I', self._file_handle.read(4))[0]
            self.file_count = raw_count - 7
            
            # Read version
            self.version = struct.unpack('<I', self._file_handle.read(4))[0]
            
            # Validate version
            if self.version != GRF_VERSION_200:
                print(f"[WARN] Unsupported GRF version: 0x{self.version:X}")
                # Continue anyway, might still work
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to read GRF header: {e}")
            return False
    
    def _read_file_table(self) -> bool:
        """
        Read the file table from the GRF.
        
        The file table is located at the end of the file (at _file_table_offset + header size).
        It contains compressed data with information about all files in the archive.
        """
        try:
            # Seek to file table
            self._file_handle.seek(GRF_HEADER_SIZE + self._file_table_offset)
            
            # Read compressed table size and uncompressed size
            compressed_size = struct.unpack('<I', self._file_handle.read(4))[0]
            uncompressed_size = struct.unpack('<I', self._file_handle.read(4))[0]
            
            # Read compressed file table
            compressed_table = self._file_handle.read(compressed_size)
            
            # Decompress
            try:
                table_data = zlib.decompress(compressed_table)
            except zlib.error as e:
                print(f"[ERROR] Failed to decompress file table: {e}")
                return False
            
            # Parse file entries
            self._file_list = []
            offset = 0
            
            while offset < len(table_data):
                # Read filename (null-terminated string)
                name_end = table_data.find(b'\x00', offset)
                if name_end == -1:
                    break
                
                filename = table_data[offset:name_end].decode('euc-kr', errors='replace')
                offset = name_end + 1
                
                # Check if enough data for entry info
                if offset + 17 > len(table_data):
                    break
                
                # Read entry info
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
                
                # Skip directories (flag 0)
                if flags == 0:
                    continue
                
                # Check if encrypted
                is_encrypted = bool(flags & (GRF_FILE_FLAG_MIXCRYPT | GRF_FILE_FLAG_DES))
                
                # Create file entry
                entry = FileEntry(
                    path=filename,
                    size=uncompressed_size,
                    compressed_size=compressed_size_aligned,
                    offset=GRF_HEADER_SIZE + file_offset,
                    is_encrypted=is_encrypted
                )
                self._file_list.append(entry)
            
            print(f"[INFO] Loaded {len(self._file_list)} file entries from GRF")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to read file table: {e}")
            return False


# ==============================================================================
# REGISTER EXTRACTOR
# ==============================================================================
# Register this extractor so it can be found by the registry
ExtractorRegistry.register(GRFExtractor)
