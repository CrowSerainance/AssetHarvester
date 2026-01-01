# ==============================================================================
# GENERIC EXTRACTOR MODULE
# ==============================================================================
# A universal extractor that uses QuickBMS for formats not natively supported.
# QuickBMS is a powerful script-based extraction tool that supports hundreds
# of game archive formats.
#
# This extractor:
#   - Uses QuickBMS.exe as an external tool
#   - Supports any format that has a BMS script available
#   - Automatically downloads BMS scripts if not present
#
# Requirements:
#   - QuickBMS.exe must be in the tools/ directory
#   - BMS scripts for specific games in tools/scripts/
#
# Usage:
#   extractor = GenericExtractor()
#   extractor.set_script("rf_online.bms")
#   extractor.open("data.pak")
#   extractor.extract_all("output/")
# ==============================================================================

import os
import subprocess
import tempfile
from typing import List, Optional
from .base_extractor import BaseExtractor, FileEntry, ExtractorRegistry


# ==============================================================================
# QUICKBMS CONFIGURATION
# ==============================================================================

# Default location for QuickBMS executable (relative to project root)
QUICKBMS_DEFAULT_PATH = "tools/quickbms.exe"

# Default location for BMS scripts
BMS_SCRIPTS_PATH = "tools/scripts"

# Known BMS scripts for different games
# Format: "game_name": "script_filename"
KNOWN_SCRIPTS = {
    "rf_online": "rf_online.bms",
    "mu_online": "mu_online.bms",
    "silkroad": "silkroad_pk2.bms",
    "lineage2": "lineage2.bms",
    "flyff": "flyff.bms",
    "metin2": "metin2.bms",
}


# ==============================================================================
# GENERIC EXTRACTOR CLASS
# ==============================================================================
class GenericExtractor(BaseExtractor):
    """
    Universal extractor using QuickBMS for unsupported formats.
    
    This extractor acts as a fallback for any game archive format that doesn't
    have a native Python extractor. It delegates extraction to QuickBMS, which
    supports hundreds of formats through BMS scripts.
    
    To use this extractor:
    1. Ensure QuickBMS.exe is in the tools/ directory
    2. Set the appropriate BMS script with set_script()
    3. Open and extract as normal
    
    Attributes:
        quickbms_path (str): Path to QuickBMS executable
        script_path (str): Path to the BMS script to use
        game_id (str): Identifier for the game format
    """
    
    def __init__(self, archive_path: str = None, quickbms_path: str = None):
        """
        Initialize the generic extractor.
        
        Args:
            archive_path: Optional path to archive to open
            quickbms_path: Optional custom path to QuickBMS executable
        """
        self.quickbms_path = quickbms_path or self._find_quickbms()
        self.script_path: Optional[str] = None
        self.game_id = "generic"
        self._temp_dir: Optional[str] = None
        
        # Call parent init
        super().__init__(archive_path)
    
    # ==========================================================================
    # ABSTRACT PROPERTY IMPLEMENTATIONS
    # ==========================================================================
    
    @property
    def game_name(self) -> str:
        return f"Generic ({self.game_id})"
    
    @property
    def supported_extensions(self) -> List[str]:
        # This extractor can potentially handle any extension
        # depending on which BMS script is loaded
        return ['.pak', '.dat', '.bin', '.arc', '.pkg', '.res', '.pk2', '.bmd']
    
    @property
    def extractor_id(self) -> str:
        return "generic"
    
    # ==========================================================================
    # QUICKBMS CONFIGURATION
    # ==========================================================================
    
    def _find_quickbms(self) -> Optional[str]:
        """Find QuickBMS executable in common locations."""
        # Try to use Paths class first (handles frozen exe)
        try:
            from src.core.paths import Paths
            qbms = Paths.get_quickbms_path()
            if os.path.isfile(qbms):
                return qbms
        except ImportError:
            pass
        
        # Fallback: Try relative paths from project root
        possible_paths = [
            QUICKBMS_DEFAULT_PATH,
            "quickbms.exe",
            "tools/quickbms/quickbms.exe",
            os.path.expanduser("~/quickbms/quickbms.exe"),
        ]
        
        for path in possible_paths:
            if os.path.isfile(path):
                return os.path.abspath(path)
        
        return None
    
    def set_script(self, script_path: str):
        """
        Set the BMS script to use for extraction.
        
        Args:
            script_path: Path to the BMS script file, or name of a known script
        """
        # Check if it's a known script name
        if script_path in KNOWN_SCRIPTS:
            script_path = os.path.join(BMS_SCRIPTS_PATH, KNOWN_SCRIPTS[script_path])
        
        if not os.path.isfile(script_path):
            raise FileNotFoundError(f"BMS script not found: {script_path}")
        
        self.script_path = script_path
        
        # Extract game ID from script name
        self.game_id = os.path.splitext(os.path.basename(script_path))[0]
    
    def set_quickbms_path(self, path: str):
        """
        Set the path to QuickBMS executable.
        
        Args:
            path: Path to QuickBMS.exe
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"QuickBMS not found: {path}")
        self.quickbms_path = path
    
    # ==========================================================================
    # ABSTRACT METHOD IMPLEMENTATIONS
    # ==========================================================================
    
    def detect(self, path: str) -> bool:
        """
        Check if this extractor can handle the file.
        
        The generic extractor can potentially handle any file, but we check
        if QuickBMS is available and if we have a script set.
        """
        # Check if QuickBMS is available
        if not self.quickbms_path or not os.path.isfile(self.quickbms_path):
            return False
        
        # Check if file exists
        if not os.path.isfile(path):
            return False
        
        # Check extension is in our supported list
        ext = os.path.splitext(path)[1].lower()
        return ext in self.supported_extensions
    
    def open(self, archive_path: str) -> bool:
        """
        Open an archive for extraction.
        
        For QuickBMS, we don't actually "open" the archive in the traditional
        sense - we just verify it exists and prepare for extraction.
        """
        if self._is_open:
            self.close()
        
        # Verify QuickBMS is available
        if not self.quickbms_path:
            print("[ERROR] QuickBMS executable not found")
            return False
        
        # Verify archive exists
        if not os.path.isfile(archive_path):
            print(f"[ERROR] Archive not found: {archive_path}")
            return False
        
        # Verify script is set
        if not self.script_path:
            print("[ERROR] No BMS script set. Call set_script() first.")
            return False
        
        self.archive_path = archive_path
        self._is_open = True
        
        # Try to get file list
        self._populate_file_list()
        
        print(f"[INFO] Opened archive: {archive_path}")
        print(f"[INFO] Using script: {self.script_path}")
        return True
    
    def close(self):
        """Close the archive and clean up."""
        self._is_open = False
        self._file_list = []
        
        # Clean up temp directory if used
        if self._temp_dir and os.path.isdir(self._temp_dir):
            try:
                import shutil
                shutil.rmtree(self._temp_dir)
            except:
                pass
            self._temp_dir = None
    
    def list_files(self) -> List[FileEntry]:
        """Get list of files in the archive."""
        return self._file_list.copy()
    
    def extract_file(self, file_path: str, output_path: str) -> bool:
        """
        Extract a single file from the archive.
        
        Note: QuickBMS doesn't easily support extracting single files,
        so this extracts to a temp directory and copies the target file.
        """
        if not self._is_open:
            return False
        
        # For single file extraction, we use QuickBMS with filter
        try:
            # Create temp output directory
            temp_dir = tempfile.mkdtemp(prefix="asset_harvester_")
            
            # Build QuickBMS command with filter
            cmd = [
                self.quickbms_path,
                "-f", file_path,  # Filter to specific file
                self.script_path,
                self.archive_path,
                temp_dir
            ]
            
            # Run QuickBMS
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                print(f"[ERROR] QuickBMS failed: {result.stderr}")
                return False
            
            # Find and copy the extracted file
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    if f.lower() == os.path.basename(file_path).lower():
                        src = os.path.join(root, f)
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        import shutil
                        shutil.copy2(src, output_path)
                        return True
            
            return False
            
        except subprocess.TimeoutExpired:
            print("[ERROR] QuickBMS timed out")
            return False
        except Exception as e:
            print(f"[ERROR] Extraction failed: {e}")
            return False
        finally:
            # Clean up temp directory
            if temp_dir and os.path.isdir(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                except:
                    pass
    
    def get_file_data(self, file_path: str) -> Optional[bytes]:
        """
        Get file data without writing to disk.
        
        This extracts to a temp file and reads it back.
        """
        if not self._is_open:
            return None
        
        try:
            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_path = temp_file.name
            temp_file.close()
            
            # Extract to temp file
            if not self.extract_file(file_path, temp_path):
                return None
            
            # Read data
            with open(temp_path, 'rb') as f:
                data = f.read()
            
            return data
            
        finally:
            # Clean up temp file
            if os.path.isfile(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
    
    # ==========================================================================
    # QUICKBMS-SPECIFIC METHODS
    # ==========================================================================
    
    def extract_all(self, output_dir: str,
                    progress_callback = None,
                    file_filter = None) -> int:
        """
        Extract all files using QuickBMS.
        
        This overrides the base implementation to use QuickBMS directly,
        which is much faster than extracting files one by one.
        """
        if not self._is_open:
            raise RuntimeError("Archive is not open")
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Build QuickBMS command
        cmd = [
            self.quickbms_path,
            self.script_path,
            self.archive_path,
            output_dir
        ]
        
        print(f"[INFO] Running QuickBMS extraction...")
        
        try:
            # Run QuickBMS
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout for large archives
            )
            
            if result.returncode != 0:
                print(f"[ERROR] QuickBMS failed: {result.stderr}")
                return 0
            
            # Count extracted files
            count = 0
            for root, dirs, files in os.walk(output_dir):
                count += len(files)
            
            print(f"[INFO] Extracted {count} files")
            return count
            
        except subprocess.TimeoutExpired:
            print("[ERROR] QuickBMS timed out")
            return 0
        except Exception as e:
            print(f"[ERROR] Extraction failed: {e}")
            return 0
    
    def _populate_file_list(self):
        """
        Try to get file list from archive.
        
        QuickBMS has a list mode (-l) that outputs file information.
        """
        if not self._is_open:
            return
        
        try:
            # Build QuickBMS list command
            cmd = [
                self.quickbms_path,
                "-l",  # List mode
                self.script_path,
                self.archive_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                print(f"[WARN] Could not list files: {result.stderr}")
                return
            
            # Parse output
            self._file_list = []
            for line in result.stdout.split('\n'):
                # QuickBMS list format: offset size name
                parts = line.strip().split()
                if len(parts) >= 3:
                    try:
                        offset = int(parts[0])
                        size = int(parts[1])
                        name = ' '.join(parts[2:])
                        
                        self._file_list.append(FileEntry(
                            path=name,
                            size=size,
                            offset=offset
                        ))
                    except ValueError:
                        continue
            
            print(f"[INFO] Found {len(self._file_list)} files in archive")
            
        except subprocess.TimeoutExpired:
            print("[WARN] File listing timed out")
        except Exception as e:
            print(f"[WARN] Could not list files: {e}")


# ==============================================================================
# REGISTER EXTRACTOR
# ==============================================================================
ExtractorRegistry.register(GenericExtractor)
