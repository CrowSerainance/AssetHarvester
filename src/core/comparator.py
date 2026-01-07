# ==============================================================================
# ASSET COMPARATOR MODULE
# ==============================================================================
# Compares extracted assets against vanilla baselines to identify custom content.
#
# Comparison statuses:
#   - "identical": File hash matches vanilla exactly (original game content)
#   - "modified":  Same path exists in vanilla but hash is different (edited)
#   - "new":       Path doesn't exist in vanilla at all (custom content!)
#   - "unknown":   Not yet compared or comparison failed
#
# Performance optimizations:
#   - Parallel file hashing using ThreadPoolExecutor
#   - Batch database operations
#   - Memory-efficient baseline cache
#
# Usage:
#   comparator = AssetComparator(database, game_id=1)
#   comparator.build_baseline("C:\\Games\\RO_Vanilla")
#   results = comparator.compare_client("C:\\Games\\ServerClient")
# ==============================================================================

import os
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from .hasher import FileHasher
from .database import Database


# ==============================================================================
# COMPARISON RESULT DATA CLASS
# ==============================================================================
@dataclass
class ComparisonResult:
    """
    Result of comparing a single file against the vanilla baseline.
    
    Attributes:
        path (str):         Relative path of the file
        status (str):       Comparison status (identical/modified/new/unknown)
        hash_md5 (str):     MD5 hash of the file
        size (int):         File size in bytes
        vanilla_hash (str): Hash from vanilla baseline (None if new)
    """
    path: str
    status: str
    hash_md5: str
    size: int
    vanilla_hash: Optional[str] = None


# ==============================================================================
# ASSET COMPARATOR CLASS
# ==============================================================================
class AssetComparator:
    """
    Compares extracted assets against vanilla baselines.

    This class is the core of custom content detection. It builds a "fingerprint"
    database of all files in a vanilla/original game client, then compares
    private server clients against this baseline to identify modifications
    and new custom content.

    The comparison process:
    1. Build baseline from vanilla client (one-time per game)
    2. Extract/scan private server client
    3. Compare each file's hash against baseline
    4. Mark files as identical, modified, or new

    Attributes:
        db (Database):      Database instance for storing baselines
        game_id (int):      ID of the game being compared
        hasher (FileHasher): File hashing utility
        baseline_cache (dict): In-memory cache of vanilla hashes
        workers (int):      Number of parallel workers for hashing
    """

    # Default number of parallel workers
    DEFAULT_WORKERS = 4

    def __init__(self, db: Database, game_id: int, workers: int = DEFAULT_WORKERS):
        """
        Initialize the comparator.

        Args:
            db: Database instance for storing/retrieving baselines
            game_id: ID of the game being compared
            workers: Number of parallel workers for file operations
        """
        self.db = db
        self.game_id = game_id
        self.workers = workers
        self.hasher = FileHasher(workers=workers)

        # In-memory cache of vanilla file hashes for faster comparison
        # Structure: {"relative/path": "md5hash"}
        self.baseline_cache: Dict[str, str] = {}

        # Load existing baseline into cache
        self._load_baseline_cache()
    
    def _load_baseline_cache(self):
        """Load vanilla baseline from database into memory cache."""
        session = self.db.Session()
        try:
            from .database import VanillaFile
            vanilla_files = session.query(VanillaFile).filter(
                VanillaFile.game_id == self.game_id
            ).all()
            
            self.baseline_cache = {
                vf.path.lower(): vf.hash_md5 
                for vf in vanilla_files
            }
            
            print(f"[INFO] Loaded {len(self.baseline_cache)} vanilla files into cache")
            
        finally:
            session.close()
    
    # ==========================================================================
    # BASELINE BUILDING
    # ==========================================================================
    
    def build_baseline(self, vanilla_path: str,
                       progress_callback: Callable[[int, int, str], None] = None,
                       file_extensions: List[str] = None,
                       batch_size: int = 100) -> int:
        """
        Build the vanilla baseline from an original game client.

        This scans all files in the vanilla client directory, computes their
        hashes in parallel, and stores them in the database. This only needs
        to be done once per game (unless the vanilla version changes).

        Performance: Uses parallel hashing and batch database inserts.

        Args:
            vanilla_path:      Path to the vanilla/original game client folder
            progress_callback: Optional function called with (current, total, filename)
                              for progress reporting
            file_extensions:   Optional list of extensions to include (e.g., ['.spr', '.bmp'])
                              If None, all files are included
            batch_size:        Number of files to process in each batch

        Returns:
            Number of files added to the baseline

        Example:
            >>> comparator = AssetComparator(db, game_id=1)
            >>> count = comparator.build_baseline("C:\\Games\\RO_Vanilla")
            >>> print(f"Added {count} files to baseline")
        """
        if not os.path.isdir(vanilla_path):
            raise ValueError(f"Vanilla path does not exist: {vanilla_path}")

        print(f"[INFO] Building baseline from: {vanilla_path}")
        print(f"[INFO] Using {self.workers} parallel workers")

        # Collect all files
        all_files = []
        ext_filter = set(e.lower() for e in file_extensions) if file_extensions else None

        for root, dirs, files in os.walk(vanilla_path):
            for filename in files:
                if ext_filter:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext not in ext_filter:
                        continue

                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, vanilla_path)
                all_files.append((full_path, rel_path))

        total_files = len(all_files)
        print(f"[INFO] Found {total_files} files to process")

        # Process files in batches with parallel hashing
        added_count = 0
        processed = 0

        for batch_start in range(0, total_files, batch_size):
            batch_end = min(batch_start + batch_size, total_files)
            batch = all_files[batch_start:batch_end]

            # Hash files in parallel
            file_paths = [fp for fp, _ in batch]
            hashes = self.hasher.hash_files_parallel(file_paths)

            # Prepare batch insert data
            batch_data = []
            for full_path, rel_path in batch:
                try:
                    md5_hash = hashes.get(full_path)
                    if md5_hash:
                        file_size = os.path.getsize(full_path)
                        batch_data.append({
                            'game_id': self.game_id,
                            'path': rel_path,
                            'hash_md5': md5_hash,
                            'size': file_size
                        })
                        self.baseline_cache[rel_path.lower()] = md5_hash
                        added_count += 1
                except Exception as e:
                    print(f"[WARN] Failed to process {rel_path}: {e}")

            # Batch insert to database
            if batch_data:
                self._batch_insert_vanilla_files(batch_data)

            processed += len(batch)
            if progress_callback:
                progress_callback(processed, total_files, f"Processed {processed}/{total_files}")

        print(f"[INFO] Added {added_count} files to baseline")
        return added_count

    def _batch_insert_vanilla_files(self, files_data: List[Dict]):
        """Batch insert vanilla files into database."""
        from .database import VanillaFile
        session = self.db.Session()
        try:
            session.bulk_insert_mappings(VanillaFile, files_data)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"[ERROR] Batch insert failed: {e}")
        finally:
            session.close()
    
    def clear_baseline(self):
        """
        Clear the baseline for this game.
        
        Use this if you need to rebuild the baseline from scratch.
        """
        session = self.db.Session()
        try:
            from .database import VanillaFile
            deleted = session.query(VanillaFile).filter(
                VanillaFile.game_id == self.game_id
            ).delete()
            session.commit()
            
            # Clear cache
            self.baseline_cache.clear()
            
            print(f"[INFO] Cleared {deleted} vanilla files from baseline")
            
        finally:
            session.close()
    
    # ==========================================================================
    # COMPARISON
    # ==========================================================================
    
    def compare_file(self, file_path: str, rel_path: str) -> ComparisonResult:
        """
        Compare a single file against the vanilla baseline.
        
        Args:
            file_path: Full path to the file to compare
            rel_path:  Relative path (used for lookup in baseline)
            
        Returns:
            ComparisonResult with status and hash information
        """
        # Get file info
        file_size = os.path.getsize(file_path) if os.path.isfile(file_path) else 0
        md5_hash = self.hasher.hash_file_md5(file_path)
        
        if not md5_hash:
            return ComparisonResult(
                path=rel_path,
                status='unknown',
                hash_md5='',
                size=file_size
            )
        
        # Look up in baseline cache (case-insensitive)
        path_lower = rel_path.lower()
        vanilla_hash = self.baseline_cache.get(path_lower)
        
        # Determine status
        if vanilla_hash is None:
            # File doesn't exist in vanilla = NEW custom content!
            status = 'new'
        elif vanilla_hash.lower() == md5_hash.lower():
            # Hash matches = identical to vanilla
            status = 'identical'
        else:
            # Path exists but hash differs = modified
            status = 'modified'
        
        return ComparisonResult(
            path=rel_path,
            status=status,
            hash_md5=md5_hash,
            size=file_size,
            vanilla_hash=vanilla_hash
        )
    
    def compare_files(self, files: List[Dict[str, str]],
                      progress_callback: Callable[[int, int, str], None] = None
                      ) -> Dict[str, List[ComparisonResult]]:
        """
        Compare multiple files against the vanilla baseline using parallel hashing.

        Args:
            files: List of dicts with 'path' and 'rel_path' keys
            progress_callback: Optional progress callback

        Returns:
            Dictionary with keys 'identical', 'modified', 'new', 'unknown'
            Each containing a list of ComparisonResult objects
        """
        results = {
            'identical': [],
            'modified': [],
            'new': [],
            'unknown': []
        }

        total = len(files)
        if total == 0:
            return results

        # Parallel hash all files first
        file_paths = [f['path'] for f in files]
        hashes = self.hasher.hash_files_parallel(file_paths)

        # Now compare using cached hashes (very fast)
        for idx, file_info in enumerate(files):
            full_path = file_info['path']
            rel_path = file_info['rel_path']

            if progress_callback:
                progress_callback(idx + 1, total, rel_path)

            # Get hash from parallel results
            md5_hash = hashes.get(full_path)
            file_size = os.path.getsize(full_path) if os.path.isfile(full_path) else 0

            if not md5_hash:
                results['unknown'].append(ComparisonResult(
                    path=rel_path,
                    status='unknown',
                    hash_md5='',
                    size=file_size
                ))
                continue

            # Look up in baseline cache (case-insensitive)
            path_lower = rel_path.lower()
            vanilla_hash = self.baseline_cache.get(path_lower)

            # Determine status
            if vanilla_hash is None:
                status = 'new'
            elif vanilla_hash.lower() == md5_hash.lower():
                status = 'identical'
            else:
                status = 'modified'

            results[status].append(ComparisonResult(
                path=rel_path,
                status=status,
                hash_md5=md5_hash,
                size=file_size,
                vanilla_hash=vanilla_hash
            ))

        return results
    
    def compare_directory(self, client_path: str,
                          progress_callback: Callable[[int, int, str], None] = None,
                          file_extensions: List[str] = None
                          ) -> Dict[str, List[ComparisonResult]]:
        """
        Compare all files in a directory against the vanilla baseline.
        
        This is the main method for comparing a private server client.
        
        Args:
            client_path: Path to the client folder to compare
            progress_callback: Optional progress callback
            file_extensions: Optional list of extensions to include
            
        Returns:
            Dictionary with keys 'identical', 'modified', 'new', 'unknown'
        """
        if not os.path.isdir(client_path):
            raise ValueError(f"Client path does not exist: {client_path}")
        
        print(f"[INFO] Comparing client: {client_path}")
        
        # Collect all files
        files = []
        for root, dirs, filenames in os.walk(client_path):
            for filename in filenames:
                # Check extension filter
                if file_extensions:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext not in [e.lower() for e in file_extensions]:
                        continue
                
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, client_path)
                files.append({'path': full_path, 'rel_path': rel_path})
        
        print(f"[INFO] Found {len(files)} files to compare")
        
        # Compare all files
        results = self.compare_files(files, progress_callback)
        
        # Print summary
        print(f"\n[RESULTS]")
        print(f"  Identical: {len(results['identical'])}")
        print(f"  Modified:  {len(results['modified'])}")
        print(f"  New:       {len(results['new'])} (CUSTOM CONTENT)")
        print(f"  Unknown:   {len(results['unknown'])}")
        
        return results
    
    # ==========================================================================
    # STATISTICS
    # ==========================================================================
    
    def get_baseline_stats(self) -> dict:
        """Get statistics about the current baseline."""
        session = self.db.Session()
        try:
            from .database import VanillaFile
            from sqlalchemy import func
            
            total = session.query(VanillaFile).filter(
                VanillaFile.game_id == self.game_id
            ).count()
            
            total_size = session.query(func.sum(VanillaFile.size)).filter(
                VanillaFile.game_id == self.game_id
            ).scalar() or 0
            
            return {
                'total_files': total,
                'total_size': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2)
            }
            
        finally:
            session.close()
