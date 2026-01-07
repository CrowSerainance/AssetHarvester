# ==============================================================================
# GRF EDITOR MODULE
# ==============================================================================
# Editor/Creator for Ragnarok Online GRF (Gravity Resource File) archives.
# This module CREATES and MODIFIES GRF files, complementing the grf_extractor
# which only reads and extracts.
#
# Features:
#   - Create new GRF archives from scratch
#   - Add files to existing GRF archives
#   - Remove files from GRF archives
#   - Repack GRF archives with compression
#   - Modify file table and headers
#
# GRF Format Overview:
#   - Header: 46 bytes with signature "Master of Magic"
#   - File table: Compressed list of file entries at end of file
#   - File data: Individual files, each potentially compressed (zlib)
#
# Usage:
#   # Create a new GRF
#   editor = GRFEditor()
#   editor.create("output.grf")
#   editor.add_file("data/sprite/monster.spr", "data\\sprite\\monster.spr")
#   editor.save()
#   editor.close()
#
#   # Add files to existing GRF
#   editor = GRFEditor()
#   editor.open("existing.grf")
#   editor.add_file("newfile.txt", "data\\newfile.txt")
#   editor.save()
#   editor.close()
#
# References:
#   - https://ragnarokresearchlab.github.io/file-formats/grf/
#   - https://github.com/vthibault/grf-loader
#   - GRFBuilder (C++ reference implementation)
# ==============================================================================

import os
import struct
import zlib
import time
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass


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
GRF_FILE_FLAG_MIXCRYPT = 0x02  # Uses mixed encryption (not implemented)
GRF_FILE_FLAG_DES = 0x04       # Uses DES encryption (not implemented)


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class GRFFileEntry:
    """
    Represents a file entry in the GRF archive.

    This is used internally by the editor to track files being added,
    modified, or removed from the archive.

    Attributes:
        path (str): Internal GRF path (e.g., "data\\sprite\\monster.spr")
        data (bytes): Actual file contents
        compressed (bool): Whether to compress this file
        flags (int): GRF file flags (FILE, MIXCRYPT, DES)
    """
    path: str
    data: bytes
    compressed: bool = True
    flags: int = GRF_FILE_FLAG_FILE


# ==============================================================================
# GRF EDITOR CLASS
# ==============================================================================

class GRFEditor:
    """
    Editor for creating and modifying Ragnarok Online GRF archives.

    This class provides functionality to:
    - Create new GRF files from scratch
    - Add files to GRF archives
    - Remove files from GRF archives
    - Repack and save GRF archives

    The editor works by maintaining an in-memory representation of the file
    table, then writing everything out when save() is called.

    Example:
        # Create a new GRF and add files
        editor = GRFEditor()
        editor.create("mygrf.grf")
        editor.add_file("C:\\data\\sprite.spr", "data\\sprite\\sprite.spr")
        editor.add_directory("C:\\data\\textures", "data\\texture")
        editor.save()
        editor.close()

    Attributes:
        grf_path (str): Path to the GRF file being edited
        files (dict): Dictionary of GRF paths to GRFFileEntry objects
        modified (bool): Whether the GRF has unsaved changes
    """

    def __init__(self):
        """Initialize the GRF editor."""
        self.grf_path: Optional[str] = None
        self.files: Dict[str, GRFFileEntry] = {}
        self.modified: bool = False
        self.version: int = GRF_VERSION_200

    # ==========================================================================
    # PUBLIC API
    # ==========================================================================

    def create(self, grf_path: str) -> bool:
        """
        Create a new empty GRF file.

        This initializes a new GRF archive. Files can then be added using
        add_file() and add_directory().

        Args:
            grf_path: Path where the new GRF will be created

        Returns:
            True if successful, False otherwise
        """
        self.grf_path = grf_path
        self.files = {}
        self.modified = True
        self.version = GRF_VERSION_200

        print(f"[INFO] Creating new GRF: {grf_path}")
        return True

    def open(self, grf_path: str) -> bool:
        """
        Open an existing GRF file for editing.

        This loads the file table from an existing GRF so you can add or
        remove files. Note: This does NOT load the actual file data into
        memory - that would be wasteful. It only loads the file table.

        To modify an existing GRF:
        1. Open it
        2. Add/remove files
        3. Call save() to write a new GRF

        Args:
            grf_path: Path to the existing GRF file

        Returns:
            True if successful, False otherwise
        """
        # Use the extractor to read the existing GRF structure
        from .grf_extractor import GRFExtractor

        extractor = GRFExtractor()
        if not extractor.open(grf_path):
            print(f"[ERROR] Failed to open GRF: {grf_path}")
            return False

        self.grf_path = grf_path
        self.files = {}
        self.version = extractor.version

        # Load file entries (but NOT the actual data - too memory intensive)
        print(f"[INFO] Loading file table from {grf_path}...")
        file_list = extractor.list_files()

        for entry in file_list:
            # Create a placeholder entry - we'll load data only if needed
            self.files[entry.path.lower()] = GRFFileEntry(
                path=entry.path,
                data=b'',  # Placeholder - will load on demand
                compressed=True,
                flags=GRF_FILE_FLAG_FILE
            )

        extractor.close()
        self.modified = False

        print(f"[INFO] Loaded {len(self.files)} files from GRF")
        return True

    def add_file(self, local_path: str, grf_path: str, compress: bool = True) -> bool:
        """
        Add a file from disk to the GRF archive.

        The file will be read from local_path and added to the GRF at grf_path.
        GRF paths use backslashes and are case-insensitive.

        Args:
            local_path: Path to the file on disk (e.g., "C:\\data\\sprite.spr")
            grf_path: Path within the GRF (e.g., "data\\sprite\\sprite.spr")
            compress: Whether to compress the file with zlib

        Returns:
            True if successful, False otherwise

        Example:
            editor.add_file("C:\\mydata\\custom.spr", "data\\sprite\\custom.spr")
        """
        # Read the file data
        try:
            with open(local_path, 'rb') as f:
                data = f.read()
        except Exception as e:
            print(f"[ERROR] Failed to read {local_path}: {e}")
            return False

        # Normalize GRF path (backslashes, lowercase for lookup)
        grf_path_normalized = grf_path.replace('/', '\\')
        grf_path_lower = grf_path_normalized.lower()

        # Add to file table
        self.files[grf_path_lower] = GRFFileEntry(
            path=grf_path_normalized,
            data=data,
            compressed=compress,
            flags=GRF_FILE_FLAG_FILE
        )

        self.modified = True

        size_kb = len(data) / 1024
        print(f"[INFO] Added {grf_path_normalized} ({size_kb:.1f} KB)")
        return True

    def add_directory(self, local_dir: str, grf_dir: str,
                     recursive: bool = True, compress: bool = True) -> int:
        """
        Add an entire directory to the GRF archive.

        This walks through local_dir and adds all files to the GRF under grf_dir.
        Very useful for bulk operations like "add all my custom sprites".

        Args:
            local_dir: Local directory path (e.g., "C:\\custom_data")
            grf_dir: Target directory in GRF (e.g., "data\\sprite")
            recursive: Whether to include subdirectories
            compress: Whether to compress files

        Returns:
            Number of files added

        Example:
            editor.add_directory("C:\\custom\\sprites", "data\\sprite", recursive=True)
        """
        if not os.path.isdir(local_dir):
            print(f"[ERROR] Directory not found: {local_dir}")
            return 0

        count = 0
        grf_dir_normalized = grf_dir.replace('/', '\\')

        print(f"[INFO] Adding directory {local_dir} -> {grf_dir_normalized}")

        # Walk directory tree
        for root, dirs, files in os.walk(local_dir):
            # Calculate relative path
            rel_root = os.path.relpath(root, local_dir)

            # Skip subdirectories if not recursive
            if not recursive and rel_root != '.':
                break

            # Process each file
            for filename in files:
                local_file_path = os.path.join(root, filename)

                # Build GRF path
                if rel_root == '.':
                    grf_file_path = f"{grf_dir_normalized}\\{filename}"
                else:
                    rel_path = rel_root.replace('/', '\\')
                    grf_file_path = f"{grf_dir_normalized}\\{rel_path}\\{filename}"

                # Add the file
                if self.add_file(local_file_path, grf_file_path, compress):
                    count += 1

        print(f"[INFO] Added {count} files from directory")
        return count

    def remove_file(self, grf_path: str) -> bool:
        """
        Remove a file from the GRF archive.

        Args:
            grf_path: Path within the GRF to remove

        Returns:
            True if file was found and removed, False otherwise
        """
        grf_path_lower = grf_path.lower().replace('/', '\\')

        if grf_path_lower in self.files:
            del self.files[grf_path_lower]
            self.modified = True
            print(f"[INFO] Removed {grf_path}")
            return True
        else:
            print(f"[WARN] File not found in GRF: {grf_path}")
            return False

    def list_files(self) -> List[str]:
        """
        Get list of all files currently in the GRF.

        Returns:
            List of GRF paths
        """
        return [entry.path for entry in self.files.values()]

    def save(self, output_path: Optional[str] = None) -> bool:
        """
        Save the GRF to disk.

        This writes out the complete GRF file with:
        - GRF header
        - All file data (compressed if requested)
        - Compressed file table

        Args:
            output_path: Optional different path to save to (defaults to self.grf_path)

        Returns:
            True if successful, False otherwise
        """
        if output_path:
            self.grf_path = output_path

        if not self.grf_path:
            print("[ERROR] No output path specified")
            return False

        if not self.modified:
            print("[INFO] No changes to save")
            return True

        print(f"[INFO] Saving GRF to {self.grf_path}...")

        try:
            with open(self.grf_path, 'wb') as f:
                self._write_grf(f)

            self.modified = False
            print(f"[SUCCESS] GRF saved: {self.grf_path}")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to save GRF: {e}")
            import traceback
            traceback.print_exc()
            return False

    def close(self):
        """
        Close the GRF editor and free resources.

        Warns if there are unsaved changes.
        """
        if self.modified:
            print("[WARN] Closing GRF editor with unsaved changes!")

        self.grf_path = None
        self.files = {}
        self.modified = False

    # ==========================================================================
    # PRIVATE METHODS - GRF WRITING
    # ==========================================================================

    def _write_grf(self, f):
        """
        Write the complete GRF structure to a file handle.

        GRF Structure:
        [Header - 46 bytes]
        [File Data - variable]
        [File Table - compressed]

        Args:
            f: Open file handle for writing (binary mode)
        """
        # Write header (we'll update it later with correct offsets)
        file_count = len(self.files)
        header_data = self._build_header(file_count, 0)  # Placeholder offset
        f.write(header_data)

        # Track file offsets as we write
        file_offsets: Dict[str, int] = {}
        file_sizes: Dict[str, Tuple[int, int]] = {}  # path -> (compressed, uncompressed)

        # Write each file's data
        print(f"[INFO] Writing {file_count} files...")
        for i, (path_lower, entry) in enumerate(sorted(self.files.items())):
            if (i + 1) % 100 == 0:
                print(f"[INFO] Writing file {i + 1}/{file_count}...")

            # Record current position (relative to start of file data, after header)
            file_offsets[path_lower] = f.tell() - GRF_HEADER_SIZE

            # Compress if requested
            if entry.compressed and len(entry.data) > 0:
                compressed_data = zlib.compress(entry.data, level=6)
                # Only use compressed if it's actually smaller
                if len(compressed_data) < len(entry.data):
                    f.write(compressed_data)
                    file_sizes[path_lower] = (len(compressed_data), len(entry.data))
                else:
                    f.write(entry.data)
                    file_sizes[path_lower] = (len(entry.data), len(entry.data))
            else:
                f.write(entry.data)
                file_sizes[path_lower] = (len(entry.data), len(entry.data))

        # Record where file table starts
        file_table_offset = f.tell() - GRF_HEADER_SIZE

        # Build file table
        print("[INFO] Building file table...")
        file_table_data = self._build_file_table(file_offsets, file_sizes)

        # Compress file table
        compressed_table = zlib.compress(file_table_data, level=9)

        # Write file table header (compressed size, uncompressed size)
        f.write(struct.pack('<I', len(compressed_table)))
        f.write(struct.pack('<I', len(file_table_data)))

        # Write compressed file table
        f.write(compressed_table)

        # Update header with correct file table offset
        f.seek(0)
        header_data = self._build_header(file_count, file_table_offset)
        f.write(header_data)

        print(f"[INFO] File table: {len(file_table_data)} bytes (compressed to {len(compressed_table)})")
        print(f"[SUCCESS] GRF write complete")

    def _build_header(self, file_count: int, file_table_offset: int) -> bytes:
        """
        Build the GRF header (46 bytes).

        Header Structure:
            - Signature: 15 bytes "Master of Magic"
            - Encryption key: 15 bytes (null)
            - File table offset: 4 bytes
            - Seed: 4 bytes (seems to be a random value, using 1)
            - File count: 4 bytes (actual count + 7)
            - Version: 4 bytes (0x200)

        Args:
            file_count: Number of files in the archive
            file_table_offset: Offset to the file table (from end of header)

        Returns:
            46 bytes of header data
        """
        header = bytearray()

        # Signature
        header.extend(GRF_SIGNATURE)

        # Encryption key (15 null bytes)
        header.extend(b'\x00' * 15)

        # File table offset
        header.extend(struct.pack('<I', file_table_offset))

        # Seed (arbitrary value)
        header.extend(struct.pack('<I', 1))

        # File count (stored as count + 7)
        header.extend(struct.pack('<I', file_count + 7))

        # Version
        header.extend(struct.pack('<I', self.version))

        return bytes(header)

    def _build_file_table(self, file_offsets: Dict[str, int],
                          file_sizes: Dict[str, Tuple[int, int]]) -> bytes:
        """
        Build the file table data (before compression).

        File Table Format (per entry):
            - Filename: Null-terminated string (Korean EUC-KR encoding)
            - Compressed size: 4 bytes
            - Compressed size aligned: 4 bytes (same value)
            - Uncompressed size: 4 bytes
            - Flags: 1 byte
            - File offset: 4 bytes

        Args:
            file_offsets: Dict of path -> offset in file
            file_sizes: Dict of path -> (compressed_size, uncompressed_size)

        Returns:
            Raw file table data (will be compressed before writing)
        """
        table = bytearray()

        for path_lower, entry in sorted(self.files.items()):
            # Encode filename to EUC-KR (Korean encoding)
            try:
                filename_bytes = entry.path.encode('euc-kr')
            except:
                filename_bytes = entry.path.encode('latin-1')

            # Write filename (null-terminated)
            table.extend(filename_bytes)
            table.append(0)  # Null terminator

            # Get sizes and offset
            compressed_size, uncompressed_size = file_sizes[path_lower]
            file_offset = file_offsets[path_lower]

            # Write entry data
            table.extend(struct.pack('<I', compressed_size))           # Compressed size
            table.extend(struct.pack('<I', compressed_size))           # Compressed size aligned
            table.extend(struct.pack('<I', uncompressed_size))         # Uncompressed size
            table.append(entry.flags)                                   # Flags
            table.extend(struct.pack('<I', file_offset))               # File offset

        return bytes(table)


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def create_grf_from_directory(directory: str, output_grf: str,
                              base_path: str = "", compress: bool = True) -> bool:
    """
    Convenience function to create a GRF from a directory.

    This is a high-level helper that:
    1. Creates a new GRF
    2. Adds all files from the directory
    3. Saves and closes

    Args:
        directory: Local directory containing files to pack
        output_grf: Output GRF path
        base_path: Base path inside GRF (e.g., "data" to pack files under data\\)
        compress: Whether to compress files

    Returns:
        True if successful

    Example:
        create_grf_from_directory("C:\\custom_data", "custom.grf", "data")
    """
    editor = GRFEditor()

    if not editor.create(output_grf):
        return False

    count = editor.add_directory(directory, base_path, recursive=True, compress=compress)

    if count == 0:
        print("[WARN] No files added to GRF")
        return False

    if not editor.save():
        return False

    editor.close()
    return True


# ==============================================================================
# STANDALONE TEST
# ==============================================================================

if __name__ == "__main__":
    import sys

    print("=== GRF Editor Test ===")

    # Test creating a simple GRF
    editor = GRFEditor()
    editor.create("test_output.grf")

    # Add this Python file to the GRF for testing
    editor.add_file(__file__, "data\\test\\grf_editor.py")

    # Save
    editor.save()
    editor.close()

    print("\n[SUCCESS] Test GRF created: test_output.grf")
    print("You can verify this with a GRF tool or the grf_extractor module")
