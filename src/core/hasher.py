# ==============================================================================
# FILE HASHER MODULE
# ==============================================================================
# Provides file hashing utilities for comparing assets against vanilla baselines.
# Supports MD5 (fast) and SHA256 (secure) hashing algorithms.
#
# Usage:
#   hasher = FileHasher()
#   md5_hash = hasher.hash_file("path/to/file.txt")
#   md5_hash = hasher.hash_bytes(file_contents)
# ==============================================================================

import os
import hashlib
from typing import Optional, Tuple, BinaryIO


class FileHasher:
    """
    File hashing utility for asset comparison.
    
    This class provides methods for computing file hashes that are used to
    compare extracted assets against vanilla baseline files. A matching hash
    indicates the file is unchanged from the original game.
    
    Attributes:
        chunk_size (int): Size of chunks to read when hashing large files.
                         Default is 8KB which balances memory usage and speed.
    """
    
    # Default chunk size for reading files (8KB)
    # This prevents loading entire large files into memory
    DEFAULT_CHUNK_SIZE = 8192
    
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE):
        """
        Initialize the file hasher.
        
        Args:
            chunk_size: Size of chunks to read when hashing files.
                       Larger chunks = faster but more memory.
                       Default is 8KB.
        """
        self.chunk_size = chunk_size
    
    # ==========================================================================
    # MD5 HASHING (Fast, good for comparison)
    # ==========================================================================
    
    def hash_file_md5(self, file_path: str) -> Optional[str]:
        """
        Compute MD5 hash of a file.
        
        MD5 is used for fast comparison of files. While MD5 is not
        cryptographically secure, it's fast and sufficient for detecting
        file changes.
        
        Args:
            file_path: Path to the file to hash
            
        Returns:
            32-character hexadecimal MD5 hash string, or None if file not found
            
        Example:
            >>> hasher = FileHasher()
            >>> hasher.hash_file_md5("data.grf")
            'e99a18c428cb38d5f260853678922e03'
        """
        # Check if file exists
        if not os.path.isfile(file_path):
            return None
        
        # Create MD5 hash object
        md5_hash = hashlib.md5()
        
        try:
            # Open file in binary mode and read in chunks
            with open(file_path, 'rb') as f:
                # Read and update hash in chunks to handle large files
                for chunk in iter(lambda: f.read(self.chunk_size), b''):
                    md5_hash.update(chunk)
            
            # Return the hexadecimal representation
            return md5_hash.hexdigest()
            
        except (IOError, OSError) as e:
            # File couldn't be read (permissions, etc.)
            print(f"[ERROR] Could not hash file {file_path}: {e}")
            return None
    
    def hash_bytes_md5(self, data: bytes) -> str:
        """
        Compute MD5 hash of raw bytes.
        
        Use this when you already have file contents in memory
        (e.g., extracted from an archive).
        
        Args:
            data: Raw bytes to hash
            
        Returns:
            32-character hexadecimal MD5 hash string
            
        Example:
            >>> hasher = FileHasher()
            >>> hasher.hash_bytes_md5(b"Hello World")
            'b10a8db164e0754105b7a99be72e3fe5'
        """
        return hashlib.md5(data).hexdigest()
    
    def hash_stream_md5(self, stream: BinaryIO) -> str:
        """
        Compute MD5 hash from a file-like stream.
        
        Use this when working with archive file handles that support
        streaming reads without extracting to disk.
        
        Args:
            stream: A file-like object supporting read()
            
        Returns:
            32-character hexadecimal MD5 hash string
        """
        md5_hash = hashlib.md5()
        for chunk in iter(lambda: stream.read(self.chunk_size), b''):
            md5_hash.update(chunk)
        return md5_hash.hexdigest()
    
    # ==========================================================================
    # SHA256 HASHING (Secure, slower)
    # ==========================================================================
    
    def hash_file_sha256(self, file_path: str) -> Optional[str]:
        """
        Compute SHA256 hash of a file.
        
        SHA256 is more secure than MD5 and can be used when you need
        stronger guarantees about file integrity.
        
        Args:
            file_path: Path to the file to hash
            
        Returns:
            64-character hexadecimal SHA256 hash string, or None if not found
        """
        if not os.path.isfile(file_path):
            return None
        
        sha256_hash = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(self.chunk_size), b''):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except (IOError, OSError) as e:
            print(f"[ERROR] Could not hash file {file_path}: {e}")
            return None
    
    def hash_bytes_sha256(self, data: bytes) -> str:
        """
        Compute SHA256 hash of raw bytes.
        
        Args:
            data: Raw bytes to hash
            
        Returns:
            64-character hexadecimal SHA256 hash string
        """
        return hashlib.sha256(data).hexdigest()
    
    # ==========================================================================
    # DUAL HASHING (Both MD5 and SHA256)
    # ==========================================================================
    
    def hash_file_both(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Compute both MD5 and SHA256 hashes in a single file read.
        
        This is more efficient than calling hash_file_md5 and hash_file_sha256
        separately when you need both hashes.
        
        Args:
            file_path: Path to the file to hash
            
        Returns:
            Tuple of (md5_hash, sha256_hash), both None if file not found
            
        Example:
            >>> hasher = FileHasher()
            >>> md5, sha256 = hasher.hash_file_both("data.grf")
            >>> print(f"MD5: {md5}")
            >>> print(f"SHA256: {sha256}")
        """
        if not os.path.isfile(file_path):
            return (None, None)
        
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(self.chunk_size), b''):
                    # Update both hashes with the same chunk
                    md5_hash.update(chunk)
                    sha256_hash.update(chunk)
            
            return (md5_hash.hexdigest(), sha256_hash.hexdigest())
            
        except (IOError, OSError) as e:
            print(f"[ERROR] Could not hash file {file_path}: {e}")
            return (None, None)
    
    def hash_bytes_both(self, data: bytes) -> Tuple[str, str]:
        """
        Compute both MD5 and SHA256 hashes of raw bytes.
        
        Args:
            data: Raw bytes to hash
            
        Returns:
            Tuple of (md5_hash, sha256_hash)
        """
        return (
            hashlib.md5(data).hexdigest(),
            hashlib.sha256(data).hexdigest()
        )
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def get_file_info(self, file_path: str) -> Optional[dict]:
        """
        Get comprehensive file information including hash and size.
        
        This is a convenience method that returns all information needed
        for the vanilla baseline in one call.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with keys: path, size, hash_md5, hash_sha256
            Or None if file not found
            
        Example:
            >>> hasher = FileHasher()
            >>> info = hasher.get_file_info("sprite/monster.spr")
            >>> print(info)
            {'path': 'sprite/monster.spr', 'size': 12345, 
             'hash_md5': 'abc123...', 'hash_sha256': 'def456...'}
        """
        if not os.path.isfile(file_path):
            return None
        
        md5, sha256 = self.hash_file_both(file_path)
        
        return {
            'path': file_path,
            'size': os.path.getsize(file_path),
            'hash_md5': md5,
            'hash_sha256': sha256
        }
    
    @staticmethod
    def compare_hashes(hash1: str, hash2: str) -> bool:
        """
        Compare two hash strings (case-insensitive).
        
        Args:
            hash1: First hash string
            hash2: Second hash string
            
        Returns:
            True if hashes match, False otherwise
        """
        if hash1 is None or hash2 is None:
            return False
        return hash1.lower() == hash2.lower()


# ==============================================================================
# CONVENIENCE FUNCTION
# ==============================================================================
# For quick one-off hashing without creating an instance

def quick_hash(file_path: str, algorithm: str = 'md5') -> Optional[str]:
    """
    Quick hash function for one-off file hashing.
    
    Args:
        file_path: Path to the file to hash
        algorithm: Hash algorithm - 'md5' or 'sha256'
        
    Returns:
        Hash string or None if file not found
        
    Example:
        >>> from core.hasher import quick_hash
        >>> print(quick_hash("data.grf"))
        'e99a18c428cb38d5f260853678922e03'
    """
    hasher = FileHasher()
    if algorithm.lower() == 'sha256':
        return hasher.hash_file_sha256(file_path)
    return hasher.hash_file_md5(file_path)
