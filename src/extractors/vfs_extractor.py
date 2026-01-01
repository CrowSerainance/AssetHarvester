# ==============================================================================
# ROSE ONLINE VFS EXTRACTOR
# ==============================================================================
# Native Python extractor for ROSE Online VFS (Virtual File System) archives.
#
# VFS Format Overview:
#   ROSE Online uses a two-file system:
#   - .VFS file: Contains the actual compressed file data
#   - .IDX file: Contains the file index/table of contents
#
# IDX File Structure:
#   - Header (16 bytes):
#       - Magic number (4 bytes): Usually version indicator
#       - File count (4 bytes): Number of files in archive
#       - Reserved (8 bytes): Padding/future use
#   - File entries (variable size each):
#       - Filename length (2 bytes)
#       - Filename (variable, null-terminated)
#       - Offset in VFS (4 bytes)
#       - Compressed size (4 bytes)
#       - Uncompressed size (4 bytes)
#       - Block size (4 bytes): For chunked compression
#       - Is deleted flag (1 byte)
#       - Is compressed flag (1 byte)
#       - Is encrypted flag (1 byte)
#       - Reserved (1 byte)
#
# VFS File Structure:
#   - Raw file data blocks at offsets specified in IDX
#   - Compression: zlib (standard)
#   - Some servers use XOR encryption
#
# Usage:
#   extractor = VFSExtractor()
#   extractor.open("data.idx")  # Will auto-find data.vfs
#   files = extractor.list_files()
#   extractor.extract_all("output/")
#
# Note: This implementation is based on community research and may need
# adjustments for specific private server modifications.
# ==============================================================================

import os
import struct
import zlib
from typing import List, Optional, BinaryIO, Dict

from .base_extractor import BaseExtractor, ExtractorRegistry, FileEntry


# ==============================================================================
# VFS FILE ENTRY CLASS
# ==============================================================================
class VFSFileEntry:
    """
    Represents a single file entry in a VFS archive.
    
    This class holds all metadata for a file stored in the VFS,
    including its location, size, and compression status.
    
    Attributes:
        path: Relative file path within the archive
        offset: Byte offset in the VFS file where data starts
        compressed_size: Size of compressed data in bytes
        uncompressed_size: Original file size in bytes
        block_size: Size of compression blocks (0 if single block)
        is_deleted: True if file was marked as deleted
        is_compressed: True if file data is zlib compressed
        is_encrypted: True if file data is encrypted (XOR)
    """
    
    def __init__(self):
        """Initialize an empty file entry."""
        self.path: str = ""
        self.offset: int = 0
        self.compressed_size: int = 0
        self.uncompressed_size: int = 0
        self.block_size: int = 0
        self.is_deleted: bool = False
        self.is_compressed: bool = False
        self.is_encrypted: bool = False
    
    def __repr__(self) -> str:
        """Return string representation for debugging."""
        flags = []
        if self.is_compressed:
            flags.append("compressed")
        if self.is_encrypted:
            flags.append("encrypted")
        if self.is_deleted:
            flags.append("deleted")
        
        flag_str = ", ".join(flags) if flags else "raw"
        return f"VFSFileEntry({self.path}, {self.uncompressed_size} bytes, {flag_str})"


# ==============================================================================
# VFS EXTRACTOR CLASS
# ==============================================================================
class VFSExtractor(BaseExtractor):
    """
    Extractor for ROSE Online VFS (Virtual File System) archives.
    
    This extractor handles the dual-file VFS format used by ROSE Online,
    consisting of an .IDX index file and a .VFS data file.
    
    Features:
        - Reads IDX file table to locate files in VFS
        - Supports zlib decompression
        - Handles block-based compression for large files
        - Basic XOR decryption support (common key patterns)
    
    Attributes:
        idx_path: Path to the index file (.idx)
        vfs_path: Path to the data file (.vfs)
        file_entries: Dictionary mapping paths to VFSFileEntry objects
        vfs_handle: Open file handle to the VFS data file
    
    Example:
        >>> extractor = VFSExtractor()
        >>> extractor.open("E:/ROSE/data.idx")
        True
        >>> print(f"Found {extractor.get_file_count()} files")
        >>> extractor.extract_all("E:/extracted/")
        >>> extractor.close()
    """
    
    # -------------------------------------------------------------------------
    # VFS FORMAT CONSTANTS
    # -------------------------------------------------------------------------
    
    # Common encryption key used by some ROSE servers
    # This is a placeholder - actual keys vary by server
    DEFAULT_XOR_KEY = bytes([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0xDE, 0xF0])
    
    # Maximum reasonable file size (1GB) to prevent memory issues
    MAX_FILE_SIZE = 1024 * 1024 * 1024
    
    # -------------------------------------------------------------------------
    # INITIALIZATION
    # -------------------------------------------------------------------------
    
    def __init__(self):
        """
        Initialize the VFS extractor.
        
        Sets up empty state - call open() to load an archive.
        """
        super().__init__()
        
        # File paths
        self.idx_path: str = ""
        self.vfs_path: str = ""
        
        # File table
        self.file_entries: Dict[str, VFSFileEntry] = {}
        
        # Open file handles
        self.vfs_handle: Optional[BinaryIO] = None
        
        # Custom XOR key (can be set for specific servers)
        self.xor_key: bytes = self.DEFAULT_XOR_KEY
    
    # -------------------------------------------------------------------------
    # ABSTRACT PROPERTY IMPLEMENTATIONS
    # -------------------------------------------------------------------------
    
    @property
    def game_name(self) -> str:
        """Return the name of the game this extractor handles."""
        return "ROSE Online"
    
    @property
    def supported_extensions(self) -> List[str]:
        """Return list of file extensions this extractor can handle."""
        return ['.vfs', '.idx']
    
    @property
    def extractor_id(self) -> str:
        """Return unique identifier for this extractor."""
        return "rose_vfs"
    
    # -------------------------------------------------------------------------
    # ARCHIVE DETECTION
    # -------------------------------------------------------------------------
    
    def detect(self, path: str) -> bool:
        """
        Check if this extractor can handle the given file.
        
        Validates that:
        1. The file extension is .vfs or .idx
        2. The companion file exists (idx for vfs, vfs for idx)
        3. The IDX file has valid structure
        
        Args:
            path: Path to the archive file
            
        Returns:
            True if this extractor can handle the file
        """
        # Normalize path
        path = os.path.abspath(path)
        ext = os.path.splitext(path)[1].lower()
        
        # Check extension
        if ext not in self.supported_extensions:
            return False
        
        # Determine both file paths
        base_path = os.path.splitext(path)[0]
        idx_path = base_path + '.idx'
        vfs_path = base_path + '.vfs'
        
        # Check both files exist
        if not os.path.isfile(idx_path):
            return False
        if not os.path.isfile(vfs_path):
            return False
        
        # Try to validate IDX header
        try:
            with open(idx_path, 'rb') as f:
                # Read first 16 bytes
                header = f.read(16)
                if len(header) < 16:
                    return False
                
                # Basic sanity check: file count should be reasonable
                version = struct.unpack('<I', header[0:4])[0]
                file_count = struct.unpack('<I', header[4:8])[0]
                
                # Reasonable limits: version < 1000, files < 1 million
                if version > 1000 or file_count > 1000000:
                    return False
                
                return True
                
        except Exception:
            return False
    
    # -------------------------------------------------------------------------
    # ARCHIVE OPERATIONS
    # -------------------------------------------------------------------------
    
    def open(self, archive_path: str) -> bool:
        """
        Open a VFS archive for reading.
        
        Accepts either the .idx or .vfs file path and automatically
        locates the companion file.
        
        Args:
            archive_path: Path to either the .idx or .vfs file
            
        Returns:
            True if archive was opened successfully
        """
        # Close any existing archive
        self.close()
        
        # Normalize path and determine both file paths
        archive_path = os.path.abspath(archive_path)
        base_path = os.path.splitext(archive_path)[0]
        
        self.idx_path = base_path + '.idx'
        self.vfs_path = base_path + '.vfs'
        
        # Verify both files exist
        if not os.path.isfile(self.idx_path):
            print(f"[ERROR] Index file not found: {self.idx_path}")
            return False
        
        if not os.path.isfile(self.vfs_path):
            print(f"[ERROR] Data file not found: {self.vfs_path}")
            return False
        
        # Parse the index file
        try:
            self._parse_idx_file()
        except Exception as e:
            print(f"[ERROR] Failed to parse index file: {e}")
            return False
        
        # Open the VFS data file
        try:
            self.vfs_handle = open(self.vfs_path, 'rb')
        except Exception as e:
            print(f"[ERROR] Failed to open data file: {e}")
            return False
        
        return True
    
    def close(self):
        """
        Close the archive and release resources.
        
        Always safe to call, even if no archive is open.
        """
        if self.vfs_handle:
            self.vfs_handle.close()
            self.vfs_handle = None
        
        self.idx_path = ""
        self.vfs_path = ""
        self.file_entries.clear()
    
    # -------------------------------------------------------------------------
    # FILE LISTING
    # -------------------------------------------------------------------------
    
    def list_files(self) -> List[FileEntry]:
        """
        List all files in the archive.
        
        Returns:
            List of FileEntry objects for each file
        """
        result = []
        
        for path, entry in self.file_entries.items():
            # Skip deleted files
            if entry.is_deleted:
                continue
            
            file_entry = FileEntry(
                path=path,
                size=entry.uncompressed_size,
                compressed_size=entry.compressed_size,
                offset=entry.offset,
                is_encrypted=entry.is_encrypted
            )
            result.append(file_entry)
        
        return result
    
    # -------------------------------------------------------------------------
    # FILE EXTRACTION
    # -------------------------------------------------------------------------
    
    def extract_file(self, file_path: str, output_path: str) -> bool:
        """
        Extract a single file from the archive.
        
        Args:
            file_path: Path of the file within the archive
            output_path: Where to save the extracted file
            
        Returns:
            True if extraction succeeded
        """
        # Get file data
        data = self.get_file_data(file_path)
        if data is None:
            return False
        
        # Create output directory
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
        Get the raw data for a file in the archive.
        
        Handles decompression and decryption as needed.
        
        Args:
            file_path: Path of the file within the archive
            
        Returns:
            File contents as bytes, or None on error
        """
        # Normalize path
        file_path = file_path.replace('\\', '/')
        
        # Find the entry
        entry = self.file_entries.get(file_path)
        if not entry:
            # Try case-insensitive search
            lower_path = file_path.lower()
            for path, e in self.file_entries.items():
                if path.lower() == lower_path:
                    entry = e
                    break
        
        if not entry:
            print(f"[WARNING] File not found in archive: {file_path}")
            return None
        
        if entry.is_deleted:
            print(f"[WARNING] File is marked as deleted: {file_path}")
            return None
        
        # Validate file handle
        if not self.vfs_handle:
            print("[ERROR] Archive not open")
            return None
        
        try:
            # Seek to file data
            self.vfs_handle.seek(entry.offset)
            
            # Read compressed/raw data
            raw_data = self.vfs_handle.read(entry.compressed_size)
            
            # Decrypt if needed
            if entry.is_encrypted:
                raw_data = self._decrypt_data(raw_data)
            
            # Decompress if needed
            if entry.is_compressed:
                try:
                    # Handle block-based compression
                    if entry.block_size > 0:
                        data = self._decompress_blocks(
                            raw_data, 
                            entry.block_size,
                            entry.uncompressed_size
                        )
                    else:
                        # Single block decompression
                        data = zlib.decompress(raw_data)
                except zlib.error as e:
                    print(f"[ERROR] Decompression failed for {file_path}: {e}")
                    return None
            else:
                data = raw_data
            
            return data
            
        except Exception as e:
            print(f"[ERROR] Failed to read {file_path}: {e}")
            return None
    
    # -------------------------------------------------------------------------
    # INTERNAL METHODS
    # -------------------------------------------------------------------------
    
    def _parse_idx_file(self):
        """
        Parse the IDX index file to build the file table.
        
        Reads the binary index file and populates self.file_entries
        with all file metadata.
        
        Raises:
            Exception: If parsing fails
        """
        with open(self.idx_path, 'rb') as f:
            # ---- Read header (16 bytes) ----
            header = f.read(16)
            if len(header) < 16:
                raise Exception("IDX file too small")
            
            # Parse header
            # Note: Structure may vary between ROSE versions
            version = struct.unpack('<I', header[0:4])[0]
            file_count = struct.unpack('<I', header[4:8])[0]
            # Reserved bytes 8-15 are ignored
            
            print(f"[INFO] VFS version: {version}, files: {file_count}")
            
            # ---- Read file entries ----
            for i in range(file_count):
                entry = VFSFileEntry()
                
                # Read filename length (2 bytes)
                name_len_data = f.read(2)
                if len(name_len_data) < 2:
                    break
                name_len = struct.unpack('<H', name_len_data)[0]
                
                # Read filename
                filename_data = f.read(name_len)
                # Decode, handling null terminator
                entry.path = filename_data.rstrip(b'\x00').decode('utf-8', errors='replace')
                entry.path = entry.path.replace('\\', '/')
                
                # Read file metadata (20 bytes typically)
                meta = f.read(20)
                if len(meta) < 20:
                    break
                
                entry.offset = struct.unpack('<I', meta[0:4])[0]
                entry.compressed_size = struct.unpack('<I', meta[4:8])[0]
                entry.uncompressed_size = struct.unpack('<I', meta[8:12])[0]
                entry.block_size = struct.unpack('<I', meta[12:16])[0]
                
                # Flags (4 bytes)
                flags = meta[16:20]
                entry.is_deleted = bool(flags[0])
                entry.is_compressed = bool(flags[1])
                entry.is_encrypted = bool(flags[2])
                # flags[3] is reserved
                
                # Store entry
                if not entry.is_deleted:
                    self.file_entries[entry.path] = entry
        
        print(f"[INFO] Loaded {len(self.file_entries)} file entries")
    
    def _decrypt_data(self, data: bytes) -> bytes:
        """
        Decrypt XOR-encrypted data.
        
        Uses the configured XOR key to decrypt data.
        
        Args:
            data: Encrypted data bytes
            
        Returns:
            Decrypted data bytes
        """
        result = bytearray(len(data))
        key_len = len(self.xor_key)
        
        for i, byte in enumerate(data):
            result[i] = byte ^ self.xor_key[i % key_len]
        
        return bytes(result)
    
    def _decompress_blocks(self, data: bytes, block_size: int, 
                           expected_size: int) -> bytes:
        """
        Decompress block-based compressed data.
        
        Some large files are compressed in chunks for better
        random access. This method handles that format.
        
        Args:
            data: Compressed data (all blocks concatenated)
            block_size: Size of each uncompressed block
            expected_size: Total expected uncompressed size
            
        Returns:
            Decompressed data
        """
        result = bytearray()
        offset = 0
        
        while offset < len(data) and len(result) < expected_size:
            # Each block starts with compressed size (4 bytes)
            if offset + 4 > len(data):
                break
            
            chunk_size = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            
            if offset + chunk_size > len(data):
                break
            
            # Decompress this block
            chunk_data = data[offset:offset+chunk_size]
            offset += chunk_size
            
            try:
                decompressed = zlib.decompress(chunk_data)
                result.extend(decompressed)
            except zlib.error:
                # If decompression fails, data might be uncompressed
                result.extend(chunk_data)
        
        return bytes(result[:expected_size])
    
    # -------------------------------------------------------------------------
    # UTILITY METHODS
    # -------------------------------------------------------------------------
    
    def set_xor_key(self, key: bytes):
        """
        Set a custom XOR encryption key.
        
        Different ROSE private servers may use different keys.
        Call this before open() if you know the server's key.
        
        Args:
            key: XOR key bytes (typically 8 bytes)
        """
        self.xor_key = key


# ==============================================================================
# REGISTER THE EXTRACTOR
# ==============================================================================
# This makes the extractor available to the ExtractorRegistry
# so it can be auto-detected based on file extension.
ExtractorRegistry.register(VFSExtractor)
