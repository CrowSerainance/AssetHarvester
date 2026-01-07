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
#
# Performance optimizations:
#   - Uses 256KB chunks for optimal SSD throughput
#   - Supports parallel hashing via hash_files_parallel()
#   - Memory-mapped file support for very large files
# ==============================================================================

import os
import hashlib
import mmap
from typing import Optional, Tuple, BinaryIO, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed


class FileHasher:
    """
    File hashing utility for asset comparison.

    This class provides methods for computing file hashes that are used to
    compare extracted assets against vanilla baseline files. A matching hash
    indicates the file is unchanged from the original game.

    Attributes:
        chunk_size (int): Size of chunks to read when hashing large files.
                         Default is 256KB for optimal SSD performance.
    """

    # Default chunk size for reading files (256KB)
    # Larger chunks = better throughput on modern SSDs
    # 256KB is optimal for NVMe and SATA SSDs
    DEFAULT_CHUNK_SIZE = 262144  # 256KB

    # Threshold for using memory-mapped files (10MB)
    MMAP_THRESHOLD = 10 * 1024 * 1024

    # Default number of parallel workers
    DEFAULT_WORKERS = 4
    
    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, workers: int = DEFAULT_WORKERS):
        """
        Initialize the file hasher.

        Args:
            chunk_size: Size of chunks to read when hashing files.
                       Larger chunks = faster but more memory.
                       Default is 256KB for optimal SSD throughput.
            workers: Number of parallel workers for batch operations.
        """
        self.chunk_size = chunk_size
        self.workers = workers
    
    # ==========================================================================
    # MD5 HASHING (Fast, good for comparison)
    # ==========================================================================
    
    def hash_file_md5(self, file_path: str) -> Optional[str]:
        """
        Compute MD5 hash of a file.

        MD5 is used for fast comparison of files. While MD5 is not
        cryptographically secure, it's fast and sufficient for detecting
        file changes.

        Uses memory-mapped files for large files (>10MB) for better performance.

        Args:
            file_path: Path to the file to hash

        Returns:
            32-character hexadecimal MD5 hash string, or None if file not found

        Example:
            >>> hasher = FileHasher()
            >>> hasher.hash_file_md5("data.grf")
            'e99a18c428cb38d5f260853678922e03'
        """
        if not os.path.isfile(file_path):
            return None

        try:
            file_size = os.path.getsize(file_path)

            # Use memory-mapped files for large files (faster I/O)
            if file_size > self.MMAP_THRESHOLD:
                return self._hash_file_mmap(file_path, 'md5')

            # Standard chunked reading for smaller files
            md5_hash = hashlib.md5()
            with open(file_path, 'rb') as f:
                # Use readinto for better performance with larger buffers
                buffer = bytearray(self.chunk_size)
                mv = memoryview(buffer)
                while True:
                    n = f.readinto(mv)
                    if not n:
                        break
                    md5_hash.update(mv[:n])

            return md5_hash.hexdigest()

        except (IOError, OSError) as e:
            print(f"[ERROR] Could not hash file {file_path}: {e}")
            return None

    def _hash_file_mmap(self, file_path: str, algorithm: str = 'md5') -> Optional[str]:
        """
        Hash a file using memory-mapped I/O for better performance.

        Args:
            file_path: Path to the file
            algorithm: Hash algorithm ('md5' or 'sha256')

        Returns:
            Hash string or None on error
        """
        try:
            hash_obj = hashlib.md5() if algorithm == 'md5' else hashlib.sha256()

            with open(file_path, 'rb') as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    # Process in chunks to avoid memory issues with huge files
                    file_size = mm.size()
                    offset = 0
                    while offset < file_size:
                        chunk_end = min(offset + self.chunk_size * 4, file_size)
                        hash_obj.update(mm[offset:chunk_end])
                        offset = chunk_end

            return hash_obj.hexdigest()

        except Exception as e:
            print(f"[ERROR] mmap hash failed for {file_path}: {e}")
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

        Uses memory-mapped files for large files (>10MB) for better performance.

        Args:
            file_path: Path to the file to hash

        Returns:
            64-character hexadecimal SHA256 hash string, or None if not found
        """
        if not os.path.isfile(file_path):
            return None

        try:
            file_size = os.path.getsize(file_path)

            # Use memory-mapped files for large files
            if file_size > self.MMAP_THRESHOLD:
                return self._hash_file_mmap(file_path, 'sha256')

            sha256_hash = hashlib.sha256()
            with open(file_path, 'rb') as f:
                buffer = bytearray(self.chunk_size)
                mv = memoryview(buffer)
                while True:
                    n = f.readinto(mv)
                    if not n:
                        break
                    sha256_hash.update(mv[:n])

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

    # ==========================================================================
    # PARALLEL HASHING (High Performance)
    # ==========================================================================

    def hash_files_parallel(self, file_paths: List[str],
                           progress_callback=None) -> Dict[str, Optional[str]]:
        """
        Hash multiple files in parallel using thread pool.

        This method provides significant speedup when hashing many files
        by utilizing multiple CPU cores for I/O-bound operations.

        Args:
            file_paths: List of file paths to hash
            progress_callback: Optional callback(current, total, filename)

        Returns:
            Dictionary mapping file paths to their MD5 hashes

        Example:
            >>> hasher = FileHasher()
            >>> hashes = hasher.hash_files_parallel(["file1.spr", "file2.spr"])
            >>> print(hashes["file1.spr"])
            'abc123...'
        """
        results = {}
        total = len(file_paths)

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            # Submit all tasks
            future_to_path = {
                executor.submit(self.hash_file_md5, path): path
                for path in file_paths
            }

            # Collect results as they complete
            for i, future in enumerate(as_completed(future_to_path)):
                path = future_to_path[future]
                try:
                    results[path] = future.result()
                except Exception as e:
                    print(f"[ERROR] Failed to hash {path}: {e}")
                    results[path] = None

                if progress_callback:
                    progress_callback(i + 1, total, path)

        return results

    def hash_files_with_info_parallel(self, file_paths: List[str],
                                      progress_callback=None) -> List[Dict]:
        """
        Hash multiple files in parallel and return full info for each.

        Args:
            file_paths: List of file paths to hash
            progress_callback: Optional callback(current, total, filename)

        Returns:
            List of dicts with keys: path, size, hash_md5
        """
        results = []
        total = len(file_paths)

        def hash_with_info(path):
            if not os.path.isfile(path):
                return None
            return {
                'path': path,
                'size': os.path.getsize(path),
                'hash_md5': self.hash_file_md5(path)
            }

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            future_to_path = {
                executor.submit(hash_with_info, path): path
                for path in file_paths
            }

            for i, future in enumerate(as_completed(future_to_path)):
                path = future_to_path[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"[ERROR] Failed to process {path}: {e}")

                if progress_callback:
                    progress_callback(i + 1, total, path)

        return results


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


def hash_files_batch(file_paths: List[str], workers: int = 4) -> Dict[str, Optional[str]]:
    """
    Hash multiple files in parallel (convenience function).

    Args:
        file_paths: List of file paths to hash
        workers: Number of parallel workers

    Returns:
        Dictionary mapping paths to MD5 hashes
    """
    hasher = FileHasher(workers=workers)
    return hasher.hash_files_parallel(file_paths)
