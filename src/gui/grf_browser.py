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
    from PIL import Image
    from PIL.ImageQt import ImageQt
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

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
    
    def run(self):
        """Load GRF file in background thread."""
        try:
            self.progress.emit(0, 100, f"Loading GRF: {os.path.basename(self.grf_path)}")
            
            # Load GRF (this may take time for large files)
            success = self.vfs.load_grf(self.grf_path, self.priority)
            
            if success:
                file_count = len(self.vfs._file_index)
                self.finished.emit(True, f"Loaded {file_count:,} files")
            else:
                self.finished.emit(False, "Failed to load GRF file")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.finished.emit(False, f"Error: {str(e)}")


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
        self._tree_build_worker = None
        
        self._setup_ui()
    
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
        Load a GRF file (asynchronously).
        
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
        
        # Create VFS if needed
        if self.vfs is None:
            self.vfs = GRFVirtualFileSystem(cache_size_mb=100)
        
        # Show loading UI
        self.loading_progress.setVisible(True)
        self.loading_progress.setRange(0, 0)  # Indeterminate
        self.status_label.setText(f"Loading GRF: {os.path.basename(grf_path)}...")
        
        # Disable buttons during loading
        for widget in self.findChildren(QPushButton):
            if widget.text() in ("📂 Load GRF...", "➕ Add GRF..."):
                widget.setEnabled(False)
        
        # Start async loading
        self._loading_worker = GRFLoadingWorker(grf_path, self.vfs, priority)
        self._loading_worker.progress.connect(self._on_loading_progress)
        self._loading_worker.finished.connect(lambda success, msg: self._on_loading_finished(success, msg, grf_path))
        self._loading_worker.start()
        
        return True
    
    def _on_loading_progress(self, current: int, total: int, message: str):
        """Handle loading progress update."""
        if total > 0:
            self.loading_progress.setMaximum(total)
            self.loading_progress.setValue(current)
        self.status_label.setText(message)
    
    def _on_loading_finished(self, success: bool, message: str, grf_path: str):
        """Handle loading completion."""
        self.loading_progress.setVisible(False)
        
        # Re-enable buttons
        for widget in self.findChildren(QPushButton):
            if widget.text() in ("📂 Load GRF...", "➕ Add GRF..."):
                widget.setEnabled(True)
        
        if success:
            self.status_label.setText(message)
            # Build tree incrementally (lazy loading)
            try:
                self._build_tree_incremental()
                self._update_status()
                QMessageBox.information(self, "Success", f"Loaded: {os.path.basename(grf_path)}\n\n{message}")
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "Error", f"Failed to build directory tree:\n{e}")
                self.status_label.setText(f"Error building tree: {e}")
        else:
            self.status_label.setText(f"Failed: {message}")
            QMessageBox.warning(self, "Error", f"Failed to load GRF:\n{message}")
    
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
            
            if self.load_grf(path, priority=priority):
                # Loading is async, message will be shown in _on_loading_finished
                pass
    
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
        """Preview SPR sprite file."""
        try:
            sprite = self.spr_parser.load_from_bytes(data)
            if sprite and sprite.get_total_frames() > 0:
                # Get first frame as image
                img = sprite.get_frame_image(0)
                if img and PIL_AVAILABLE:
                    self._display_image(img)
                    # Update file info with sprite details
                    info = self.file_info.text()
                    info += f"\n\nSPR Details:\nFrames: {sprite.get_total_frames()}\n"
                    info += f"Indexed: {sprite.get_indexed_count()}\n"
                    info += f"RGBA: {sprite.get_rgba_count()}"
                    self.file_info.setText(info)
                else:
                    self.preview_label.setText(f"SPR: {sprite.get_total_frames()} frames\n(Image rendering unavailable)")
                    self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                self.preview_label.setText("SPR: Invalid or empty sprite\n(File may be corrupted)")
                self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        except Exception as e:
            import traceback
            error_msg = f"SPR Preview Error:\n{str(e)}"
            self.preview_label.setText(error_msg)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    
    def _preview_act(self, data: bytes, file_path: str = ""):
        """Preview ACT action file."""
        try:
            act = self.act_parser.load_from_bytes(data)
            if act:
                # Try to load matching SPR file for visual preview
                spr_path = file_path.replace('.act', '.spr') if file_path else ""
                
                # Try to load SPR and render first frame
                if spr_path and self.vfs and self.vfs.file_exists(spr_path) and self.spr_parser:
                    spr_data = self.vfs.read_file(spr_path)
                    if spr_data:
                        try:
                            sprite = self.spr_parser.load_from_bytes(spr_data)
                            if sprite and sprite.get_total_frames() > 0 and PIL_AVAILABLE:
                                # Try to render first frame of first action
                                if act.get_action_count() > 0:
                                    action = act.get_action(0)
                                    if action.get_frame_count() > 0:
                                        frame = action.get_frame(0)
                                        if frame and len(frame.layers) > 0:
                                            # Get sprite frame from first layer
                                            layer = frame.layers[0]
                                            sprite_idx = layer.sprite_index
                                            if sprite_idx >= 0:
                                                if layer.sprite_type == 1:
                                                    sprite_idx += sprite.get_indexed_count()
                                                img = sprite.get_frame_image(sprite_idx)
                                                if img:
                                                    self._display_image(img)
                                                    # Add ACT info to file info
                                                    info = self.file_info.text()
                                                    info += f"\n\nACT Details:\n"
                                                    info += f"Actions: {act.get_action_count()}\n"
                                                    info += f"Events: {len(act.events)}\n"
                                                    info += f"Action 0: {action.get_frame_count()} frames, {len(frame.layers)} layers"
                                                    self.file_info.setText(info)
                                                    return
                        except Exception:
                            pass  # Fall through to text preview
                
                # Text-only preview if SPR not available
                info = f"ACT Version: {act.version}\n"
                info += f"Actions: {act.get_action_count()}\n"
                info += f"Events: {len(act.events)}\n"
                
                if act.get_action_count() > 0:
                    action = act.get_action(0)
                    if action:
                        info += f"\nAction 0: {action.get_frame_count()} frames"
                        if action.get_frame_count() > 0:
                            frame = action.get_frame(0)
                            if frame:
                                info += f", {len(frame.layers)} layers"
                
                self.preview_label.setText(info)
                self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            else:
                self.preview_label.setText("ACT: Invalid action file\n(File may be corrupted or incomplete)")
                self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        except Exception as e:
            error_msg = f"ACT Preview Error:\n{str(e)}"
            self.preview_label.setText(error_msg)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    
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
        Preview map file (.gat, .gnd, .rsw, .imf).
        
        These files contain binary map data. We show basic info without
        attempting to fully parse them, to avoid crashes on corrupted data.
        """
        try:
            info = f"{ext.upper().replace('.', '')} Map File\n\n"
            info += f"Size: {len(data):,} bytes\n"
            info += f"Path: {file_path}\n\n"
            
            # Only attempt parsing if we have enough data
            # Use very defensive parsing with multiple try/except blocks
            
            if ext == '.gat':
                info += "GAT: Ground Altitude Table (terrain walkability)\n"
                if len(data) >= 14:
                    try:
                        import struct
                        # GAT format: magic (4), version (2 bytes), width (4), height (4)
                        magic = data[0:4]
                        if magic == b'GRAT':
                            try:
                                version = struct.unpack('<H', data[4:6])[0]
                                width = struct.unpack('<I', data[6:10])[0]
                                height = struct.unpack('<I', data[10:14])[0]
                                # Sanity check dimensions
                                if 0 < width < 10000 and 0 < height < 10000:
                                    info += f"\nVersion: {version}\n"
                                    info += f"Map Size: {width} x {height} cells\n"
                                    info += f"Total Cells: {width * height:,}\n"
                                else:
                                    info += "\n(Dimensions out of range - may be corrupted)\n"
                            except struct.error:
                                info += "\n(Header parse error)\n"
                        else:
                            # Try legacy format (no magic)
                            try:
                                width = struct.unpack('<I', data[0:4])[0]
                                height = struct.unpack('<I', data[4:8])[0]
                                if 0 < width < 10000 and 0 < height < 10000:
                                    info += f"\nMap Size: {width} x {height} cells (legacy format)\n"
                                else:
                                    info += "\n(Invalid format or corrupted)\n"
                            except struct.error:
                                info += f"\n(Non-standard format: {magic})\n"
                    except Exception as e:
                        info += f"\n(Parse error: {e})\n"
                else:
                    info += "\n(File too small to parse)\n"
                    
            elif ext == '.gnd':
                info += "GND: Ground mesh data (textures, surfaces)\n"
                if len(data) >= 10:
                    try:
                        import struct
                        magic = data[0:4]
                        if magic == b'GRGN':
                            try:
                                version = struct.unpack('<H', data[4:6])[0]
                                info += f"\nVersion: {version}\n"
                            except struct.error:
                                info += "\n(Version parse error)\n"
                        else:
                            info += f"\n(Format: {magic.hex() if magic else 'unknown'})\n"
                    except Exception as e:
                        info += f"\n(Parse error: {e})\n"
                else:
                    info += "\n(File too small to parse)\n"
                    
            elif ext == '.rsw':
                info += "RSW: Resource World (map objects, lighting, sounds)\n"
                if len(data) >= 8:
                    try:
                        import struct
                        magic = data[0:4]
                        if magic == b'GRSW':
                            try:
                                version = struct.unpack('<H', data[4:6])[0]
                                info += f"\nVersion: {version}\n"
                                info += "Contains: Objects, Lights, Sounds, Effects\n"
                            except struct.error:
                                info += "\n(Version parse error)\n"
                        else:
                            info += f"\n(Format: {magic.hex() if magic else 'unknown'})\n"
                    except Exception as e:
                        info += f"\n(Parse error: {e})\n"
                else:
                    info += "\n(File too small to parse)\n"
                        
            elif ext == '.imf':
                info += "IMF: Interface Motion File (UI animations)\n"
                if len(data) >= 4:
                    try:
                        # IMF has various formats, just show basic info
                        info += f"\nData preview available via hex view\n"
                    except Exception as e:
                        info += f"\n(Parse error: {e})\n"
            
            else:
                info += f"\nUnrecognized map format: {ext}\n"
            
            # Always show hex preview option
            info += "\n\n[Right-click → View Hex Dump for raw data]"
            
            self.preview_label.setText(info)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            
        except Exception as e:
            # Ultimate fallback - show error and hex dump
            error_info = f"{ext.upper()} Preview Error:\n{str(e)}\n\n"
            error_info += "Showing hex dump instead:\n\n"
            self.preview_label.setText(error_info)
            try:
                self._preview_hex(data)
            except:
                self.preview_label.setText(f"Hex view also failed:\n{str(e)}")
    
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

