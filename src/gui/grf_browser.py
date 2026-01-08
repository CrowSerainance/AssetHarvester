# ==============================================================================
# GRF BROWSER WIDGET MODULE
# ==============================================================================
# PyQt6 widget for browsing GRF archive contents.
#
# Features:
#   - Tree view showing folder structure inside GRF
#   - File list showing files in selected folder
#   - Preview panel for selected file (images, sprites, text)
#   - Search bar with real-time filtering
#   - Extract files/folders to disk
#   - Integration with Character Designer
#
# Usage:
#   browser = GRFBrowserWidget()
#   browser.load_grf("data.grf")
# ==============================================================================

import os
import io
from typing import Optional, List, Dict
from collections import defaultdict

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QGroupBox, QLabel, QPushButton, QLineEdit, QFileDialog,
        QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
        QSplitter, QTextEdit, QMessageBox, QMenu, QProgressDialog,
        QFrame, QScrollArea, QProgressBar, QApplication
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread
    from PyQt6.QtGui import QImage, QPixmap, QPainter, QAction, QIcon
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

# Try to import PIL for image preview
try:
    from PIL import Image, ImageDraw
    from PIL.ImageQt import ImageQt
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    ImageDraw = None

# Import GRF VFS
try:
    from src.extractors.grf_vfs import GRFVirtualFileSystem, GRFFileEntry
    VFS_AVAILABLE = True
except ImportError:
    VFS_AVAILABLE = False
    print("[WARN] GRF VFS not available")

# Import parsers for preview
try:
    from src.parsers.spr_parser import SPRParser
    from src.parsers.act_parser import ACTParser
    PARSERS_AVAILABLE = True
except ImportError:
    PARSERS_AVAILABLE = False


# ==============================================================================
# GRF LOADING WORKER THREAD
# ==============================================================================

class GRFLoadingWorker(QThread):
    """Worker thread for loading GRF files asynchronously."""
    
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, grf_path: str, vfs: 'GRFVirtualFileSystem', priority: int):
        super().__init__()
        self.grf_path = grf_path
        self.vfs = vfs
        self.priority = priority
        self._cancelled = False
    
    def cancel(self):
        """Cancel the loading operation."""
        self._cancelled = True
    
    def run(self):
        """Load GRF file in background thread."""
        try:
            self.progress.emit(0, 100, f"Loading GRF: {os.path.basename(self.grf_path)}")
            
            if self._cancelled:
                self.finished.emit(False, "Cancelled")
                return
            
            # Load GRF (this may take time for large files)
            success = self.vfs.load_grf(self.grf_path, self.priority)
            
            if self._cancelled:
                self.finished.emit(False, "Cancelled")
                return
            
            if success:
                file_count = len(self.vfs._file_index)
                self.finished.emit(True, f"Loaded {file_count:,} files")
            else:
                self.finished.emit(False, "Failed to load GRF file")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished.emit(False, f"Error: {str(e)}")


class GRFIndexingWorker(QThread):
    """Worker thread for building GRF file index asynchronously."""
    
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(bool, dict)  # success, index_data
    
    def __init__(self, archive: 'GRFArchive'):
        super().__init__()
        self.archive = archive
        self._cancelled = False
    
    def cancel(self):
        """Cancel the indexing operation."""
        self._cancelled = True
    
    def run(self):
        """Build file index in background thread."""
        try:
            # Get entries from archive
            entries = list(self.archive.list_entries())
            total = len(entries)
            
            if total == 0:
                self.finished.emit(False, {})
                return
            
            # Build index with progress updates
            index = {}
            processed = 0
            progress_interval = max(1, total // 100)  # Update every 1%
            
            for entry in entries:
                if self._cancelled:
                    self.finished.emit(False, {})
                    return
                
                try:
                    normalized_path = entry.path
                    # Higher priority overrides lower
                    if normalized_path not in index:
                        index[normalized_path] = entry
                    elif entry.priority > index[normalized_path].priority:
                        index[normalized_path] = entry
                    
                    processed += 1
                    
                    # Emit progress every N entries
                    if processed % progress_interval == 0 or processed == total:
                        percent = int((processed / total) * 100)
                        self.progress.emit(processed, total, f"Indexing: {processed:,}/{total:,} files ({percent}%)")
                        
                except Exception as e:
                    # Skip invalid entry
                    continue
            
            if self._cancelled:
                self.finished.emit(False, {})
                return
            
            # Return index data for UI thread
            self.finished.emit(True, index)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished.emit(False, {})


# ==============================================================================
# GRF BROWSER WIDGET
# ==============================================================================

class GRFBrowserWidget(QWidget):
    """
    Widget for browsing GRF archive contents.
    
    Provides tree view, file list, preview, and extraction functionality.
    """
    
    file_selected = pyqtSignal(str)  # Emitted when file is selected
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.vfs = None
        self.current_directory = ""
        self._current_file_path = ""
        self.spr_parser = SPRParser() if PARSERS_AVAILABLE else None
        self.act_parser = ACTParser() if PARSERS_AVAILABLE else None
        self._loading_worker = None
        self._indexing_worker = None
        self._tree_build_worker = None
        self._current_archive = None  # Archive being indexed
        self._debug_mode = False  # Debug mode for showing parse failures
        
        self._setup_ui()
        
        # Warn if PIL is not available
        if not PIL_AVAILABLE:
            print("[WARN] Pillow (PIL) not installed - image previews will be disabled")
            print("[INFO] Install Pillow with: pip install Pillow")
    
    def _setup_ui(self):
        """Build the user interface."""
        main_layout = QVBoxLayout(self)
        
        # === TOP BAR: Load GRF and Search ===
        top_bar = QHBoxLayout()
        
        load_btn = QPushButton("📂 Load GRF...")
        load_btn.clicked.connect(self._on_load_grf)
        top_bar.addWidget(load_btn)
        
        add_btn = QPushButton("➕ Add GRF...")
        add_btn.clicked.connect(self._on_add_grf)
        top_bar.addWidget(add_btn)
        
        top_bar.addStretch()
        
        search_label = QLabel("Search:")
        top_bar.addWidget(search_label)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search files...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        top_bar.addWidget(self.search_edit)
        
        # Debug mode toggle
        self.debug_checkbox = QPushButton("🔍 Debug")
        self.debug_checkbox.setCheckable(True)
        self.debug_checkbox.setToolTip("Enable debug mode to show detailed parse errors")
        self.debug_checkbox.toggled.connect(self._on_debug_toggled)
        top_bar.addWidget(self.debug_checkbox)
        
        main_layout.addLayout(top_bar)
        
        # === MAIN SPLITTER: Tree | File List | Preview ===
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # === LEFT: Directory Tree ===
        tree_group = QGroupBox("📁 Folders")
        tree_layout = QVBoxLayout(tree_group)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Directory Structure")
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self.tree.itemExpanded.connect(self._on_tree_item_expanded)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        tree_layout.addWidget(self.tree)
        
        main_splitter.addWidget(tree_group)
        
        # === MIDDLE: File List ===
        files_group = QGroupBox("📄 Files")
        files_layout = QVBoxLayout(files_group)
        
        # File list header
        file_header = QHBoxLayout()
        file_header.addWidget(QLabel("Name"))
        file_header.addStretch()
        file_header.addWidget(QLabel("Size"))
        files_layout.addLayout(file_header)
        
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self._on_file_double_clicked)
        self.file_list.itemSelectionChanged.connect(self._on_file_selection_changed)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._on_file_context_menu)
        files_layout.addWidget(self.file_list)
        
        main_splitter.addWidget(files_group)
        
        # === RIGHT: Preview ===
        preview_group = QGroupBox("👁️ Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_area = QScrollArea()
        self.preview_area.setWidgetResizable(True)
        self.preview_label = QLabel("No file selected")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_area.setWidget(self.preview_label)
        preview_layout.addWidget(self.preview_area)
        
        # File info
        self.file_info = QLabel("")
        self.file_info.setWordWrap(True)
        self.file_info.setStyleSheet("font-family: monospace; font-size: 10pt;")
        preview_layout.addWidget(self.file_info)
        
        main_splitter.addWidget(preview_group)
        
        # Set splitter sizes (40%, 30%, 30%)
        main_splitter.setSizes([400, 300, 400])
        main_layout.addWidget(main_splitter)
        
        # === BOTTOM: Status Bar ===
        status_bar = QHBoxLayout()
        
        self.status_label = QLabel("No GRF loaded")
        status_bar.addWidget(self.status_label)
        
        status_bar.addStretch()
        
        self.stats_label = QLabel("")
        status_bar.addWidget(self.stats_label)
        
        # Progress bar for loading
        self.loading_progress = QProgressBar()
        self.loading_progress.setVisible(False)
        status_bar.addWidget(self.loading_progress)
        
        main_layout.addLayout(status_bar)
    
    def load_grf(self, grf_path: str, priority: int = 0) -> bool:
        """
        Load a GRF file (asynchronously with background indexing).
        
        Args:
            grf_path: Path to GRF file
            priority: Priority level (higher = overrides lower priority GRFs)
            
        Returns:
            True if load started successfully, False otherwise
        """
        if not VFS_AVAILABLE:
            QMessageBox.warning(self, "Error", "GRF VFS not available")
            return False
        
        if not os.path.isfile(grf_path):
            QMessageBox.warning(self, "Error", f"GRF file not found: {grf_path}")
            return False
        
        # Cancel any existing workers
        if self._loading_worker and self._loading_worker.isRunning():
            self._loading_worker.cancel()
            self._loading_worker.wait(1000)  # Wait up to 1 second
        
        if self._indexing_worker and self._indexing_worker.isRunning():
            self._indexing_worker.cancel()
            self._indexing_worker.wait(1000)
        
        # Create VFS if needed
        if self.vfs is None:
            self.vfs = GRFVirtualFileSystem(cache_size_mb=100)
        
        # Show loading UI
        self.loading_progress.setVisible(True)
        self.loading_progress.setRange(0, 0)  # Indeterminate
        self.status_label.setText(f"Opening GRF: {os.path.basename(grf_path)}...")
        
        # Disable buttons during loading
        for widget in self.findChildren(QPushButton):
            if widget.text() in ("📂 Load GRF...", "➕ Add GRF..."):
                widget.setEnabled(False)
        
        # Load GRF archive synchronously (quick - just opens file)
        # Indexing will happen in background
        from src.extractors.grf_vfs import GRFArchive
        archive = GRFArchive(grf_path, priority)
        if not archive.open():
            QMessageBox.warning(self, "Error", f"Failed to open GRF file: {grf_path}")
            self.loading_progress.setVisible(False)
            for widget in self.findChildren(QPushButton):
                if widget.text() in ("📂 Load GRF...", "➕ Add GRF..."):
                    widget.setEnabled(True)
            return False
        
        # Add to archives list
        self.vfs._archives.append(archive)
        self.vfs._archives.sort(key=lambda a: a.priority)
        self._current_archive = archive
        
        # Start background indexing
        self.status_label.setText(f"Indexing GRF: {os.path.basename(grf_path)}...")
        self._indexing_worker = GRFIndexingWorker(archive)
        self._indexing_worker.progress.connect(self._on_indexing_progress)
        self._indexing_worker.finished.connect(lambda success, index: self._on_indexing_finished(success, index, grf_path, priority))
        self._indexing_worker.start()
        
        return True
    
    def _on_indexing_progress(self, current: int, total: int, message: str):
        """Handle indexing progress update."""
        if total > 0:
            self.loading_progress.setMaximum(total)
            self.loading_progress.setValue(current)
        self.status_label.setText(message)
    
    def _on_indexing_finished(self, success: bool, index: dict, grf_path: str, priority: int):
        """Handle indexing completion."""
        self.loading_progress.setVisible(False)
        
        # Re-enable buttons
        for widget in self.findChildren(QPushButton):
            if widget.text() in ("📂 Load GRF...", "➕ Add GRF..."):
                widget.setEnabled(True)
        
        if success and index:
            # Merge index into VFS
            if self.vfs._file_index:
                # Merge with existing index (higher priority overrides)
                self.vfs.merge_file_index(index)
            else:
                # First GRF - set index directly
                self.vfs.set_file_index(index)
            
            file_count = len(self.vfs._file_index)
            self.status_label.setText(f"Loaded {file_count:,} files")
            
            # Build tree incrementally (lazy loading)
            try:
                self._build_tree_incremental()
                self._update_status()
                QMessageBox.information(self, "Success", f"Loaded: {os.path.basename(grf_path)}\n\n{file_count:,} files indexed")
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Failed to build directory tree:\n{e}")
                self.status_label.setText(f"Error building tree: {e}")
        else:
            self.status_label.setText(f"Failed to index GRF")
            QMessageBox.warning(self, "Error", f"Failed to index GRF:\n{grf_path}\n\nThe file may be corrupted or inaccessible.")
            # Remove archive if indexing failed
            if self._current_archive and self._current_archive in self.vfs._archives:
                self.vfs._archives.remove(self._current_archive)
        
        self._current_archive = None
    
    def _on_load_grf(self):
        """Handle Load GRF button click."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load GRF File", "", "GRF Files (*.grf *.gpf);;All Files (*.*)"
        )
        if path:
            if self.vfs is None:
                self.vfs = GRFVirtualFileSystem(cache_size_mb=100)
            
            self.load_grf(path, priority=0)
            # Loading is async, message will be shown in _on_loading_finished
    
    def _on_add_grf(self):
        """Handle Add GRF button click."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Add GRF File", "", "GRF Files (*.grf *.gpf);;All Files (*.*)"
        )
        if path:
            if self.vfs is None:
                self.vfs = GRFVirtualFileSystem(cache_size_mb=100)
            
            # Calculate priority (number of already loaded GRFs)
            priority = len(self.vfs._archives) if self.vfs else 0
            
            # Load with background indexing (will merge with existing index)
            self.load_grf(path, priority=priority)
    
    def _build_tree_incremental(self):
        """Build directory tree incrementally (only show top level first)."""
        if not self.vfs:
            return
        
        try:
            self.tree.clear()
            self.status_label.setText("Building directory tree...")
            QApplication.processEvents()
            
            # Build top-level directories only (lazy loading)
            top_dirs = set()
            top_files = set()
            
            # Process files in batches to avoid blocking
            file_count = len(self.vfs._file_index)
            processed = 0
            
            # Limit processing for very large GRFs to avoid crashes
            max_process = min(file_count, 500000)  # Process max 500k files at a time
            
            for file_path in list(self.vfs._file_index.keys())[:max_process]:
                processed += 1
                
                # Update status every 5000 files to keep UI responsive
                if processed % 5000 == 0:
                    self.status_label.setText(f"Processing files: {processed:,}/{file_count:,}")
                    QApplication.processEvents()  # Keep UI responsive
                
                # Get top-level item
                if '/' in file_path:
                    parts = file_path.split('/')
                    if parts[0]:
                        top_level = parts[0]
                        top_dirs.add(top_level)
                else:
                    top_files.add(file_path)
            
            # Build root items
            root = self.tree.invisibleRootItem()
            
            # Add directories first
            for dir_name in sorted(top_dirs):
                item = QTreeWidgetItem(root, [f"📁 {dir_name}"])
                item.setData(0, Qt.ItemDataRole.UserRole, dir_name + '/')
                # Add placeholder child to make it expandable
                placeholder = QTreeWidgetItem(item, ["..."])
                placeholder.setData(0, Qt.ItemDataRole.UserRole, None)
            
            # Add root-level files (limit to 100 to avoid clutter)
            for file_name in sorted(top_files)[:100]:
                item = QTreeWidgetItem(root, [f"📄 {file_name}"])
                item.setData(0, Qt.ItemDataRole.UserRole, file_name)
            
            if file_count > max_process:
                self.status_label.setText(f"Loaded {max_process:,}/{file_count:,} files (showing top-level only)")
            else:
                self.status_label.setText(f"Loaded {file_count:,} files")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.status_label.setText(f"Error building tree: {e}")
            QMessageBox.warning(self, "Warning", f"Directory tree partially built:\n{e}\n\nYou can still browse files using search.")
    
    def _build_tree(self):
        """Build directory tree from GRF files (deprecated - use incremental version)."""
        # For backwards compatibility, call incremental version
        self._build_tree_incremental()
    
    def _on_tree_item_expanded(self, item: QTreeWidgetItem):
        """Handle tree item expansion (lazy loading)."""
        dir_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not dir_path or dir_path.endswith('/'):
            # Load children for this directory
            self._load_tree_item_children(item, dir_path)
    
    def _load_tree_item_children(self, parent: QTreeWidgetItem, dir_path: str):
        """Lazy load children of a tree item."""
        if not self.vfs:
            return
        
        try:
            # Remove placeholder
            for i in range(parent.childCount() - 1, -1, -1):
                child = parent.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole) is None:
                    parent.removeChild(child)
            
            # Build children for this directory
            subdirs = set()
            files = []
            
            dir_prefix = dir_path if dir_path.endswith('/') else dir_path + '/'
            
            # Limit files processed to avoid freezing
            processed = 0
            max_files = 10000  # Process max 10k files per directory
            
            for file_path in self.vfs._file_index.keys():
                if not file_path.startswith(dir_prefix):
                    continue
                
                processed += 1
                if processed > max_files:
                    break  # Stop if too many files
                
                # Get relative path
                rel_path = file_path[len(dir_prefix):]
                
                if '/' in rel_path:
                    # Subdirectory
                    parts = rel_path.split('/')
                    if parts[0]:
                        subdir_name = parts[0]
                        subdirs.add((dir_prefix + subdir_name + '/', subdir_name))
                else:
                    # File
                    files.append((rel_path, file_path))
            
            # Add subdirectories
            for subdir_path, subdir_name in sorted(subdirs):
                child = QTreeWidgetItem(parent, [f"📁 {subdir_name}"])
                child.setData(0, Qt.ItemDataRole.UserRole, subdir_path)
                # Add placeholder for lazy loading
                placeholder = QTreeWidgetItem(child, ["..."])
                placeholder.setData(0, Qt.ItemDataRole.UserRole, None)
            
            # Add files (limit display to 5000 files per directory)
            for file_name, file_path in sorted(files, key=lambda x: x[0].lower())[:5000]:
                child = QTreeWidgetItem(parent, [f"📄 {file_name}"])
                child.setData(0, Qt.ItemDataRole.UserRole, file_path)
            
            if len(files) > 5000:
                # Add indicator that more files exist
                more_item = QTreeWidgetItem(parent, [f"... ({len(files) - 5000} more files)"])
                more_item.setData(0, Qt.ItemDataRole.UserRole, None)
                
        except Exception as e:
            # Silently fail - directory might be too large
            pass
    
    def _on_tree_selection_changed(self):
        """Handle tree selection change."""
        selected = self.tree.selectedItems()
        if not selected:
            return
        
        item = selected[0]
        path = item.data(0, Qt.ItemDataRole.UserRole)
        
        if path:
            self.current_directory = path
            self._update_file_list()
    
    def _update_file_list(self):
        """Update file list for current directory."""
        if not self.vfs:
            return
        
        self.file_list.clear()
        
        # Get files in current directory
        files = []
        dir_path = self.current_directory
        
        if not dir_path.endswith('/'):
            dir_path += '/'
        
        for file_path in self.vfs._file_index.keys():
            if file_path.startswith(dir_path):
                # Get relative path
                rel_path = file_path[len(dir_path):]
                # Only show immediate children (not subdirectories)
                if '/' not in rel_path:
                    entry = self.vfs._file_index[file_path]
                    files.append((rel_path, entry))
        
        # Sort files
        files.sort(key=lambda x: x[0].lower())
        
        # Add to list
        for name, entry in files:
            # Format: "filename.ext (24 KB)"
            size_kb = entry.uncompressed_size / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            
            item = QListWidgetItem(f"{name} ({size_str})")
            item.setData(Qt.ItemDataRole.UserRole, entry.path)
            self.file_list.addItem(item)
    
    def _on_file_selection_changed(self):
        """Handle file list selection change."""
        selected = self.file_list.selectedItems()
        if not selected:
            self.preview_label.setText("No file selected")
            self.file_info.setText("")
            return
        
        item = selected[0]
        file_path = item.data(Qt.ItemDataRole.UserRole)
        
        if file_path:
            self._preview_file(file_path)
            self.file_selected.emit(file_path)
    
    def _on_file_double_clicked(self, item: QListWidgetItem):
        """Handle file double-click."""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self._preview_file(file_path)
    
    def _preview_file(self, file_path: str):
        """Preview a file with full error handling."""
        if not self.vfs:
            return
        
        try:
            # Get file info
            entry = self.vfs.get_file_info(file_path)
            if not entry:
                self.preview_label.setText("File not found in GRF index")
                self.file_info.setText("")
                return
            
            # Read file data
            data = self.vfs.read_file(file_path)
            if not data:
                self.preview_label.setText("Failed to read/decompress file\n\n(File may be corrupted or use unsupported compression)")
                # Still show file info
                ext = os.path.splitext(file_path)[1].lower()
                info_text = f"File: {entry.original_path}\n"
                info_text += f"Size: {entry.uncompressed_size:,} bytes\n"
                info_text += f"Compressed: {entry.compressed_size:,} bytes\n"
                info_text += f"Source: {os.path.basename(entry.grf_path)}\n"
                info_text += f"Type: {ext if ext else '(no extension)'}\n"
                info_text += f"Compression: {entry.compression_type}\n"
                info_text += f"Encrypted: {'Yes' if entry.is_encrypted() else 'No'}\n"
                info_text += "\n⚠️ Decompression failed"
                self.file_info.setText(info_text)
                return
            
            # Update file info
            ext = os.path.splitext(file_path)[1].lower()
            info_text = f"File: {entry.original_path}\n"
            info_text += f"Size: {entry.uncompressed_size:,} bytes\n"
            info_text += f"Compressed: {entry.compressed_size:,} bytes\n"
            info_text += f"Source: {os.path.basename(entry.grf_path)}\n"
            info_text += f"Type: {ext if ext else '(no extension)'}\n"
            info_text += f"Compression: {entry.compression_type}\n"
            info_text += f"Encrypted: {'Yes' if entry.is_encrypted() else 'No'}"
            self.file_info.setText(info_text)
            
            # Store current file path
            self._current_file_path = file_path
            
            # Preview based on file type - with individual error handling
            try:
                if ext == '.spr' and PIL_AVAILABLE and self.spr_parser:
                    self._preview_spr(data, file_path)
                elif ext == '.act' and PARSERS_AVAILABLE and self.act_parser:
                    self._preview_act(data, file_path)
                elif ext in ('.bmp', '.jpg', '.jpeg', '.png', '.tga') and PIL_AVAILABLE:
                    self._preview_image(data)
                elif ext in ('.txt', '.xml', '.lua', '.lub', '.dat', '.ini', '.cfg'):
                    self._preview_text(data)
                elif ext in ('.gat', '.gnd', '.rsw', '.imf', '.rsm', '.str', '.pal'):
                    self._preview_map_file(data, file_path, ext)
                elif ext in ('.wav', '.mp3', '.ogg'):
                    self._preview_audio_info(data, ext)
                else:
                    # Unknown type - show hex
                    self._preview_hex(data)
            except Exception as preview_error:
                # If specific preview fails, fall back to hex
                error_msg = f"Preview failed for {ext}:\n{str(preview_error)}\n\n"
                error_msg += "Falling back to hex view:\n\n"
                self.preview_label.setText(error_msg)
                try:
                    self._preview_hex(data)
                except:
                    self.preview_label.setText(f"Hex view also failed:\n{str(preview_error)}")
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.preview_label.setText(f"Error loading file:\n{str(e)}")
            self.file_info.setText("Error - see preview for details")
    
    def _preview_spr(self, data: bytes, file_path: str = ""):
        """Preview SPR sprite file with enhanced error handling."""
        # Check PIL availability
        if not PIL_AVAILABLE:
            error_msg = "⚠️ Pillow (PIL) not installed\n\n"
            error_msg += "Image preview is disabled.\n"
            error_msg += "Install Pillow with: pip install Pillow\n\n"
            error_msg += "Showing hex dump instead:"
            self.preview_label.setText(error_msg)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self._preview_hex(data)
            return
        
        if not self.spr_parser:
            error_msg = "⚠️ SPR Parser not available\n\n"
            error_msg += "SPR parsing is disabled.\n\n"
            error_msg += "Showing hex dump instead:"
            self.preview_label.setText(error_msg)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self._preview_hex(data)
            return
        
        try:
            sprite = self.spr_parser.load_from_bytes(data)
            
            # Handle parse failure
            if sprite is None:
                error_msg = "❌ SPR Parse Failed\n\n"
                error_msg += "The SPR file could not be parsed.\n"
                error_msg += "Possible reasons:\n"
                error_msg += "  • File is corrupted\n"
                error_msg += "  • Invalid format or version\n"
                error_msg += "  • Data is truncated or incomplete\n"
                
                if self._debug_mode:
                    import traceback
                    error_msg += f"\n\nDebug Info:\n{traceback.format_exc()}"
                else:
                    error_msg += "\n\n(Enable debug mode to see detailed error)"
                
                error_msg += "\n\nShowing hex dump:"
                self.preview_label.setText(error_msg)
                self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                self._preview_hex(data)
                return
            
            # Check frame count
            total_frames = sprite.get_total_frames()
            if total_frames == 0:
                error_msg = "❌ SPR has 0 frames\n\n"
                error_msg += "The SPR file was parsed but contains no frames.\n"
                error_msg += "This may indicate:\n"
                error_msg += "  • Empty or incomplete sprite file\n"
                error_msg += "  • Corrupted frame data\n"
                error_msg += "  • Parser read incorrect frame count\n\n"
                error_msg += f"Indexed frames: {sprite.get_indexed_count()}\n"
                error_msg += f"RGBA frames: {sprite.get_rgba_count()}\n\n"
                error_msg += "Showing hex dump:"
                self.preview_label.setText(error_msg)
                self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                self._preview_hex(data)
                return
            
            # Try to render first frame
            try:
                img = sprite.get_frame_image(0)
                if img and PIL_AVAILABLE:
                    self._display_image(img)
                    # Update file info with sprite details
                    info = self.file_info.text()
                    info += f"\n\nSPR Details:\nFrames: {sprite.get_total_frames()}\n"
                    info += f"Indexed: {sprite.get_indexed_count()}\n"
                    info += f"RGBA: {sprite.get_rgba_count()}"
                    self.file_info.setText(info)
                    return
                else:
                    error_msg = f"SPR: {total_frames} frames\n"
                    error_msg += "⚠️ Image rendering failed\n"
                    error_msg += "(Frame 0 could not be converted to image)"
                    self.preview_label.setText(error_msg)
                    self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            except Exception as img_error:
                error_msg = f"SPR: {total_frames} frames\n"
                error_msg += f"⚠️ Failed to render frame 0: {str(img_error)}\n\n"
                error_msg += "Showing hex dump:"
                self.preview_label.setText(error_msg)
                self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                self._preview_hex(data)
                
        except Exception as e:
            import traceback
            error_msg = f"❌ SPR Preview Error:\n{str(e)}\n\n"
            
            if self._debug_mode:
                error_msg += f"Full traceback:\n{traceback.format_exc()}\n\n"
            else:
                error_msg += "(Enable debug mode to see full traceback)\n\n"
            
            error_msg += "Showing hex dump:"
            self.preview_label.setText(error_msg)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self._preview_hex(data)
    
    def _preview_act(self, data: bytes, file_path: str = ""):
        """Preview ACT action file with enhanced error handling."""
        # Check PIL availability
        if not PIL_AVAILABLE:
            error_msg = "⚠️ Pillow (PIL) not installed\n\n"
            error_msg += "Image preview is disabled.\n"
            error_msg += "Install Pillow with: pip install Pillow\n\n"
            error_msg += "Showing text info instead:"
            self.preview_label.setText(error_msg)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            # Fall through to text preview
        
        if not self.act_parser:
            error_msg = "⚠️ ACT Parser not available\n\n"
            error_msg += "ACT parsing is disabled.\n\n"
            error_msg += "Showing hex dump instead:"
            self.preview_label.setText(error_msg)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self._preview_hex(data)
            return
        
        try:
            act = self.act_parser.load_from_bytes(data)
            
            # Handle parse failure
            if act is None:
                error_msg = "❌ ACT Parse Failed\n\n"
                error_msg += "The ACT file could not be parsed.\n"
                error_msg += "Possible reasons:\n"
                error_msg += "  • File is corrupted\n"
                error_msg += "  • Invalid format or version\n"
                error_msg += "  • Data is truncated or incomplete\n"
                
                if self._debug_mode:
                    import traceback
                    error_msg += f"\n\nDebug Info:\n{traceback.format_exc()}"
                else:
                    error_msg += "\n\n(Enable debug mode to see detailed error)"
                
                error_msg += "\n\nShowing hex dump:"
                self.preview_label.setText(error_msg)
                self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                self._preview_hex(data)
                return
            
            # Try to load matching SPR file for visual preview
            spr_path = file_path.replace('.act', '.spr') if file_path else ""
            spr_loaded = False
            spr_error_msg = ""
            
            if not spr_path:
                spr_error_msg = "No file path available to locate SPR file"
            elif not self.vfs:
                spr_error_msg = "GRF VFS not loaded - cannot search for SPR file"
            elif not self.vfs.file_exists(spr_path):
                spr_error_msg = f"Matching SPR file not found in GRF:\n{spr_path}\n\n"
                spr_error_msg += "The ACT file requires a matching .spr file for visual preview.\n"
                spr_error_msg += "Ensure both files are in the same directory."
            elif not self.spr_parser:
                spr_error_msg = "SPR Parser not available"
            else:
                # Try to read SPR file from GRF
                spr_data = self.vfs.read_file(spr_path)
                if not spr_data:
                    spr_error_msg = f"Failed to read/decompress SPR file:\n{spr_path}\n\n"
                    spr_error_msg += "The file exists in GRF but could not be read.\n"
                    spr_error_msg += "Possible reasons:\n"
                    spr_error_msg += "  • File is corrupted\n"
                    spr_error_msg += "  • Unsupported compression/encryption\n"
                    spr_error_msg += "  • Decompression failed"
                else:
                    # Successfully read SPR data, try to parse and render
                    try:
                        sprite = self.spr_parser.load_from_bytes(spr_data)
                        if not sprite or sprite.get_total_frames() == 0:
                            spr_error_msg = f"SPR file parsed but has 0 frames:\n{spr_path}"
                        elif not PIL_AVAILABLE:
                            spr_error_msg = "PIL not available - cannot render image"
                        else:
                            # Find first action with frames
                            action_to_use = None
                            action_idx = 0
                            
                            for i in range(act.get_action_count()):
                                action = act.get_action(i)
                                if action and action.get_frame_count() > 0:
                                    action_to_use = action
                                    action_idx = i
                                    break
                            
                            if not action_to_use:
                                spr_error_msg = "ACT file has no actions with frames"
                            else:
                                # Try to render first frame of the action
                                frame = action_to_use.get_frame(0)
                                if not frame or len(frame.layers) == 0:
                                    spr_error_msg = f"Action {action_idx} has no layers in frame 0"
                                else:
                                    # Get sprite frame from first layer
                                    layer = frame.layers[0]
                                    sprite_idx = layer.sprite_index
                                    if sprite_idx < 0:
                                        spr_error_msg = f"Invalid sprite index: {sprite_idx}"
                                    else:
                                        if layer.sprite_type == 1:
                                            sprite_idx += sprite.get_indexed_count()
                                        
                                        if sprite_idx >= sprite.get_total_frames():
                                            spr_error_msg = f"Sprite index {sprite_idx} out of range (max: {sprite.get_total_frames() - 1})"
                                        else:
                                            try:
                                                img = sprite.get_frame_image(sprite_idx)
                                                if img:
                                                    self._display_image(img)
                                                    # Add ACT info to file info
                                                    info = self.file_info.text()
                                                    info += f"\n\nACT Details:\n"
                                                    info += f"Actions: {act.get_action_count()}\n"
                                                    info += f"Events: {len(act.events)}\n"
                                                    info += f"Action {action_idx}: {action_to_use.get_frame_count()} frames, {len(frame.layers)} layers"
                                                    if action_idx != 0:
                                                        info += f"\n(Using Action {action_idx} - Action 0 has 0 frames)"
                                                    self.file_info.setText(info)
                                                    spr_loaded = True
                                                    return
                                                else:
                                                    spr_error_msg = f"Failed to get image for sprite index {sprite_idx}"
                                            except Exception as img_error:
                                                spr_error_msg = f"Failed to render sprite frame: {str(img_error)}"
                    except Exception as spr_parse_error:
                        spr_error_msg = f"Failed to parse SPR file:\n{str(spr_parse_error)}"
                        if self._debug_mode:
                            import traceback
                            spr_error_msg += f"\n\n{traceback.format_exc()}"
            
            # Fall back to text preview
            info = f"ACT Version: {act.version}\n"
            info += f"Actions: {act.get_action_count()}\n"
            info += f"Events: {len(act.events)}\n\n"
            
            # Try to find first action with frames
            action_with_frames = None
            action_idx = -1
            for i in range(act.get_action_count()):
                action = act.get_action(i)
                if action and action.get_frame_count() > 0:
                    action_with_frames = action
                    action_idx = i
                    break
            
            if action_with_frames:
                frame = action_with_frames.get_frame(0)
                info += f"Action {action_idx}: {action_with_frames.get_frame_count()} frames"
                if frame:
                    info += f", {len(frame.layers)} layers"
            elif act.get_action_count() > 0:
                action = act.get_action(0)
                info += f"Action 0: {action.get_frame_count() if action else 0} frames"
                if action and action.get_frame_count() == 0:
                    info += " (empty)"
            
            # Add SPR loading error message if available
            if spr_error_msg:
                info += f"\n\n⚠️ Visual Preview Unavailable:\n{spr_error_msg}"
            
            self.preview_label.setText(info)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            
        except Exception as e:
            import traceback
            error_msg = f"❌ ACT Preview Error:\n{str(e)}\n\n"
            
            if self._debug_mode:
                error_msg += f"Full traceback:\n{traceback.format_exc()}\n\n"
            else:
                error_msg += "(Enable debug mode to see full traceback)\n\n"
            
            error_msg += "Showing hex dump:"
            self.preview_label.setText(error_msg)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self._preview_hex(data)
    
    def _preview_image(self, data: bytes):
        """Preview image file."""
        try:
            img = Image.open(io.BytesIO(data))
            self._display_image(img)
        except Exception as e:
            self.preview_label.setText(f"Image Preview Error: {e}")
    
    def _preview_text(self, data: bytes):
        """Preview text file."""
        try:
            # Try different encodings
            for encoding in ['utf-8', 'euc-kr', 'latin-1']:
                try:
                    text = data.decode(encoding)
                    # Limit preview size
                    if len(text) > 10000:
                        text = text[:10000] + "\n\n... (truncated)"
                    self.preview_label.setText(text)
                    self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                    return
                except UnicodeDecodeError:
                    continue
            
            # If all encodings fail, show hex
            self._preview_hex(data)
        except Exception as e:
            self.preview_label.setText(f"Text Preview Error: {e}")
    
    def _preview_map_file(self, data: bytes, file_path: str, ext: str):
        """
        Preview map file (.gat, .gnd, .rsw, .imf) with visual rendering.
        
        Attempts to render a visual preview, falls back to text info if parsing fails.
        """
        try:
            # Try to render visual preview
            rendered_img = self._render_map_preview(data, file_path, ext)
            
            if rendered_img and PIL_AVAILABLE:
                # Display rendered image
                self._display_image(rendered_img)
                # Still update file info with metadata
                self._update_map_file_info(data, file_path, ext)
                return
            
            # Fall back to text preview if rendering failed
            self._preview_map_file_text(data, file_path, ext)
            
        except Exception as e:
            # Ultimate fallback - show error and text info
            error_info = f"{ext.upper()} Preview Error:\n{str(e)}\n\n"
            self.preview_label.setText(error_info)
            self._preview_map_file_text(data, file_path, ext)
    
    def _preview_map_file_text(self, data: bytes, file_path: str, ext: str):
        """Text-only preview fallback for map files."""
        try:
            info = f"{ext.upper().replace('.', '')} Map File\n\n"
            info += f"Size: {len(data):,} bytes\n"
            info += f"Path: {file_path}\n\n"
            
            # Parse header for basic info
            import struct
            
            if ext == '.gat' and len(data) >= 14:
                magic = data[0:4]
                if magic == b'GRAT':
                    try:
                        version = struct.unpack('<H', data[4:6])[0]
                        width = struct.unpack('<I', data[6:10])[0]
                        height = struct.unpack('<I', data[10:14])[0]
                        if 0 < width < 10000 and 0 < height < 10000:
                            info += f"Version: {version}\n"
                            info += f"Map Size: {width} x {height} cells\n"
                            info += f"Total Cells: {width * height:,}\n"
                    except struct.error:
                        pass
                else:
                    try:
                        width = struct.unpack('<I', data[0:4])[0]
                        height = struct.unpack('<I', data[4:8])[0]
                        if 0 < width < 10000 and 0 < height < 10000:
                            info += f"Map Size: {width} x {height} cells (legacy)\n"
                    except struct.error:
                        pass
                info += "\nGAT: Ground Altitude Table (terrain walkability)"
                        
            elif ext == '.gnd' and len(data) >= 10:
                magic = data[0:4]
                if magic == b'GRGN':
                    try:
                        version = struct.unpack('<H', data[4:6])[0]
                        info += f"Version: {version}\n"
                    except struct.error:
                        pass
                info += "\nGND: Ground mesh data (textures, surfaces)"
                    
            elif ext == '.rsw' and len(data) >= 8:
                magic = data[0:4]
                if magic == b'GRSW':
                    try:
                        version = struct.unpack('<H', data[4:6])[0]
                        info += f"Version: {version}\n"
                        info += "Contains: Objects, Lights, Sounds, Effects\n"
                    except struct.error:
                        pass
                info += "\nRSW: Resource World (map objects, lighting, sounds)"
                        
            elif ext == '.imf':
                info += "\nIMF: Interface Motion File (UI animations)\n"
                info += "Data preview available via hex view"
            
            info += "\n\n[Right-click → View Hex Dump for raw data]"
            
            self.preview_label.setText(info)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            
        except Exception as e:
            self.preview_label.setText(f"{ext.upper()} Text Preview Error:\n{str(e)}")
    
    def _update_map_file_info(self, data: bytes, file_path: str, ext: str):
        """Update file info panel with map file metadata."""
        try:
            import struct
            entry = self.vfs.get_file_info(file_path)
            if entry:
                info = self.file_info.text()
                info += f"\n\n{ext.upper()} Map Data:"
                
                if ext == '.gat' and len(data) >= 14:
                    magic = data[0:4]
                    if magic == b'GRAT':
                        try:
                            version = struct.unpack('<H', data[4:6])[0]
                            width = struct.unpack('<I', data[6:10])[0]
                            height = struct.unpack('<I', data[10:14])[0]
                            if 0 < width < 10000 and 0 < height < 10000:
                                info += f"\n{width}x{height} cells"
                        except:
                            pass
                
                self.file_info.setText(info)
        except:
            pass  # Ignore errors in metadata update
    
    def _render_map_preview(self, data: bytes, file_path: str, ext: str) -> Optional[Image.Image]:
        """
        Render visual preview for map files.
        
        Args:
            data: Raw map file bytes
            file_path: File path
            ext: File extension (.gat, .gnd, .rsw, .imf)
            
        Returns:
            PIL Image if successful, None otherwise
        """
        if not PIL_AVAILABLE:
            return None
        
        try:
            import struct
            
            if ext == '.gat':
                return self._render_gat_preview(data)
            elif ext == '.gnd':
                return self._render_gnd_preview(data)
            elif ext == '.rsw':
                return self._render_rsw_preview(data)
            elif ext == '.imf':
                return self._render_imf_preview(data)
            
            return None
            
        except Exception as e:
            # Silently fail - will fall back to text preview
            return None
    
    def _render_gat_preview(self, data: bytes) -> Optional[Image.Image]:
        """
        Render GAT (Ground Altitude Table) as walkability/height map.
        
        GAT format:
        - Header: magic (4), version (2), width (4), height (4)
        - Cells: Each cell is 20 bytes: 4 floats (heights at corners), 4 uints (flags)
        """
        try:
            import struct
            
            if len(data) < 14:
                return None
            
            # Parse header
            magic = data[0:4]
            offset = 14 if magic == b'GRAT' else 0
            
            if offset == 0:
                # Legacy format - no magic, just width/height
                if len(data) < 8:
                    return None
                try:
                    width = struct.unpack('<I', data[0:4])[0]
                    height = struct.unpack('<I', data[4:8])[0]
                    offset = 8
                except struct.error:
                    return None
            else:
                try:
                    width = struct.unpack('<I', data[6:10])[0]
                    height = struct.unpack('<I', data[10:14])[0]
                except struct.error:
                    return None
            
            # Validate dimensions
            if width <= 0 or height <= 0 or width > 1000 or height > 1000:
                # Too large for preview, or invalid
                return None
            
            # Each cell is 20 bytes (4 floats + 4 uints)
            cell_size = 20
            expected_size = offset + (width * height * cell_size)
            
            if len(data) < expected_size:
                # Data truncated, but try to render what we have
                available_cells = (len(data) - offset) // cell_size
                if available_cells == 0:
                    return None
            
            # Create preview image (limit to 512x512 for performance)
            preview_scale = min(1.0, 512.0 / max(width, height))
            img_width = max(1, int(width * preview_scale))
            img_height = max(1, int(height * preview_scale))
            
            img = Image.new('RGB', (img_width, img_height), color=(128, 128, 128))
            pixels = img.load()
            
            # Sample cells for preview (every Nth cell based on scale)
            cell_stride = max(1, int(1.0 / preview_scale))
            
            for y in range(0, height, cell_stride):
                for x in range(0, width, cell_stride):
                    cell_offset = offset + (y * width + x) * cell_size
                    
                    if cell_offset + 20 > len(data):
                        continue
                    
                    try:
                        # Read heights at 4 corners (float32 each)
                        h1 = struct.unpack('<f', data[cell_offset:cell_offset+4])[0]
                        h2 = struct.unpack('<f', data[cell_offset+4:cell_offset+8])[0]
                        h3 = struct.unpack('<f', data[cell_offset+8:cell_offset+12])[0]
                        h4 = struct.unpack('<f', data[cell_offset+12:cell_offset+16])[0]
                        
                        # Read walkability flags (4 bytes)
                        flags = struct.unpack('<I', data[cell_offset+16:cell_offset+20])[0]
                        
                        # Average height for visualization
                        avg_height = (h1 + h2 + h3 + h4) / 4.0
                        
                        # Normalize height to 0-255 range (assuming reasonable terrain heights)
                        # Ragnarok maps typically range from -100 to 100
                        height_normalized = max(0, min(255, int((avg_height + 100) * 255 / 200)))
                        
                        # Check walkability (bit 0 = walkable)
                        walkable = (flags & 0x01) != 0
                        
                        # Color: green for walkable, red for unwalkable, brightness = height
                        if walkable:
                            r = 0
                            g = height_normalized
                            b = 0
                        else:
                            r = height_normalized
                            g = 0
                            b = 0
                        
                        # Draw pixel(s) in preview
                        px = int(x * preview_scale)
                        py = int(y * preview_scale)
                        
                        if px < img_width and py < img_height:
                            pixels[px, py] = (r, g, b)
                            
                            # Fill surrounding pixels if downscaled
                            for dy in range(max(0, py-1), min(img_height, py+2)):
                                for dx in range(max(0, px-1), min(img_width, px+2)):
                                    pixels[dx, dy] = (r, g, b)
                                    
                    except (struct.error, ValueError, IndexError):
                        continue
            
            return img
            
        except Exception:
            return None
    
    def _render_gnd_preview(self, data: bytes) -> Optional[Image.Image]:
        """
        Render GND (Ground) as texture/height approximation.
        
        GND format is complex, we'll just show a basic visualization.
        """
        try:
            if len(data) < 20:
                return None
            
            import struct
            
            magic = data[0:4]
            if magic != b'GRGN':
                return None
            
            # GND has version, dimensions, and texture data
            # Simplified: create a colored placeholder showing we have GND data
            # In a full implementation, you'd parse the actual texture/height data
            
            # Create a simple colored rectangle as placeholder
            img = Image.new('RGB', (400, 300), color=(100, 150, 100))
            
            # Draw some pattern to indicate it's GND data
            if ImageDraw:
                draw = ImageDraw.Draw(img)
            else:
                return img
            
            # Draw grid pattern
            for i in range(0, 400, 20):
                draw.line([(i, 0), (i, 300)], fill=(80, 120, 80), width=1)
            for i in range(0, 300, 20):
                draw.line([(0, i), (400, i)], fill=(80, 120, 80), width=1)
            
            # Add label
            draw.text((10, 10), "GND Ground Mesh", fill=(255, 255, 255))
            draw.text((10, 30), "(Texture/Heightmap data)", fill=(200, 200, 200))
            
            return img
            
        except Exception:
            return None
    
    def _render_rsw_preview(self, data: bytes) -> Optional[Image.Image]:
        """
        Render RSW (Resource World) showing object placements or map bounds.
        
        RSW contains map metadata, objects, lights, etc.
        We'll create a simple visualization.
        """
        try:
            if len(data) < 20:
                return None
            
            import struct
            
            magic = data[0:4]
            if magic != b'GRSW':
                return None
            
            # Create a simple visualization
            img = Image.new('RGB', (400, 300), color=(50, 50, 80))
            
            if not ImageDraw:
                return img
            
            draw = ImageDraw.Draw(img)
            
            # Draw map bounds representation
            bounds_color = (100, 150, 255)
            draw.rectangle([50, 50, 350, 250], outline=bounds_color, width=2)
            
            # Try to extract basic info and show as text
            try:
                version = struct.unpack('<H', data[4:6])[0]
                draw.text((60, 60), f"RSW Version {version}", fill=(255, 255, 255))
                draw.text((60, 80), "Map Objects & Lighting", fill=(200, 200, 200))
            except:
                draw.text((60, 60), "RSW Resource World", fill=(255, 255, 255))
            
            # Draw some placeholder "objects" as dots
            for x, y in [(150, 120), (200, 150), (250, 180), (180, 200)]:
                draw.ellipse([x-5, y-5, x+5, y+5], fill=(255, 200, 100))
            
            return img
            
        except Exception:
            return None
    
    def _render_imf_preview(self, data: bytes) -> Optional[Image.Image]:
        """
        Render IMF (Interface Motion File) as a placeholder.
        
        IMF files are UI animations - we'll show a simple placeholder.
        """
        try:
            # Create placeholder image
            img = Image.new('RGB', (300, 200), color=(60, 60, 60))
            
            if not ImageDraw:
                return img
            
            draw = ImageDraw.Draw(img)
            
            draw.text((20, 20), "IMF Interface Motion", fill=(255, 255, 255))
            draw.text((20, 45), "UI Animation File", fill=(200, 200, 200))
            draw.text((20, 70), "(Preview not available)", fill=(150, 150, 150))
            
            return img
            
        except Exception:
            return None
    
    def _preview_hex(self, data: bytes):
        """Preview file as hex dump."""
        try:
            # Show first 256 bytes as hex
            preview_size = min(256, len(data))
            preview_data = data[:preview_size]
            
            hex_lines = []
            for i in range(0, preview_size, 16):
                chunk = preview_data[i:i+16]
                hex_str = ' '.join(f'{b:02x}' for b in chunk)
                ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                hex_lines.append(f"{i:04x}: {hex_str:<48} {ascii_str}")
            
            if len(data) > preview_size:
                hex_lines.append(f"\n... ({len(data) - preview_size:,} more bytes)")
            
            self.preview_label.setText('\n'.join(hex_lines))
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.preview_label.setFont(self.font())
        except Exception as e:
            self.preview_label.setText(f"Hex view error: {e}")
    
    def _preview_audio_info(self, data: bytes, ext: str):
        """Preview audio file info (without playing)."""
        try:
            info = f"Audio File ({ext.upper()})\n\n"
            info += f"Size: {len(data):,} bytes\n"
            
            if ext == '.wav' and len(data) >= 44:
                try:
                    import struct
                    # WAV header parsing
                    if data[0:4] == b'RIFF' and data[8:12] == b'WAVE':
                        try:
                            channels = struct.unpack('<H', data[22:24])[0]
                            sample_rate = struct.unpack('<I', data[24:28])[0]
                            bits = struct.unpack('<H', data[34:36])[0]
                            
                            # Validate reasonable values
                            if 1 <= channels <= 8 and 8000 <= sample_rate <= 192000 and bits in (8, 16, 24, 32):
                                info += f"\nChannels: {channels}\n"
                                info += f"Sample Rate: {sample_rate} Hz\n"
                                info += f"Bits: {bits}-bit\n"
                                # Estimate duration
                                data_size = len(data) - 44
                                bytes_per_sec = sample_rate * channels * (bits // 8)
                                if bytes_per_sec > 0:
                                    duration = data_size / bytes_per_sec
                                    info += f"Duration: ~{duration:.1f} seconds\n"
                            else:
                                info += "\n(Invalid WAV header values)\n"
                        except struct.error:
                            info += "\n(WAV header parse error)\n"
                    else:
                        info += "\n(Invalid WAV format)\n"
                except Exception as e:
                    info += f"\n(Parse error: {e})\n"
            
            info += "\n(Audio playback not supported)"
            self.preview_label.setText(info)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        except Exception as e:
            self.preview_label.setText(f"Audio preview error: {e}")
    
    def _display_image(self, img: Image.Image):
        """Display PIL Image in preview label."""
        if not PIL_AVAILABLE:
            return
        
        # Convert to QPixmap
        qim = ImageQt(img)
        pixmap = QPixmap.fromImage(qim)
        
        # Scale if too large
        max_size = 800
        if pixmap.width() > max_size or pixmap.height() > max_size:
            pixmap = pixmap.scaled(max_size, max_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        self.preview_label.setPixmap(pixmap)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    
    def _on_debug_toggled(self, enabled: bool):
        """Handle debug mode toggle."""
        self._debug_mode = enabled
        if enabled:
            self.debug_checkbox.setText("🔍 Debug ON")
        else:
            self.debug_checkbox.setText("🔍 Debug")
        
        # If a file is currently previewed, refresh it to show/hide debug info
        if self._current_file_path:
            # Re-read and re-preview the current file
            self._preview_file(self._current_file_path)
    
    def _on_search_changed(self, text: str):
        """Handle search text change."""
        if not text:
            self._update_file_list()
            return
        
        # Filter file list by search text
        self.file_list.clear()
        
        if not self.vfs:
            return
        
        # Search in current directory
        dir_path = self.current_directory
        if not dir_path.endswith('/'):
            dir_path += '/'
        
        text_lower = text.lower()
        matches = []
        
        for file_path in self.vfs._file_index.keys():
            if file_path.startswith(dir_path):
                rel_path = file_path[len(dir_path):]
                if '/' not in rel_path and text_lower in rel_path.lower():
                    entry = self.vfs._file_index[file_path]
                    matches.append((rel_path, entry))
        
        matches.sort(key=lambda x: x[0].lower())
        
        for name, entry in matches:
            size_kb = entry.uncompressed_size / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
            
            item = QListWidgetItem(f"{name} ({size_str})")
            item.setData(Qt.ItemDataRole.UserRole, entry.path)
            self.file_list.addItem(item)
    
    def _on_tree_context_menu(self, position):
        """Show context menu for tree."""
        item = self.tree.itemAt(position)
        if not item:
            return
        
        menu = QMenu(self)
        
        extract_action = QAction("📦 Extract Folder", self)
        extract_action.triggered.connect(lambda: self._extract_folder(item))
        menu.addAction(extract_action)
        
        menu.exec(self.tree.mapToGlobal(position))
    
    def _on_file_context_menu(self, position):
        """Show context menu for file list."""
        item = self.file_list.itemAt(position)
        if not item:
            return
        
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            return
        
        menu = QMenu(self)
        
        # Extract
        extract_action = QAction("📦 Extract Selected", self)
        extract_action.triggered.connect(lambda checked, it=item: self._extract_selected(it))
        menu.addAction(extract_action)
        
        # Copy path
        copy_path_action = QAction("📋 Copy Path", self)
        copy_path_action.triggered.connect(lambda checked, it=item: self._copy_path(it))
        menu.addAction(copy_path_action)
        
        # View hex (always available)
        menu.addSeparator()
        view_hex_action = QAction("🔢 View Hex Dump", self)
        view_hex_action.triggered.connect(lambda checked, fp=file_path: self._view_hex_for_file(fp))
        menu.addAction(view_hex_action)
        
        # Only show "Open in Character Designer" for SPR/ACT files
        if file_path.lower().endswith(('.spr', '.act')):
            menu.addSeparator()
            open_designer_action = QAction("🎨 Open in Character Designer", self)
            open_designer_action.triggered.connect(lambda checked, it=item: self._open_in_designer(it))
            menu.addAction(open_designer_action)
        
        menu.exec(self.file_list.mapToGlobal(position))
    
    def _view_hex_for_file(self, file_path: str):
        """Force hex view for a file."""
        if not self.vfs:
            QMessageBox.warning(self, "Error", "No GRF loaded")
            return
        
        try:
            data = self.vfs.read_file(file_path)
            if data:
                self._preview_hex(data)
                # Also update file info if available
                entry = self.vfs.get_file_info(file_path)
                if entry:
                    info_text = f"File: {entry.original_path}\n"
                    info_text += f"Size: {len(data):,} bytes\n"
                    info_text += f"Source: {os.path.basename(entry.grf_path)}\n"
                    info_text += "\n(Hex dump view)"
                    self.file_info.setText(info_text)
            else:
                self.preview_label.setText("Failed to read file for hex view\n\n(File may be corrupted or use unsupported compression)")
        except Exception as e:
            self.preview_label.setText(f"Hex view error: {e}")
    
    def _extract_selected(self, item: QListWidgetItem):
        """Extract selected file."""
        if not self.vfs:
            QMessageBox.warning(self, "Error", "No GRF loaded")
            return
        
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            QMessageBox.warning(self, "Error", "No file selected")
            return
        
        # Choose output directory
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not output_dir:
            return
        
        # Read file data
        data = self.vfs.read_file(file_path)
        if not data:
            QMessageBox.warning(self, "Error", f"Failed to read file:\n{file_path}")
            return
        
        # Write to disk (preserve directory structure)
        output_path = os.path.join(output_dir, file_path.replace('/', os.sep))
        output_dir_path = os.path.dirname(output_path)
        
        try:
            os.makedirs(output_dir_path, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(data)
            QMessageBox.information(self, "Success", f"Extracted to:\n{output_path}")
            self._update_status()  # Update cache stats
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to extract file:\n{e}")
    
    def _extract_folder(self, item: QTreeWidgetItem):
        """Extract entire folder."""
        if not self.vfs:
            return
        
        dir_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not dir_path or not dir_path.endswith('/'):
            return
        
        # Choose output directory
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not output_dir:
            return
        
        # Find all files in this directory
        files_to_extract = []
        for file_path in self.vfs._file_index.keys():
            if file_path.startswith(dir_path):
                files_to_extract.append(file_path)
        
        if not files_to_extract:
            QMessageBox.information(self, "Info", "No files to extract")
            return
        
        # Extract with progress
        progress = QProgressDialog(f"Extracting {len(files_to_extract)} files...", "Cancel", 0, len(files_to_extract), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        
        extracted = 0
        for i, file_path in enumerate(files_to_extract):
            if progress.wasCanceled():
                break
            
            progress.setValue(i)
            progress.setLabelText(f"Extracting: {os.path.basename(file_path)}")
            
            # Read file
            data = self.vfs.read_file(file_path)
            if not data:
                continue
            
            # Write to disk
            output_path = os.path.join(output_dir, file_path.replace('/', os.sep))
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(data)
                extracted += 1
            except Exception as e:
                print(f"[ERROR] Failed to extract {file_path}: {e}")
        
        progress.setValue(len(files_to_extract))
        QMessageBox.information(self, "Complete", f"Extracted {extracted}/{len(files_to_extract)} files")
    
    def _copy_path(self, item: QListWidgetItem):
        """Copy file path to clipboard."""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(file_path)
            QMessageBox.information(self, "Copied", f"Path copied to clipboard:\n{file_path}")
        else:
            QMessageBox.warning(self, "Error", "No file selected")
    
    def _open_in_designer(self, item: QListWidgetItem):
        """Open sprite in Character Designer (if available)."""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if not file_path:
            QMessageBox.warning(self, "Error", "No file selected")
            return
        
        if not file_path.lower().endswith(('.spr', '.act')):
            QMessageBox.warning(self, "Error", "Character Designer only supports SPR and ACT files")
            return
        
        # Emit signal - the main window should handle this
        self.file_selected.emit(file_path)
        
        # Also try to find parent window and switch to Character Designer tab
        parent = self.parent()
        while parent:
            if hasattr(parent, 'tabs'):
                # Found main window - switch to Character Designer tab
                for i in range(parent.tabs.count()):
                    tab_text = parent.tabs.tabText(i)
                    if 'Character Designer' in tab_text or '🎨' in tab_text:
                        parent.tabs.setCurrentIndex(i)
                        # Try to load the GRF in Character Designer
                        if hasattr(parent, 'character_designer') and parent.character_designer:
                            # Get GRF path from current VFS
                            if self.vfs and self.vfs._archives:
                                grf_paths = [arch.grf_path for arch in self.vfs._archives]
                                parent.character_designer.compositor.set_grf_source(grf_paths)
                                # Update UI
                                if hasattr(parent.character_designer, 'path_edit'):
                                    parent.character_designer.path_edit.setText(grf_paths[0])
                                if hasattr(parent.character_designer, 'source_label'):
                                    parent.character_designer.source_label.setText(f"Source: GRF ({', '.join(os.path.basename(p) for p in grf_paths)})")
                        QMessageBox.information(self, "Info", f"Switched to Character Designer\n\nNote: You'll need to manually load the sprite:\n{file_path}")
                        return
            parent = parent.parent()
        
        QMessageBox.information(self, "Info", f"Character Designer signal sent for:\n{file_path}\n\nIf Character Designer tab is available, it should receive this file.")
    
    def _update_status(self):
        """Update status bar."""
        if not self.vfs:
            self.status_label.setText("No GRF loaded")
            self.stats_label.setText("")
            return
        
        stats = self.vfs.get_statistics()
        
        # Build status text
        loaded_grfs = [os.path.basename(arch.grf_path) for arch in self.vfs._archives]
        status_text = f"Loaded: {', '.join(loaded_grfs)}"
        self.status_label.setText(status_text)
        
        stats_text = f"Files: {stats['total_files']:,} | Cache: {stats['cache_size_mb']:.1f} MB | Hits: {stats['cache_hits']}/{stats['cache_hits'] + stats['cache_misses']}"
        self.stats_label.setText(stats_text)

