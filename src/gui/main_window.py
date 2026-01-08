# ==============================================================================
# MAIN WINDOW MODULE - FULLY FUNCTIONAL VERSION
# ==============================================================================
# Complete working GUI for Asset Harvester with all dialogs and functionality.
#
# Features:
#   - Add/manage games and servers
#   - Scan vanilla baselines
#   - Extract archives (GRF, VFS, etc.)
#   - Compare to find custom content
#   - Export only custom/modified files
# ==============================================================================

import os
import sys
import hashlib
import threading
from typing import Optional, List, Dict
from datetime import datetime

# ==============================================================================
# PyQt6 IMPORTS
# ==============================================================================
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTabWidget, QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox,
        QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
        QFileDialog, QMessageBox, QGroupBox, QSplitter, QTreeWidget,
        QTreeWidgetItem, QStatusBar, QToolBar, QSpacerItem, QSizePolicy,
        QDialog, QFormLayout, QDialogButtonBox, QCheckBox, QSpinBox,
        QListWidget, QListWidgetItem, QFrame, QGridLayout, QSlider,
        QScrollArea, QMenu, QInputDialog
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtGui import QAction, QIcon, QFont, QColor
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("[ERROR] PyQt6 is not installed. Install with: pip install PyQt6")

# ==============================================================================
# GUI MODULE IMPORTS
# ==============================================================================
# Import optional GUI widgets for RO-specific features
try:
    from src.gui.character_designer import CharacterDesignerWidget
    CHARACTER_DESIGNER_AVAILABLE = True
except ImportError:
    CHARACTER_DESIGNER_AVAILABLE = False
    print("[INFO] Character Designer module not loaded - this is optional")

try:
    from src.gui.act_spr_editor import ACTSPREditorWidget
    ACT_SPR_EDITOR_AVAILABLE = True
except ImportError:
    ACT_SPR_EDITOR_AVAILABLE = False
    print("[INFO] ACT/SPR Editor module not loaded - this is optional")

try:
    from src.gui.grf_browser import GRFBrowserWidget
    GRF_BROWSER_AVAILABLE = True
except ImportError:
    GRF_BROWSER_AVAILABLE = False
    print("[INFO] GRF Browser module not loaded - this is optional")


# ==============================================================================
# ADD GAME DIALOG
# ==============================================================================
class AddGameDialog(QDialog):
    """
    Dialog for adding a new game to the database.
    
    Allows user to specify:
    - Game name
    - Archive format (GRF, VFS, PAK, etc.)
    - File extensions to look for
    - Vanilla client path (optional)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Game")
        self.setMinimumWidth(500)
        self.setup_ui()
    
    def setup_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Form layout for inputs
        form = QFormLayout()
        
        # Game name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Ragnarok Online, ROSE Online, RF Online")
        form.addRow("Game Name:", self.name_edit)
        
        # Archive format dropdown
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "GRF (Ragnarok Online)",
            "VFS (ROSE Online)", 
            "PAK (RF Online)",
            "PKG (Generic)",
            "DAT (Lineage 2)",
            "Other (QuickBMS)"
        ])
        form.addRow("Archive Format:", self.format_combo)
        
        # File extensions
        self.extensions_edit = QLineEdit()
        self.extensions_edit.setPlaceholderText(".grf, .gpf")
        self.format_combo.currentIndexChanged.connect(self._update_extensions)
        self._update_extensions()
        form.addRow("File Extensions:", self.extensions_edit)
        
        # Vanilla client path
        vanilla_row = QHBoxLayout()
        self.vanilla_path_edit = QLineEdit()
        self.vanilla_path_edit.setPlaceholderText("Optional: Path to official/vanilla client")
        vanilla_row.addWidget(self.vanilla_path_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_vanilla)
        vanilla_row.addWidget(browse_btn)
        form.addRow("Vanilla Client:", vanilla_row)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _update_extensions(self):
        """Update extensions based on format selection."""
        format_extensions = {
            0: ".grf, .gpf",      # GRF
            1: ".vfs",            # VFS
            2: ".pak",            # PAK
            3: ".pkg",            # PKG
            4: ".dat, .u",        # DAT
            5: "*"                # Other
        }
        self.extensions_edit.setText(format_extensions.get(self.format_combo.currentIndex(), "*"))
    
    def _browse_vanilla(self):
        """Browse for vanilla client folder."""
        path = QFileDialog.getExistingDirectory(self, "Select Vanilla Client Folder")
        if path:
            self.vanilla_path_edit.setText(path)
    
    def get_data(self) -> dict:
        """Return the dialog data."""
        format_map = {
            0: "grf", 1: "vfs", 2: "pak", 3: "pkg", 4: "dat", 5: "other"
        }
        return {
            'name': self.name_edit.text().strip(),
            'format': format_map.get(self.format_combo.currentIndex(), "other"),
            'extensions': self.extensions_edit.text().strip(),
            'vanilla_path': self.vanilla_path_edit.text().strip()
        }


# ==============================================================================
# ADD SERVER DIALOG
# ==============================================================================
class AddServerDialog(QDialog):
    """
    Dialog for adding a new private server.
    
    Allows user to specify:
    - Server name
    - Game it belongs to
    - Client path
    - Website (optional)
    """
    
    def __init__(self, parent=None, games: List[tuple] = None):
        super().__init__(parent)
        self.setWindowTitle("Add New Server")
        self.setMinimumWidth(500)
        self.games = games or []
        self.setup_ui()
    
    def setup_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        # Server name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., NovaRO, OriginsRO, DreamerRO")
        form.addRow("Server Name:", self.name_edit)
        
        # Game selection
        self.game_combo = QComboBox()
        for game_id, game_name in self.games:
            self.game_combo.addItem(game_name, game_id)
        form.addRow("Game:", self.game_combo)
        
        # Client path
        client_row = QHBoxLayout()
        self.client_path_edit = QLineEdit()
        self.client_path_edit.setPlaceholderText("Path to this server's client folder")
        client_row.addWidget(self.client_path_edit)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_client)
        client_row.addWidget(browse_btn)
        form.addRow("Client Path:", client_row)
        
        # Website
        self.website_edit = QLineEdit()
        self.website_edit.setPlaceholderText("https://example.com (optional)")
        form.addRow("Website:", self.website_edit)
        
        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(80)
        self.notes_edit.setPlaceholderText("Any notes about this server...")
        form.addRow("Notes:", self.notes_edit)
        
        layout.addLayout(form)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _browse_client(self):
        """Browse for client folder."""
        path = QFileDialog.getExistingDirectory(self, "Select Server Client Folder")
        if path:
            self.client_path_edit.setText(path)
    
    def get_data(self) -> dict:
        """Return the dialog data."""
        return {
            'name': self.name_edit.text().strip(),
            'game_id': self.game_combo.currentData(),
            'client_path': self.client_path_edit.text().strip(),
            'website': self.website_edit.text().strip(),
            'notes': self.notes_edit.toPlainText().strip()
        }


# ==============================================================================
# WORKER THREAD FOR BACKGROUND OPERATIONS
# ==============================================================================
class ExtractWorker(QThread):
    """
    Background worker for extraction and comparison operations.
    
    Signals:
        progress(int, int, str): current, total, message
        log(str): log message
        finished(dict): results dictionary
        error(str): error message
    """
    progress = pyqtSignal(int, int, str)
    log = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, operation: str, **kwargs):
        super().__init__()
        self.operation = operation
        self.kwargs = kwargs
        self._cancelled = False
    
    def cancel(self):
        """Request cancellation."""
        self._cancelled = True
    
    def run(self):
        """Execute the operation."""
        try:
            if self.operation == "scan_baseline":
                self._scan_baseline()
            elif self.operation == "extract":
                self._extract()
            elif self.operation == "compare":
                self._compare()
            elif self.operation == "export_custom":
                self._export_custom()
        except Exception as e:
            self.error.emit(str(e))
    
    def _scan_baseline(self):
        """Scan a vanilla client to build baseline hashes."""
        path = self.kwargs.get('path')
        game_format = self.kwargs.get('format', 'grf')
        
        self.log.emit(f"Scanning baseline: {path}")
        self.log.emit(f"Format: {game_format}")
        
        # Find archive files
        archives = []
        extensions = self._get_extensions(game_format)
        
        for root, dirs, files in os.walk(path):
            for f in files:
                if any(f.lower().endswith(ext) for ext in extensions):
                    archives.append(os.path.join(root, f))
        
        self.log.emit(f"Found {len(archives)} archive(s)")
        
        if not archives:
            self.error.emit(f"No {game_format.upper()} archives found in {path}")
            return
        
        # Process each archive
        baseline_hashes = {}
        total_files = 0
        
        for i, archive_path in enumerate(archives):
            if self._cancelled:
                self.log.emit("Cancelled by user")
                return
            
            self.progress.emit(i, len(archives), f"Processing: {os.path.basename(archive_path)}")
            self.log.emit(f"\nProcessing: {archive_path}")
            
            # Get extractor for this format
            extractor = self._get_extractor(game_format, archive_path)
            if not extractor:
                self.log.emit(f"  [SKIP] No extractor for format: {game_format}")
                continue
            
            # List files in archive
            try:
                if extractor.open(archive_path):
                    files = extractor.list_files()
                    self.log.emit(f"  Found {len(files)} files")
                    
                    for j, entry in enumerate(files):
                        if self._cancelled:
                            self.log.emit("Cancelled by user")
                            return
                        
                        if j % 100 == 0:  # Check more frequently (every 100 files instead of 1000)
                            if self._cancelled:
                                self.log.emit("Cancelled by user")
                                return
                            self.progress.emit(j, len(files), f"Hashing: {entry.path[:50]}...")
                        
                        # Get file data and hash it
                        data = extractor.get_file_data(entry.path)
                        if data:
                            file_hash = hashlib.md5(data).hexdigest()
                            baseline_hashes[entry.path.lower()] = {
                                'hash': file_hash,
                                'size': len(data),
                                'archive': os.path.basename(archive_path)
                            }
                            total_files += 1
                    
                    extractor.close()
            except Exception as e:
                self.log.emit(f"  [ERROR] {e}")
        
        if self._cancelled:
            self.log.emit("\n⚠️ Baseline scan cancelled")
            self.finished.emit({
                'type': 'baseline',
                'hashes': baseline_hashes,
                'total': total_files,
                'cancelled': True
            })
        else:
            self.log.emit(f"\nBaseline complete: {total_files} files hashed")
            self.finished.emit({
                'type': 'baseline',
                'hashes': baseline_hashes,
                'total': total_files,
                'cancelled': False
            })
    
    def _extract(self):
        """Extract all files from archives."""
        source = self.kwargs.get('source')
        output = self.kwargs.get('output')
        game_format = self.kwargs.get('format', 'grf')
        
        self.log.emit(f"Extracting from: {source}")
        self.log.emit(f"Output to: {output}")
        
        # Find archives
        archives = []
        extensions = self._get_extensions(game_format)
        
        for root, dirs, files in os.walk(source):
            for f in files:
                if any(f.lower().endswith(ext) for ext in extensions):
                    archives.append(os.path.join(root, f))
        
        if not archives:
            self.error.emit(f"No archives found in {source}")
            return
        
        self.log.emit(f"Found {len(archives)} archive(s)")
        
        total_extracted = 0
        total_errors = 0
        
        for i, archive_path in enumerate(archives):
            if self._cancelled:
                self.log.emit("Cancelled")
                return
            
            self.log.emit(f"\nExtracting: {os.path.basename(archive_path)}")
            
            extractor = self._get_extractor(game_format, archive_path)
            if not extractor:
                continue
            
            try:
                if extractor.open(archive_path):
                    files = extractor.list_files()
                    self.log.emit(f"  {len(files)} files")
                    
                    for j, entry in enumerate(files):
                        if self._cancelled:
                            return
                        
                        if j % 100 == 0:
                            self.progress.emit(j, len(files), entry.path[:60])
                        
                        # Build output path
                        out_path = os.path.join(output, entry.path.replace('\\', os.sep))
                        
                        # Extract
                        if extractor.extract_file(entry.path, out_path):
                            total_extracted += 1
                        else:
                            total_errors += 1
                    
                    extractor.close()
            except Exception as e:
                self.log.emit(f"  [ERROR] {e}")
                total_errors += 1
        
        if self._cancelled:
            self.log.emit(f"\n⚠️ Extraction cancelled")
            self.finished.emit({
                'type': 'extract',
                'extracted': total_extracted,
                'errors': total_errors,
                'cancelled': True
            })
        else:
            self.log.emit(f"\nExtraction complete!")
            self.log.emit(f"  Extracted: {total_extracted}")
            self.log.emit(f"  Errors: {total_errors}")
            self.finished.emit({
                'type': 'extract',
                'extracted': total_extracted,
                'errors': total_errors,
                'cancelled': False
            })
    
    def _compare(self):
        """Compare client against baseline to find custom content."""
        source = self.kwargs.get('source')
        baseline = self.kwargs.get('baseline', {})
        game_format = self.kwargs.get('format', 'grf')
        
        self.log.emit(f"Comparing: {source}")
        self.log.emit(f"Baseline has {len(baseline)} files")
        
        if not baseline:
            self.error.emit("No baseline loaded! Scan vanilla first.")
            return
        
        # Find archives
        archives = []
        extensions = self._get_extensions(game_format)
        
        for root, dirs, files in os.walk(source):
            for f in files:
                if any(f.lower().endswith(ext) for ext in extensions):
                    archives.append(os.path.join(root, f))
        
        results = {
            'identical': [],      # Same hash as vanilla
            'modified': [],       # Different hash from vanilla
            'new': [],            # Not in vanilla at all
            'missing': []         # In vanilla but not in server
        }
        
        server_files = {}
        
        for archive_path in archives:
            if self._cancelled:
                return
            
            self.log.emit(f"\nScanning: {os.path.basename(archive_path)}")
            
            extractor = self._get_extractor(game_format, archive_path)
            if not extractor:
                continue
            
            try:
                if extractor.open(archive_path):
                    files = extractor.list_files()
                    
                    for j, entry in enumerate(files):
                        if self._cancelled:
                            return
                        
                        if j % 500 == 0:
                            self.progress.emit(j, len(files), f"Comparing: {entry.path[:50]}...")
                        
                        path_lower = entry.path.lower()
                        data = extractor.get_file_data(entry.path)
                        
                        if data:
                            file_hash = hashlib.md5(data).hexdigest()
                            server_files[path_lower] = {
                                'hash': file_hash,
                                'size': len(data),
                                'path': entry.path
                            }
                            
                            # Compare with baseline
                            if path_lower in baseline:
                                if baseline[path_lower]['hash'] == file_hash:
                                    results['identical'].append(entry.path)
                                else:
                                    results['modified'].append(entry.path)
                            else:
                                results['new'].append(entry.path)
                    
                    extractor.close()
            except Exception as e:
                self.log.emit(f"  [ERROR] {e}")
        
        # Find missing files
        for path in baseline:
            if path not in server_files:
                results['missing'].append(path)
        
        if self._cancelled:
            self.log.emit(f"\n⚠️ Comparison cancelled")
            self.finished.emit({
                'type': 'compare',
                'results': results,
                'server_files': server_files,
                'cancelled': True
            })
        else:
            self.log.emit(f"\n{'='*50}")
            self.log.emit(f"COMPARISON RESULTS:")
            self.log.emit(f"  Identical: {len(results['identical'])}")
            self.log.emit(f"  Modified:  {len(results['modified'])}")
            self.log.emit(f"  New:       {len(results['new'])}")
            self.log.emit(f"  Missing:   {len(results['missing'])}")
            self.log.emit(f"{'='*50}")
            
            custom_count = len(results['modified']) + len(results['new'])
            self.log.emit(f"\n>>> CUSTOM CONTENT: {custom_count} files <<<")
            
            self.finished.emit({
                'type': 'compare',
                'results': results,
                'server_files': server_files,
                'cancelled': False
            })
    
    def _export_custom(self):
        """Export only custom/modified files."""
        source = self.kwargs.get('source')
        output = self.kwargs.get('output')
        custom_files = self.kwargs.get('custom_files', [])
        game_format = self.kwargs.get('format', 'grf')
        
        self.log.emit(f"Exporting {len(custom_files)} custom files...")
        
        if not custom_files:
            self.error.emit("No custom files to export! Run comparison first.")
            return
        
        # Create output dir
        os.makedirs(output, exist_ok=True)
        
        # Find archives
        archives = []
        extensions = self._get_extensions(game_format)
        
        for root, dirs, files in os.walk(source):
            for f in files:
                if any(f.lower().endswith(ext) for ext in extensions):
                    archives.append(os.path.join(root, f))
        
        # Convert to set for fast lookup
        custom_set = set(f.lower() for f in custom_files)
        
        exported = 0
        
        for archive_path in archives:
            if self._cancelled:
                return
            
            extractor = self._get_extractor(game_format, archive_path)
            if not extractor:
                continue
            
            try:
                if extractor.open(archive_path):
                    files = extractor.list_files()
                    
                    for j, entry in enumerate(files):
                        if self._cancelled:
                            return
                        
                        if entry.path.lower() in custom_set:
                            out_path = os.path.join(output, entry.path.replace('\\', os.sep))
                            
                            if j % 50 == 0:
                                self.progress.emit(exported, len(custom_files), entry.path[:60])
                            
                            if extractor.extract_file(entry.path, out_path):
                                exported += 1
                    
                    extractor.close()
            except Exception as e:
                self.log.emit(f"[ERROR] {e}")
        
        if self._cancelled:
            self.log.emit(f"\n⚠️ Export cancelled")
            self.finished.emit({
                'type': 'export_custom',
                'exported': exported,
                'cancelled': True
            })
        else:
            self.log.emit(f"\nExported {exported} custom files to: {output}")
            self.finished.emit({
                'type': 'export_custom',
                'exported': exported,
                'cancelled': False
            })
    
    def _get_extensions(self, game_format: str) -> list:
        """Get file extensions for a format."""
        ext_map = {
            'grf': ['.grf', '.gpf'],
            'vfs': ['.vfs'],
            'pak': ['.pak'],
            'pkg': ['.pkg'],
            'dat': ['.dat', '.u'],
            'other': ['*']
        }
        return ext_map.get(game_format, ['*'])
    
    def _get_extractor(self, game_format: str, archive_path: str):
        """Get appropriate extractor for format."""
        try:
            if game_format == 'grf':
                from src.extractors.grf_extractor import GRFExtractor
                return GRFExtractor()
            elif game_format == 'vfs':
                from src.extractors.vfs_extractor import VFSExtractor
                return VFSExtractor()
            else:
                from src.extractors.generic_extractor import GenericExtractor
                return GenericExtractor()
        except ImportError as e:
            self.log.emit(f"[WARN] Extractor not available: {e}")
            return None


# ==============================================================================
# MAIN WINDOW CLASS
# ==============================================================================
class MainWindow(QMainWindow):
    """
    Primary application window for Asset Harvester.
    
    This is a fully functional GUI that allows:
    - Adding and managing games
    - Adding and managing private servers
    - Scanning vanilla baselines
    - Extracting all assets
    - Comparing to find custom content
    - Exporting only custom/modified files
    """
    
    def __init__(self):
        super().__init__()
        
        # Data storage
        self.db = None
        self.games = []          # List of (id, name, format, vanilla_path)
        self.servers = []        # List of server dicts
        self.baseline = {}       # {path: {hash, size, archive}}
        self.comparison = None   # Last comparison results
        self.worker = None       # Background worker thread
        
        # Initialize
        self._init_database()
        self._setup_window()
        self._setup_toolbar()
        self._setup_statusbar()  # Must be before _setup_tabs() because tabs may call _log()
        self._setup_tabs()
        self._load_data()
    
    def _init_database(self):
        """Initialize database connection."""
        try:
            from src.core.database import Database
            
            if getattr(sys, 'frozen', False):
                base = os.environ.get('APPDATA', os.path.expanduser('~'))
                data_dir = os.path.join(base, 'AssetHarvester')
            else:
                data_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    'data'
                )
            
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'harvester.db')
            self.db = Database(db_path)
            print(f"[INFO] Database: {db_path}")
        except Exception as e:
            print(f"[WARN] Database init failed: {e}")
            self.db = None
    
    # ==========================================================================
    # WINDOW SETUP
    # ==========================================================================
    
    def _setup_window(self):
        """Configure window properties."""
        self.setWindowTitle("Asset Harvester - Extract Custom Content from Private Servers")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Dark theme stylesheet
        self.setStyleSheet("""
            QMainWindow { background-color: #1a1a2e; }
            QTabWidget::pane { border: 1px solid #3d3d5c; background-color: #16213e; border-radius: 4px; }
            QTabBar::tab { background-color: #0f3460; color: #e0e0e0; padding: 10px 20px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background-color: #1a1a2e; color: #ffffff; }
            QTabBar::tab:hover { background-color: #1f4068; }
            QGroupBox { font-weight: bold; border: 1px solid #3d3d5c; border-radius: 4px; margin-top: 10px; padding-top: 10px; color: #e0e0e0; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QPushButton { background-color: #0f3460; color: #ffffff; border: none; padding: 8px 16px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #1f4068; }
            QPushButton:pressed { background-color: #0a2540; }
            QPushButton:disabled { background-color: #2d2d4d; color: #666666; }
            QPushButton#greenBtn { background-color: #1b5e20; }
            QPushButton#greenBtn:hover { background-color: #2e7d32; }
            QPushButton#orangeBtn { background-color: #e65100; }
            QPushButton#orangeBtn:hover { background-color: #ff6d00; }
            QLineEdit, QComboBox, QTextEdit, QSpinBox { background-color: #16213e; color: #e0e0e0; border: 1px solid #3d3d5c; padding: 6px; border-radius: 4px; }
            QLineEdit:focus, QComboBox:focus { border-color: #0f3460; }
            QTableWidget { background-color: #16213e; color: #e0e0e0; border: 1px solid #3d3d5c; gridline-color: #3d3d5c; }
            QTableWidget::item:selected { background-color: #0f3460; }
            QHeaderView::section { background-color: #0f3460; color: #ffffff; padding: 8px; border: none; }
            QProgressBar { border: 1px solid #3d3d5c; border-radius: 4px; text-align: center; color: #ffffff; background-color: #16213e; }
            QProgressBar::chunk { background-color: #4caf50; border-radius: 3px; }
            QLabel { color: #e0e0e0; }
            QTreeWidget { background-color: #16213e; color: #e0e0e0; border: 1px solid #3d3d5c; }
            QTreeWidget::item:selected { background-color: #0f3460; }
            QStatusBar { background-color: #0f3460; color: #e0e0e0; }
            QListWidget { background-color: #16213e; color: #e0e0e0; border: 1px solid #3d3d5c; }
            QDialog { background-color: #1a1a2e; }
        """)
    
    def _setup_toolbar(self):
        """Create toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Add Game
        add_game = QAction("➕ Add Game", self)
        add_game.setToolTip("Add a new game to the database")
        add_game.triggered.connect(self._on_add_game)
        toolbar.addAction(add_game)
        
        # Add Server
        add_server = QAction("🌐 Add Server", self)
        add_server.setToolTip("Add a new private server")
        add_server.triggered.connect(self._on_add_server)
        toolbar.addAction(add_server)
        
        toolbar.addSeparator()
        
        # Quick Extract
        quick_extract = QAction("⚡ Quick Extract Custom", self)
        quick_extract.setToolTip("Extract only custom content (requires baseline)")
        quick_extract.triggered.connect(self._on_quick_extract)
        toolbar.addAction(quick_extract)
        
        toolbar.addSeparator()
        
        # Refresh
        refresh = QAction("🔄 Refresh", self)
        refresh.triggered.connect(self._load_data)
        toolbar.addAction(refresh)
    
    def _setup_tabs(self):
        """Create tabbed interface."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self._create_extract_tab()    # Main functionality first
        self._create_servers_tab()
        self._create_results_tab()
        self._create_grf_browser_tab()  # GRF Browser (browse GRF contents)
        self._create_grf_editor_tab()  # GRF Editor/Creator (archive management)
        self._create_act_spr_editor_tab()  # ACT/SPR Editor (binary file editing)
        self._create_character_designer_tab()  # Character Designer (visual preview)
        self._create_settings_tab()
    
    def _setup_statusbar(self):
        """Create status bar."""
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(400)
        self.progress_bar.setVisible(False)
        self.statusbar.addPermanentWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready - Add a game and scan vanilla baseline to get started")
        self.statusbar.addWidget(self.status_label)
    
    # ==========================================================================
    # TAB CREATION
    # ==========================================================================
    
    def _create_extract_tab(self):
        """Create the main Extract tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # === STEP 1: SELECT GAME ===
        step1 = QGroupBox("Step 1: Select Game")
        step1_layout = QHBoxLayout(step1)
        
        step1_layout.addWidget(QLabel("Game:"))
        self.game_combo = QComboBox()
        self.game_combo.setMinimumWidth(200)
        self.game_combo.currentIndexChanged.connect(self._on_game_changed)
        step1_layout.addWidget(self.game_combo)
        
        add_game_btn = QPushButton("➕ Add Game")
        add_game_btn.clicked.connect(self._on_add_game)
        step1_layout.addWidget(add_game_btn)
        
        step1_layout.addStretch()
        
        self.baseline_status = QLabel("⚠️ No baseline loaded")
        self.baseline_status.setStyleSheet("color: #ff9800;")
        step1_layout.addWidget(self.baseline_status)
        
        layout.addWidget(step1)
        
        # === STEP 2: SCAN VANILLA BASELINE ===
        step2 = QGroupBox("Step 2: Scan Vanilla Baseline (Do this once per game)")
        step2_layout = QVBoxLayout(step2)
        
        vanilla_row = QHBoxLayout()
        vanilla_row.addWidget(QLabel("Vanilla Client:"))
        self.vanilla_path = QLineEdit()
        self.vanilla_path.setPlaceholderText("Path to official/vanilla game client folder...")
        vanilla_row.addWidget(self.vanilla_path)
        browse_vanilla = QPushButton("Browse...")
        browse_vanilla.clicked.connect(lambda: self._browse_path(self.vanilla_path))
        vanilla_row.addWidget(browse_vanilla)
        
        self.scan_baseline_btn = QPushButton("📁 Scan Vanilla Baseline")
        self.scan_baseline_btn.setObjectName("greenBtn")
        self.scan_baseline_btn.clicked.connect(self._on_scan_baseline)
        vanilla_row.addWidget(self.scan_baseline_btn)
        
        step2_layout.addLayout(vanilla_row)
        layout.addWidget(step2)
        
        # === STEP 3: PRIVATE SERVER CLIENT ===
        step3 = QGroupBox("Step 3: Select Private Server Client")
        step3_layout = QVBoxLayout(step3)
        
        server_row = QHBoxLayout()
        server_row.addWidget(QLabel("Server Client:"))
        self.server_path = QLineEdit()
        self.server_path.setPlaceholderText("Path to private server client folder...")
        server_row.addWidget(self.server_path)
        browse_server = QPushButton("Browse...")
        browse_server.clicked.connect(lambda: self._browse_path(self.server_path))
        server_row.addWidget(browse_server)
        step3_layout.addLayout(server_row)
        
        layout.addWidget(step3)
        
        # === STEP 4: OUTPUT ===
        step4 = QGroupBox("Step 4: Output Location")
        step4_layout = QHBoxLayout(step4)
        
        step4_layout.addWidget(QLabel("Output:"))
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Where to save extracted assets...")
        step4_layout.addWidget(self.output_path)
        browse_output = QPushButton("Browse...")
        browse_output.clicked.connect(lambda: self._browse_path(self.output_path))
        step4_layout.addWidget(browse_output)
        
        layout.addWidget(step4)
        
        # === ACTION BUTTONS ===
        actions = QHBoxLayout()
        
        self.extract_all_btn = QPushButton("📦 Extract ALL Files")
        self.extract_all_btn.setToolTip("Extract everything from the server client")
        self.extract_all_btn.clicked.connect(self._on_extract_all)
        actions.addWidget(self.extract_all_btn)
        
        self.compare_btn = QPushButton("🔍 Compare to Vanilla")
        self.compare_btn.setToolTip("Find files that are different from vanilla")
        self.compare_btn.clicked.connect(self._on_compare)
        actions.addWidget(self.compare_btn)
        
        self.export_custom_btn = QPushButton("⭐ Export CUSTOM Only")
        self.export_custom_btn.setObjectName("orangeBtn")
        self.export_custom_btn.setToolTip("Extract only custom/modified files (fastest!)")
        self.export_custom_btn.clicked.connect(self._on_export_custom)
        actions.addWidget(self.export_custom_btn)
        
        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        actions.addWidget(self.cancel_btn)
        
        actions.addStretch()
        layout.addLayout(actions)
        
        # === LOG OUTPUT ===
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMinimumHeight(200)
        log_layout.addWidget(self.log_text)
        
        clear_log = QPushButton("Clear Log")
        clear_log.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_log, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addWidget(log_group)
        
        self.tabs.addTab(tab, "⚡ Extract")
    
    def _create_servers_tab(self):
        """Create Servers management tab."""
        tab = QWidget()
        layout = QHBoxLayout(tab)
        
        # Games list
        games_group = QGroupBox("Games")
        games_layout = QVBoxLayout(games_group)
        
        self.games_table = QTableWidget()
        self.games_table.setColumnCount(4)
        self.games_table.setHorizontalHeaderLabels(["Name", "Format", "Vanilla Path", "Baseline"])
        self.games_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.games_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        games_layout.addWidget(self.games_table)
        
        game_btns = QHBoxLayout()
        add_game = QPushButton("➕ Add")
        add_game.clicked.connect(self._on_add_game)
        remove_game = QPushButton("🗑️ Remove")
        remove_game.clicked.connect(self._on_remove_game)
        game_btns.addWidget(add_game)
        game_btns.addWidget(remove_game)
        game_btns.addStretch()
        games_layout.addLayout(game_btns)
        
        layout.addWidget(games_group, 1)
        
        # Servers list
        servers_group = QGroupBox("Private Servers")
        servers_layout = QVBoxLayout(servers_group)
        
        self.servers_table = QTableWidget()
        self.servers_table.setColumnCount(4)
        self.servers_table.setHorizontalHeaderLabels(["Name", "Game", "Client Path", "Website"])
        self.servers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.servers_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        servers_layout.addWidget(self.servers_table)
        
        server_btns = QHBoxLayout()
        add_server = QPushButton("➕ Add")
        add_server.clicked.connect(self._on_add_server)
        remove_server = QPushButton("🗑️ Remove")
        remove_server.clicked.connect(self._on_remove_server)
        server_btns.addWidget(add_server)
        server_btns.addWidget(remove_server)
        server_btns.addStretch()
        servers_layout.addLayout(server_btns)
        
        layout.addWidget(servers_group, 2)
        
        self.tabs.addTab(tab, "📋 Servers")
    
    def _create_results_tab(self):
        """Create Results tab showing comparison results."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Summary
        summary_group = QGroupBox("Comparison Summary")
        summary_layout = QHBoxLayout(summary_group)
        
        self.identical_label = QLabel("Identical: 0")
        self.identical_label.setStyleSheet("color: #4caf50; font-weight: bold; font-size: 14px;")
        summary_layout.addWidget(self.identical_label)
        
        self.modified_label = QLabel("Modified: 0")
        self.modified_label.setStyleSheet("color: #ff9800; font-weight: bold; font-size: 14px;")
        summary_layout.addWidget(self.modified_label)
        
        self.new_label = QLabel("New: 0")
        self.new_label.setStyleSheet("color: #2196f3; font-weight: bold; font-size: 14px;")
        summary_layout.addWidget(self.new_label)
        
        self.custom_total_label = QLabel("CUSTOM TOTAL: 0")
        self.custom_total_label.setStyleSheet("color: #e91e63; font-weight: bold; font-size: 16px;")
        summary_layout.addWidget(self.custom_total_label)
        
        summary_layout.addStretch()
        layout.addWidget(summary_group)
        
        # File lists
        lists_layout = QHBoxLayout()
        
        # Modified files
        modified_group = QGroupBox("Modified Files (changed from vanilla)")
        modified_layout = QVBoxLayout(modified_group)
        self.modified_list = QListWidget()
        modified_layout.addWidget(self.modified_list)
        lists_layout.addWidget(modified_group)
        
        # New files
        new_group = QGroupBox("New Files (custom content)")
        new_layout = QVBoxLayout(new_group)
        self.new_list = QListWidget()
        new_layout.addWidget(self.new_list)
        lists_layout.addWidget(new_group)
        
        layout.addLayout(lists_layout)
        
        self.tabs.addTab(tab, "📊 Results")
    
    def _create_grf_browser_tab(self):
        """Create GRF Browser tab for browsing GRF contents."""
        if not GRF_BROWSER_AVAILABLE:
            # Create placeholder tab
            tab = QWidget()
            layout = QVBoxLayout(tab)
            
            info_label = QLabel(
                "<h2>📂 GRF Browser</h2>"
                "<p>The GRF Browser module could not be loaded.</p>"
                "<p>Make sure the following files exist:</p>"
                "<ul>"
                "<li>src/gui/grf_browser.py</li>"
                "<li>src/extractors/grf_vfs.py</li>"
                "</ul>"
            )
            info_label.setTextFormat(Qt.TextFormat.RichText)
            info_label.setWordWrap(True)
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(info_label)
            layout.addStretch()
            
            self.tabs.addTab(tab, "📂 GRF Browser")
            return
        
        # Create the GRF Browser widget
        self.grf_browser = GRFBrowserWidget()
        
        # Connect signals for integration
        self.grf_browser.file_selected.connect(self._on_grf_browser_file_selected)
        
        self.tabs.addTab(self.grf_browser, "📂 GRF Browser")
        self._log("GRF Browser loaded - Browse GRF archives without extraction")
    
    def _on_grf_browser_file_selected(self, file_path: str):
        """
        Handle file selection in GRF Browser.
        
        NOTE: This only logs the selection. Tab switching is handled by 
        right-click context menu -> "Open in Character Designer" only.
        """
        # Just log the selection - do NOT auto-switch tabs
        self._log(f"GRF Browser: Selected file: {file_path}")
        # Tab switching removed - user can right-click for "Open in Character Designer"
    
    def _create_act_spr_editor_tab(self):
        """
        Create the ACT/SPR Editor tab for binary file editing.
        
        This tab provides direct editing of Ragnarok Online ACT (action) and 
        SPR (sprite) files. It's separate from the Character Designer which 
        focuses on visual preview/composition.
        """
        # Check if the ACT/SPR Editor module is available
        if not ACT_SPR_EDITOR_AVAILABLE:
            # Create a placeholder tab
            tab = QWidget()
            layout = QVBoxLayout(tab)
            
            info_label = QLabel(
                "<h2>✏️ ACT/SPR Editor</h2>"
                "<p>The ACT/SPR Editor module could not be loaded.</p>"
                "<p>Make sure the following files exist:</p>"
                "<ul>"
                "<li>src/gui/act_spr_editor.py</li>"
                "<li>src/parsers/act_parser.py</li>"
                "<li>src/parsers/spr_parser.py</li>"
                "</ul>"
            )
            info_label.setTextFormat(Qt.TextFormat.RichText)
            info_label.setWordWrap(True)
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(info_label)
            layout.addStretch()
            
            self.tabs.addTab(tab, "✏️ ACT/SPR Editor")
            return
        
        # Create the ACT/SPR Editor widget
        self.act_spr_editor = ACTSPREditorWidget()
        self.tabs.addTab(self.act_spr_editor, "✏️ ACT/SPR Editor")
        self._log("ACT/SPR Editor loaded - Use this for binary editing of ACT/SPR files")
    
    def _create_character_designer_tab(self):
        """
        Create the RO Character Designer tab.
        
        This tab provides a visual character designer for Ragnarok Online sprites,
        allowing users to preview how harvested custom assets look compared to
        vanilla sprites. Features include:
        
        - Job/Class selection
        - Gender and hairstyle customization
        - Equipment slots (headgear, weapon, shield, garment)
        - Palette/dye options
        - Animation playback
        - Side-by-side comparison
        - Sprite export
        
        The Character Designer requires extracted RO data files (from GRF) to
        function. Point it to a folder containing the extracted 'data/sprite'
        directory structure.
        """
        # Check if the Character Designer module is available
        if not CHARACTER_DESIGNER_AVAILABLE:
            # Create a placeholder tab explaining the feature is not available
            tab = QWidget()
            layout = QVBoxLayout(tab)
            
            # Info message
            info_label = QLabel(
                "<h2>🎨 RO Character Designer</h2>"
                "<p>The Character Designer module could not be loaded.</p>"
                "<p>Make sure the following files exist:</p>"
                "<ul>"
                "<li>src/gui/character_designer.py</li>"
                "<li>src/parsers/spr_parser.py</li>"
                "<li>src/parsers/act_parser.py</li>"
                "</ul>"
                "<p>Also ensure PIL/Pillow is installed:</p>"
                "<pre>pip install Pillow</pre>"
            )
            info_label.setTextFormat(Qt.TextFormat.RichText)
            info_label.setWordWrap(True)
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(info_label)
            
            layout.addStretch()
            self.tabs.addTab(tab, "🎨 Character Designer")
            return
        
        # Create the Character Designer widget
        self.character_designer = CharacterDesignerWidget()
        
        # Connect signals for integration with main window
        self.character_designer.sprite_loaded.connect(self._on_designer_sprite_loaded)
        
        # Connect Character Designer to main window's database and baseline
        if self.character_designer.custom_detector:
            self.character_designer.custom_detector.database = self.db
            # Update baseline if we have one
            if self.baseline:
                self.character_designer.custom_detector.set_baseline(self.baseline)
        
        # Add to tabs
        self.tabs.addTab(self.character_designer, "🎨 Character Designer")
        
        # Log that it's ready
        self._log("Character Designer loaded - Set resource path to extracted RO data")
    
    def _on_designer_sprite_loaded(self, path: str):
        """
        Handle notification from Character Designer when sprites are loaded.
        
        Args:
            path: Path to the loaded sprite
        """
        self._log(f"Character Designer: Loaded sprite from {path}")
    
    def _create_grf_editor_tab(self):
        """
        Create the GRF Editor tab for creating and modifying GRF archives.

        This tab provides comprehensive GRF archive management:
        - Create new GRF files from scratch
        - Add files and directories to GRF archives
        - Remove files from GRF archives
        - Repack existing GRF archives
        - Preview GRF contents

        This is useful for creating custom content patches or distributing
        modified game assets in GRF format.
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Instructions
        instructions_label = QLabel(
            "<h3>📦 GRF Editor - Create & Modify GRF Archives</h3>"
            "<p>Create new GRF files or modify existing ones. GRF is Ragnarok Online's archive format.</p>"
            "<p><b>Use cases:</b> Custom content distribution, modding, repacking assets</p>"
        )
        instructions_label.setWordWrap(True)
        layout.addWidget(instructions_label)

        # GRF File Selection
        file_group = QGroupBox("GRF File")
        file_layout = QGridLayout(file_group)

        file_layout.addWidget(QLabel("GRF Path:"), 0, 0)
        self.grf_editor_path = QLineEdit()
        self.grf_editor_path.setPlaceholderText("Path to GRF file (existing or new)...")
        file_layout.addWidget(self.grf_editor_path, 0, 1)

        browse_grf_btn = QPushButton("Browse")
        browse_grf_btn.clicked.connect(self._browse_grf_editor_file)
        file_layout.addWidget(browse_grf_btn, 0, 2)

        create_new_btn = QPushButton("🆕 Create New GRF")
        create_new_btn.clicked.connect(self._create_new_grf)
        file_layout.addWidget(create_new_btn, 1, 0)

        open_existing_btn = QPushButton("📂 Open Existing GRF")
        open_existing_btn.clicked.connect(self._open_existing_grf)
        file_layout.addWidget(open_existing_btn, 1, 1, 1, 2)

        layout.addWidget(file_group)

        # Splitter for file list and operations
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Current GRF contents
        contents_group = QGroupBox("GRF Contents")
        contents_layout = QVBoxLayout(contents_group)

        self.grf_contents_list = QListWidget()
        contents_layout.addWidget(self.grf_contents_list)

        content_buttons = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._refresh_grf_contents)
        content_buttons.addWidget(refresh_btn)

        remove_file_btn = QPushButton("🗑️ Remove Selected")
        remove_file_btn.clicked.connect(self._remove_from_grf)
        content_buttons.addWidget(remove_file_btn)
        content_buttons.addStretch()

        contents_layout.addLayout(content_buttons)
        splitter.addWidget(contents_group)

        # Right: Add files panel
        add_group = QGroupBox("Add to GRF")
        add_layout = QVBoxLayout(add_group)

        # Add single file
        add_file_group = QGroupBox("Add Single File")
        add_file_layout = QGridLayout(add_file_group)

        add_file_layout.addWidget(QLabel("Local File:"), 0, 0)
        self.add_local_file_path = QLineEdit()
        add_file_layout.addWidget(self.add_local_file_path, 0, 1)

        browse_local_btn = QPushButton("Browse")
        browse_local_btn.clicked.connect(self._browse_local_file)
        add_file_layout.addWidget(browse_local_btn, 0, 2)

        add_file_layout.addWidget(QLabel("GRF Path:"), 1, 0)
        self.add_grf_path = QLineEdit()
        self.add_grf_path.setPlaceholderText("data\\sprite\\custom.spr")
        add_file_layout.addWidget(self.add_grf_path, 1, 1, 1, 2)

        add_single_btn = QPushButton("➕ Add File")
        add_single_btn.clicked.connect(self._add_single_file_to_grf)
        add_file_layout.addWidget(add_single_btn, 2, 0, 1, 3)

        add_layout.addWidget(add_file_group)

        # Add directory
        add_dir_group = QGroupBox("Add Directory")
        add_dir_layout = QGridLayout(add_dir_group)

        add_dir_layout.addWidget(QLabel("Local Directory:"), 0, 0)
        self.add_local_dir_path = QLineEdit()
        add_dir_layout.addWidget(self.add_local_dir_path, 0, 1)

        browse_dir_btn = QPushButton("Browse")
        browse_dir_btn.clicked.connect(self._browse_local_directory)
        add_dir_layout.addWidget(browse_dir_btn, 0, 2)

        add_dir_layout.addWidget(QLabel("GRF Base Path:"), 1, 0)
        self.add_grf_base_path = QLineEdit()
        self.add_grf_base_path.setPlaceholderText("data\\sprite")
        add_dir_layout.addWidget(self.add_grf_base_path, 1, 1, 1, 2)

        recursive_check = QCheckBox("Include subdirectories")
        recursive_check.setChecked(True)
        add_dir_layout.addWidget(recursive_check, 2, 0, 1, 3)
        self.grf_recursive_check = recursive_check

        add_dir_btn = QPushButton("📁 Add Directory")
        add_dir_btn.clicked.connect(self._add_directory_to_grf)
        add_dir_layout.addWidget(add_dir_btn, 3, 0, 1, 3)

        add_layout.addWidget(add_dir_group)
        add_layout.addStretch()

        splitter.addWidget(add_group)
        layout.addWidget(splitter)

        # Save and close buttons
        action_buttons = QHBoxLayout()

        save_grf_btn = QPushButton("💾 Save GRF")
        save_grf_btn.clicked.connect(self._save_grf)
        action_buttons.addWidget(save_grf_btn)

        save_as_btn = QPushButton("💾 Save GRF As...")
        save_as_btn.clicked.connect(self._save_grf_as)
        action_buttons.addWidget(save_as_btn)

        close_grf_btn = QPushButton("❌ Close GRF")
        close_grf_btn.clicked.connect(self._close_grf_editor)
        action_buttons.addWidget(close_grf_btn)

        action_buttons.addStretch()
        layout.addLayout(action_buttons)

        # Status
        self.grf_editor_status = QLabel("No GRF file open")
        self.grf_editor_status.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.grf_editor_status)

        self.tabs.addTab(tab, "📦 GRF Editor")

        # Store GRF editor instance
        self.grf_editor = None

    def _browse_grf_editor_file(self):
        """Browse for GRF file."""
        path, _ = QFileDialog.getSaveFileName(self, "Select GRF File", "", "GRF Files (*.grf)")
        if path:
            self.grf_editor_path.setText(path)

    def _create_new_grf(self):
        """Create a new empty GRF file."""
        from src.extractors.grf_editor import GRFEditor

        path = self.grf_editor_path.text().strip()
        if not path:
            QMessageBox.warning(self, "Error", "Enter a GRF file path first")
            return

        self.grf_editor = GRFEditor()
        if self.grf_editor.create(path):
            self.grf_editor_status.setText(f"New GRF created: {os.path.basename(path)}")
            self.grf_editor_status.setStyleSheet("color: #4caf50; font-weight: bold;")
            self._refresh_grf_contents()
            self._log(f"Created new GRF: {path}")
        else:
            QMessageBox.critical(self, "Error", "Failed to create GRF")

    def _open_existing_grf(self):
        """Open an existing GRF file for editing."""
        from src.extractors.grf_editor import GRFEditor

        path = self.grf_editor_path.text().strip()
        if not path:
            QMessageBox.warning(self, "Error", "Enter a GRF file path first")
            return

        if not os.path.exists(path):
            QMessageBox.warning(self, "Error", f"GRF file not found: {path}")
            return

        self.grf_editor = GRFEditor()
        if self.grf_editor.open(path):
            self.grf_editor_status.setText(f"Opened: {os.path.basename(path)} ({len(self.grf_editor.files)} files)")
            self.grf_editor_status.setStyleSheet("color: #4caf50; font-weight: bold;")
            self._refresh_grf_contents()
            self._log(f"Opened GRF: {path}")
        else:
            QMessageBox.critical(self, "Error", "Failed to open GRF")

    def _refresh_grf_contents(self):
        """Refresh the GRF contents list."""
        self.grf_contents_list.clear()

        if not self.grf_editor:
            return

        files = self.grf_editor.list_files()
        for file_path in sorted(files):
            self.grf_contents_list.addItem(file_path)

        self.grf_editor_status.setText(f"{len(files)} files in GRF")

    def _browse_local_file(self):
        """Browse for local file to add."""
        path, _ = QFileDialog.getOpenFileName(self, "Select File to Add")
        if path:
            self.add_local_file_path.setText(path)

    def _browse_local_directory(self):
        """Browse for local directory to add."""
        path = QFileDialog.getExistingDirectory(self, "Select Directory to Add")
        if path:
            self.add_local_dir_path.setText(path)

    def _add_single_file_to_grf(self):
        """Add a single file to the GRF."""
        if not self.grf_editor:
            QMessageBox.warning(self, "Error", "Create or open a GRF first")
            return

        local_path = self.add_local_file_path.text().strip()
        grf_path = self.add_grf_path.text().strip()

        if not local_path or not grf_path:
            QMessageBox.warning(self, "Error", "Enter both local and GRF paths")
            return

        if self.grf_editor.add_file(local_path, grf_path):
            self._refresh_grf_contents()
            self.grf_editor_status.setText("File added (not saved)")
            self.grf_editor_status.setStyleSheet("color: #ff9800; font-weight: bold;")
            self._log(f"Added: {grf_path}")
        else:
            QMessageBox.critical(self, "Error", "Failed to add file")

    def _add_directory_to_grf(self):
        """Add an entire directory to the GRF."""
        if not self.grf_editor:
            QMessageBox.warning(self, "Error", "Create or open a GRF first")
            return

        local_dir = self.add_local_dir_path.text().strip()
        grf_base = self.add_grf_base_path.text().strip()

        if not local_dir or not grf_base:
            QMessageBox.warning(self, "Error", "Enter both local directory and GRF base path")
            return

        recursive = self.grf_recursive_check.isChecked()
        count = self.grf_editor.add_directory(local_dir, grf_base, recursive=recursive)

        if count > 0:
            self._refresh_grf_contents()
            self.grf_editor_status.setText(f"Added {count} files (not saved)")
            self.grf_editor_status.setStyleSheet("color: #ff9800; font-weight: bold;")
            self._log(f"Added directory: {count} files")
        else:
            QMessageBox.warning(self, "Warning", "No files were added")

    def _remove_from_grf(self):
        """Remove selected file from GRF."""
        if not self.grf_editor:
            return

        selected = self.grf_contents_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "Error", "Select a file to remove")
            return

        file_path = selected.text()

        if self.grf_editor.remove_file(file_path):
            self._refresh_grf_contents()
            self.grf_editor_status.setText("File removed (not saved)")
            self.grf_editor_status.setStyleSheet("color: #ff9800; font-weight: bold;")
            self._log(f"Removed: {file_path}")

    def _save_grf(self):
        """Save the GRF to disk."""
        if not self.grf_editor:
            QMessageBox.warning(self, "Error", "No GRF file open")
            return

        self._log("Saving GRF...")
        if self.grf_editor.save():
            self.grf_editor_status.setText("GRF saved successfully")
            self.grf_editor_status.setStyleSheet("color: #4caf50; font-weight: bold;")
            QMessageBox.information(self, "Success", "GRF saved successfully")
        else:
            QMessageBox.critical(self, "Error", "Failed to save GRF")

    def _save_grf_as(self):
        """Save the GRF to a new location."""
        if not self.grf_editor:
            QMessageBox.warning(self, "Error", "No GRF file open")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save GRF As", "", "GRF Files (*.grf)")
        if path:
            if self.grf_editor.save(path):
                self.grf_editor_path.setText(path)
                self.grf_editor_status.setText(f"GRF saved: {os.path.basename(path)}")
                self.grf_editor_status.setStyleSheet("color: #4caf50; font-weight: bold;")
                self._log(f"Saved GRF as: {path}")
                QMessageBox.information(self, "Success", "GRF saved successfully")
            else:
                QMessageBox.critical(self, "Error", "Failed to save GRF")

    def _close_grf_editor(self):
        """Close the current GRF file."""
        if self.grf_editor:
            self.grf_editor.close()
            self.grf_editor = None
            self.grf_contents_list.clear()
            self.grf_editor_status.setText("GRF closed")
            self.grf_editor_status.setStyleSheet("color: #888; font-style: italic;")
            self._log("GRF editor closed")

    def _create_settings_tab(self):
        """Create Settings tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Paths
        paths_group = QGroupBox("Paths")
        paths_layout = QFormLayout(paths_group)
        
        self.default_output = QLineEdit()
        self.default_output.setPlaceholderText("C:\\Extracted\\Assets")
        paths_layout.addRow("Default Output:", self.default_output)
        
        layout.addWidget(paths_group)
        
        # Info
        info_group = QGroupBox("About")
        info_layout = QVBoxLayout(info_group)
        info_layout.addWidget(QLabel("Asset Harvester v1.0.0"))
        info_layout.addWidget(QLabel("Universal Private Server Asset Extraction Tool"))
        info_layout.addWidget(QLabel(""))
        info_layout.addWidget(QLabel("Supported formats: GRF, VFS, PAK, and 700+ via QuickBMS"))
        
        layout.addWidget(info_group)
        layout.addStretch()
        
        self.tabs.addTab(tab, "⚙️ Settings")
    
    # ==========================================================================
    # DATA LOADING
    # ==========================================================================
    
    def _load_data(self):
        """Load all data from database."""
        self._load_games()
        self._load_servers()
    
    def _load_games(self):
        """Load games list."""
        # Clear
        self.game_combo.clear()
        self.games_table.setRowCount(0)
        self.games = []
        
        if self.db:
            try:
                db_games = self.db.get_all_games()
                for g in db_games:
                    self.games.append((g.id, g.name, g.archive_format, g.vanilla_path or ""))
            except:
                pass
        
        # Add default games if empty
        if not self.games:
            self.games = [
                (1, "Ragnarok Online", "grf", ""),
                (2, "ROSE Online", "vfs", ""),
                (3, "RF Online", "pak", "")
            ]
        
        # Populate combo
        for gid, name, fmt, vpath in self.games:
            self.game_combo.addItem(f"{name} ({fmt.upper()})", gid)
        
        # Populate table
        self.games_table.setRowCount(len(self.games))
        for i, (gid, name, fmt, vpath) in enumerate(self.games):
            self.games_table.setItem(i, 0, QTableWidgetItem(name))
            self.games_table.setItem(i, 1, QTableWidgetItem(fmt.upper()))
            self.games_table.setItem(i, 2, QTableWidgetItem(vpath or "Not set"))
            self.games_table.setItem(i, 3, QTableWidgetItem("❌ Not scanned"))
    
    def _load_servers(self):
        """Load servers list."""
        self.servers_table.setRowCount(0)
        self.servers = []

        if self.db:
            try:
                db_servers = self.db.get_all_servers()
                for s in db_servers:
                    game = self.db.get_game(s.game_id)
                    # Get client path from latest client if exists
                    client_path = ""
                    if s.clients:
                        client_path = s.clients[-1].path or ""
                    self.servers.append({
                        'id': s.id,
                        'name': s.name,
                        'game': game.name if game else "Unknown",
                        'game_id': s.game_id,
                        'path': client_path,
                        'website': s.website or ""
                    })
            except:
                pass

        self.servers_table.setRowCount(len(self.servers))
        for i, s in enumerate(self.servers):
            self.servers_table.setItem(i, 0, QTableWidgetItem(s['name']))
            self.servers_table.setItem(i, 1, QTableWidgetItem(s['game']))
            self.servers_table.setItem(i, 2, QTableWidgetItem(s['path']))
            self.servers_table.setItem(i, 3, QTableWidgetItem(s['website']))
    
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    
    def _browse_path(self, line_edit: QLineEdit):
        """Browse for a folder path."""
        path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if path:
            line_edit.setText(path)
    
    def _on_game_changed(self):
        """Handle game selection change."""
        idx = self.game_combo.currentIndex()
        if idx >= 0 and idx < len(self.games):
            gid, name, fmt, vpath = self.games[idx]
            if vpath:
                self.vanilla_path.setText(vpath)
            
            # Update baseline status
            if self.baseline:
                self.baseline_status.setText(f"✅ Baseline loaded: {len(self.baseline)} files")
                self.baseline_status.setStyleSheet("color: #4caf50;")
            else:
                self.baseline_status.setText("⚠️ No baseline loaded - scan vanilla first!")
                self.baseline_status.setStyleSheet("color: #ff9800;")
    
    def _on_add_game(self):
        """Add a new game."""
        dialog = AddGameDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data['name']:
                # Add to database
                if self.db:
                    try:
                        self.db.add_game(
                            name=data['name'],
                            archive_format=data['format'],
                            vanilla_path=data['vanilla_path']
                        )
                    except:
                        pass
                
                # Add to local list
                new_id = max(g[0] for g in self.games) + 1 if self.games else 1
                self.games.append((new_id, data['name'], data['format'], data['vanilla_path']))
                
                self._load_games()
                self._log(f"Added game: {data['name']}")
    
    def _on_add_server(self):
        """Add a new server."""
        if not self.games:
            QMessageBox.warning(self, "Error", "Add a game first!")
            return

        game_list = [(g[0], g[1]) for g in self.games]
        dialog = AddServerDialog(self, game_list)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data['name']:
                # Add to database
                if self.db:
                    try:
                        server = self.db.add_server(
                            name=data['name'],
                            game_id=data['game_id'],
                            website=data.get('website', '')
                        )
                        # If client path provided, create a client entry
                        if data.get('client_path'):
                            self.db.add_client(server.id, data['client_path'])
                    except:
                        pass

                self._load_servers()
                self._log(f"Added server: {data['name']}")

                # Auto-fill the server path
                if data.get('client_path'):
                    self.server_path.setText(data['client_path'])
    
    def _on_remove_game(self):
        """Remove selected game."""
        row = self.games_table.currentRow()
        if row >= 0 and row < len(self.games):
            gid, name, _, _ = self.games[row]
            reply = QMessageBox.question(self, "Confirm", f"Remove game '{name}'?")
            if reply == QMessageBox.StandardButton.Yes:
                # Delete from database
                if self.db:
                    try:
                        self.db.delete_game(gid)
                    except:
                        pass
                # Remove from local list
                del self.games[row]
                self._load_games()
                self._log(f"Removed game: {name}")
    
    def _on_remove_server(self):
        """Remove selected server."""
        row = self.servers_table.currentRow()
        if row >= 0 and row < len(self.servers):
            server = self.servers[row]
            reply = QMessageBox.question(self, "Confirm", f"Remove server '{server['name']}'?")
            if reply == QMessageBox.StandardButton.Yes:
                # Delete from database
                if self.db:
                    try:
                        self.db.delete_server(server['id'])
                    except:
                        pass
                # Remove from local list
                del self.servers[row]
                self._load_servers()
                self._log(f"Removed server: {server['name']}")
    
    def _on_scan_baseline(self):
        """Scan vanilla baseline."""
        path = self.vanilla_path.text().strip()
        if not path:
            QMessageBox.warning(self, "Error", "Select a vanilla client folder first!")
            return
        
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Error", f"Folder not found: {path}")
            return
        
        # Get current game format
        idx = self.game_combo.currentIndex()
        game_format = self.games[idx][2] if idx >= 0 else "grf"
        
        self._start_worker("scan_baseline", path=path, format=game_format)
    
    def _on_extract_all(self):
        """Extract all files."""
        source = self.server_path.text().strip()
        output = self.output_path.text().strip()
        
        if not source:
            QMessageBox.warning(self, "Error", "Select a server client folder!")
            return
        if not output:
            QMessageBox.warning(self, "Error", "Select an output folder!")
            return
        
        idx = self.game_combo.currentIndex()
        game_format = self.games[idx][2] if idx >= 0 else "grf"
        
        self._start_worker("extract", source=source, output=output, format=game_format)
    
    def _on_compare(self):
        """Compare to vanilla baseline."""
        source = self.server_path.text().strip()
        
        if not source:
            QMessageBox.warning(self, "Error", "Select a server client folder!")
            return
        
        if not self.baseline:
            reply = QMessageBox.question(
                self, "No Baseline",
                "No baseline loaded. Scan vanilla first?\n\nWithout a baseline, ALL files will be marked as 'new'.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_scan_baseline()
                return
        
        idx = self.game_combo.currentIndex()
        game_format = self.games[idx][2] if idx >= 0 else "grf"
        
        self._start_worker("compare", source=source, baseline=self.baseline, format=game_format)
    
    def _on_export_custom(self):
        """Export only custom files."""
        source = self.server_path.text().strip()
        output = self.output_path.text().strip()
        
        if not source:
            QMessageBox.warning(self, "Error", "Select a server client folder!")
            return
        if not output:
            QMessageBox.warning(self, "Error", "Select an output folder!")
            return
        
        if not self.comparison:
            QMessageBox.warning(self, "Error", "Run comparison first to identify custom files!")
            return
        
        # Get custom files (modified + new)
        custom_files = self.comparison['results']['modified'] + self.comparison['results']['new']
        
        if not custom_files:
            QMessageBox.information(self, "Info", "No custom files found!")
            return
        
        idx = self.game_combo.currentIndex()
        game_format = self.games[idx][2] if idx >= 0 else "grf"
        
        # Create subfolder for custom content
        custom_output = os.path.join(output, "CUSTOM_CONTENT")
        
        self._start_worker("export_custom", 
                          source=source, 
                          output=custom_output, 
                          custom_files=custom_files,
                          format=game_format)
    
    def _on_quick_extract(self):
        """Quick extract - scan baseline, compare, and export custom in one go."""
        self.tabs.setCurrentIndex(0)  # Switch to Extract tab
        QMessageBox.information(
            self, "Quick Extract",
            "Quick Extract will:\n\n"
            "1. Scan your vanilla baseline (if not already done)\n"
            "2. Compare the private server client\n"
            "3. Export only custom/modified files\n\n"
            "Use the Extract tab to run each step."
        )
    
    def _on_cancel(self):
        """Cancel current operation."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self._log("Cancelling operation...")
            # Don't reset UI immediately - let worker finish and handle cleanup
        else:
            self._log("No operation to cancel")
    
    # ==========================================================================
    # WORKER MANAGEMENT
    # ==========================================================================
    
    def _start_worker(self, operation: str, **kwargs):
        """Start a background worker."""
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Busy", "An operation is already running!")
            return
        
        self.worker = ExtractWorker(operation, **kwargs)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._log)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.error.connect(self._on_worker_error)
        
        # UI state
        self._set_busy(True)
        self.worker.start()
    
    def _set_busy(self, busy: bool):
        """Set UI busy state."""
        self.progress_bar.setVisible(busy)
        self.cancel_btn.setVisible(busy)
        
        self.scan_baseline_btn.setEnabled(not busy)
        self.extract_all_btn.setEnabled(not busy)
        self.compare_btn.setEnabled(not busy)
        self.export_custom_btn.setEnabled(not busy)
    
    def _on_progress(self, current: int, total: int, message: str):
        """Handle progress update."""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(message)
    
    def _on_worker_finished(self, result: dict):
        """Handle worker completion."""
        # Check if operation was cancelled
        if result and result.get('cancelled', False):
            self._log("\n⚠️ Operation cancelled by user")
            self._set_busy(False)
            return
        
        self._set_busy(False)
        
        result_type = result.get('type')
        
        if result_type == 'baseline':
            self.baseline = result.get('hashes', {})
            count = result.get('total', 0)
            self.baseline_status.setText(f"✅ Baseline: {count} files")
            self.baseline_status.setStyleSheet("color: #4caf50;")
            self._log(f"\n✅ Baseline ready: {count} files hashed")
            
            # Update games table
            row = self.game_combo.currentIndex()
            if row >= 0:
                self.games_table.setItem(row, 3, QTableWidgetItem(f"✅ {count} files"))
            
            # Update Character Designer with new baseline
            if self.character_designer and self.character_designer.custom_detector:
                # Convert baseline format: {path: {hash, size, archive}} -> {path: hash}
                baseline_hashes = {path: data.get('hash', '') for path, data in self.baseline.items()}
                self.character_designer.custom_detector.set_baseline(baseline_hashes)
                self._log("Character Designer: Baseline updated")
        
        elif result_type == 'compare':
            self.comparison = result
            results = result.get('results', {})
            
            # Update results tab
            identical = len(results.get('identical', []))
            modified = len(results.get('modified', []))
            new = len(results.get('new', []))
            custom = modified + new
            
            self.identical_label.setText(f"Identical: {identical}")
            self.modified_label.setText(f"Modified: {modified}")
            self.new_label.setText(f"New: {new}")
            self.custom_total_label.setText(f"⭐ CUSTOM TOTAL: {custom}")
            
            # Populate lists
            self.modified_list.clear()
            self.new_list.clear()
            
            for f in results.get('modified', [])[:1000]:  # Limit for performance
                self.modified_list.addItem(f)
            
            for f in results.get('new', [])[:1000]:
                self.new_list.addItem(f)
            
            # Switch to results tab
            self.tabs.setCurrentIndex(2)
            
            self._log(f"\n✅ Comparison complete! {custom} custom files found")
        
        elif result_type == 'extract':
            extracted = result.get('extracted', 0)
            self._log(f"\n✅ Extraction complete! {extracted} files extracted")
            QMessageBox.information(self, "Complete", f"Extracted {extracted} files!")
        
        elif result_type == 'export_custom':
            exported = result.get('exported', 0)
            self._log(f"\n✅ Export complete! {exported} custom files exported")
            QMessageBox.information(self, "Complete", f"Exported {exported} custom files!")
    
    def _on_worker_error(self, error: str):
        """Handle worker error."""
        self._set_busy(False)
        self._log(f"\n❌ ERROR: {error}")
        QMessageBox.critical(self, "Error", error)
    
    # ==========================================================================
    # LOGGING
    # ==========================================================================
    
    def _log(self, message: str):
        """Add message to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        self.status_label.setText(message[:100])
        
        # Auto-scroll
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


# ==============================================================================
# ENTRY POINT
# ==============================================================================
def run_gui():
    """Run the Asset Harvester GUI."""
    if not PYQT_AVAILABLE:
        print("[ERROR] PyQt6 required. Install: pip install PyQt6")
        return 1
    
    app = QApplication(sys.argv)
    app.setApplicationName("Asset Harvester")
    app.setApplicationVersion("1.0.0")
    
    window = MainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(run_gui())
