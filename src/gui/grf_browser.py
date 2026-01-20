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
        QFrame, QScrollArea, QProgressBar, QApplication, QComboBox, QDoubleSpinBox, QCheckBox,
        QSlider, QToolButton, QDialog
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QSize, QThread, QTimer
    from PyQt6.QtGui import QImage, QPixmap, QPainter, QAction, QIcon, QWheelEvent, QMouseEvent
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

# Try to import PIL for image preview
try:
    from PIL import Image, ImageDraw, ImageOps
    from PIL.ImageQt import ImageQt
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    ImageDraw = None

# Pillow/PyQt compatibility helper (see act_spr_editor.py for rationale)
if PIL_AVAILABLE:
    def _pil_to_qimage(pil_img):
        try:
            qimg = ImageQt(pil_img)
        except Exception:
            qimg = ImageQt.ImageQt(pil_img)
        try:
            return qimg.copy()
        except Exception:
            return qimg

# ==============================================================================
# Canvas Preview Widget (ActEditor-like: zoom/pan + fit-to-view + fixed origin)
# ==============================================================================
class CanvasPreviewWidget(QWidget):
    """
    Lightweight canvas widget:
      - Wheel zoom, pan by dragging
      - Fit-to-view
      - Optional fixed-origin crosshair (best for motion offsets)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self._pixmap: Optional[QPixmap] = None
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._dragging = False
        self._drag_last = None
        self._show_fixed_origin = False
        self._bg_checker = True

    def set_pixmap(self, pm: Optional[QPixmap]):
        self._pixmap = pm
        self.update()

    def clear(self):
        self._pixmap = None
        self.update()

    def set_fixed_origin(self, enabled: bool):
        self._show_fixed_origin = bool(enabled)
        self.update()

    def set_checkerboard(self, enabled: bool):
        self._bg_checker = bool(enabled)
        self.update()

    def reset_view(self):
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.update()

    def fit_to_view(self):
        if not self._pixmap or self._pixmap.isNull():
            return
        vw = max(1, self.width())
        vh = max(1, self.height())
        pw = max(1, self._pixmap.width())
        ph = max(1, self._pixmap.height())
        sx = vw / pw
        sy = vh / ph
        self._zoom = max(0.05, min(sx, sy))
        self._pan_x = 0.0
        self._pan_y = 0.0
        self.update()

    def wheelEvent(self, e: 'QWheelEvent'):
        if not self._pixmap or self._pixmap.isNull():
            return
        delta = e.angleDelta().y()
        if delta == 0:
            return
        old_zoom = self._zoom
        factor = 1.15 if delta > 0 else (1.0 / 1.15)
        new_zoom = max(0.05, min(32.0, old_zoom * factor))
        if abs(new_zoom - old_zoom) < 1e-6:
            return
        cx = e.position().x() - (self.width() / 2.0) - self._pan_x
        cy = e.position().y() - (self.height() / 2.0) - self._pan_y
        scale = new_zoom / old_zoom
        self._pan_x -= cx * (scale - 1.0)
        self._pan_y -= cy * (scale - 1.0)
        self._zoom = new_zoom
        self.update()

    def mousePressEvent(self, e: 'QMouseEvent'):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_last = e.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, e: 'QMouseEvent'):
        if self._dragging and self._drag_last is not None:
            cur = e.position()
            dx = cur.x() - self._drag_last.x()
            dy = cur.y() - self._drag_last.y()
            self._pan_x += dx
            self._pan_y += dy
            self._drag_last = cur
            self.update()

    def mouseReleaseEvent(self, e: 'QMouseEvent'):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._drag_last = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if self._bg_checker:
            tile = 16
            c1 = self.palette().color(self.backgroundRole())
            c2 = self.palette().color(self.backgroundRole()).darker(110)
            for y in range(0, self.height(), tile):
                for x in range(0, self.width(), tile):
                    p.fillRect(x, y, tile, tile, c1 if ((x // tile + y // tile) % 2 == 0) else c2)
        else:
            p.fillRect(0, 0, self.width(), self.height(), self.palette().color(self.backgroundRole()))

        if self._pixmap and not self._pixmap.isNull():
            cx = self.width() / 2.0 + self._pan_x
            cy = self.height() / 2.0 + self._pan_y
            w = self._pixmap.width() * self._zoom
            h = self._pixmap.height() * self._zoom
            x = cx - (w / 2.0)
            y = cy - (h / 2.0)
            p.drawPixmap(int(x), int(y), int(w), int(h), self._pixmap)

        if self._show_fixed_origin:
            midx = int(self.width() / 2)
            midy = int(self.height() / 2)
            p.setPen(self.palette().color(self.foregroundRole()))
            p.drawLine(midx - 12, midy, midx + 12, midy)
            p.drawLine(midx, midy - 12, midx, midy + 12)
            p.drawRect(midx - 1, midy - 1, 2, 2)

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


class PreviewWorker(QThread):
    """Worker thread for loading and rendering file previews asynchronously."""

    # Emit image as bytes + size tuple to avoid cross-thread PIL/Qt issues
    preview_ready = pyqtSignal(bytes, int, int, str, str)  # image_bytes, width, height, info_text, file_path
    preview_act_ready = pyqtSignal(object, object, str, str)  # act_data, spr_data, info_text, file_path
    preview_text = pyqtSignal(str, str, str)  # text_content, info_text, file_path
    error = pyqtSignal(str, str)  # error_message, file_path

    def __init__(self, vfs, file_path: str, spr_parser=None, act_parser=None, debug_mode: bool = False):
        super().__init__()
        self.vfs = vfs
        self.file_path = file_path
        self.spr_parser = spr_parser
        self.act_parser = act_parser
        self.debug_mode = debug_mode
        self._cancelled = False

    def cancel(self):
        """Cancel the preview operation."""
        self._cancelled = True

    def _emit_image(self, img, info_text: str):
        """Convert PIL image to bytes and emit signal (thread-safe)."""
        if self._cancelled:
            return
        
        if img is None:
            self.error.emit("Image is None - rendering failed", self.file_path)
            return
        
        try:
            # Validate image dimensions
            width, height = img.size
            if width <= 0 or height <= 0:
                self.error.emit(f"Invalid image dimensions: {width}x{height}", self.file_path)
                return
            
            if width > 4096 or height > 4096:
                # Scale down oversized images
                scale = min(4096 / width, 4096 / height)
                new_size = (int(width * scale), int(height * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                width, height = img.size
                if self.debug_mode:
                    print(f"[DEBUG] Scaled image from {width}x{height} to {new_size}")
            
            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Validate byte count
            img_bytes = img.tobytes()
            expected_bytes = width * height * 4
            if len(img_bytes) != expected_bytes:
                self.error.emit(f"Image byte mismatch: got {len(img_bytes)}, expected {expected_bytes}", self.file_path)
                return
            
            if self.debug_mode:
                print(f"[DEBUG] Emitting image: {width}x{height}, {len(img_bytes)} bytes")
            
            self.preview_ready.emit(img_bytes, width, height, info_text, self.file_path)
            
        except Exception as e:
            import traceback
            error_msg = f"Failed to convert image: {e}"
            if self.debug_mode:
                error_msg += f"\n{traceback.format_exc()}"
            self.error.emit(error_msg, self.file_path)

    def run(self):
        """Load and render preview in background thread."""
        if self._cancelled:
            return

        try:
            # Get file info
            entry = self.vfs.get_file_info(self.file_path)
            if not entry:
                self.error.emit("File not found in GRF index", self.file_path)
                return

            if self._cancelled:
                return

            # Read file data
            data = self.vfs.read_file(self.file_path)
            if not data:
                self.error.emit("Failed to read/decompress file\n\n(File may be corrupted or use unsupported compression)", self.file_path)
                return

            if self._cancelled:
                return

            # Build file info text
            ext = os.path.splitext(self.file_path)[1].lower()
            info_text = f"File: {entry.original_path}\n"
            info_text += f"Size: {entry.uncompressed_size:,} bytes\n"
            info_text += f"Compressed: {entry.compressed_size:,} bytes\n"
            info_text += f"Source: {os.path.basename(entry.grf_path)}\n"
            info_text += f"Type: {ext if ext else '(no extension)'}\n"
            info_text += f"Compression: {entry.compression_type}\n"
            info_text += f"Encrypted: {'Yes' if entry.is_encrypted() else 'No'}"

            if self._cancelled:
                return

            # Process based on file type
            if ext == '.spr' and PIL_AVAILABLE and self.spr_parser:
                self._process_spr(data, info_text)
            elif ext == '.act' and PARSERS_AVAILABLE and self.act_parser:
                self._process_act(data, info_text)
            elif ext in ('.bmp', '.jpg', '.jpeg', '.png', '.tga') and PIL_AVAILABLE:
                self._process_image(data, info_text)
            elif ext in ('.txt', '.xml', '.lua', '.lub', '.dat', '.ini', '.cfg'):
                self._process_text(data, info_text)
            else:
                # Unknown type - show hex
                self._process_hex(data, info_text)

        except Exception as e:
            if not self._cancelled:
                import traceback
                error_msg = f"Error loading file:\n{str(e)}"
                if self.debug_mode:
                    error_msg += f"\n\n{traceback.format_exc()}"
                self.error.emit(error_msg, self.file_path)

    def _process_spr(self, data: bytes, info_text: str):
        """Process SPR.

        Behavior:
        - If matching .act exists (same basename), auto-load it so the preview can animate (manual-play).
        - If no matching .act exists, show first frame as a static preview.
        """
        if self._cancelled:
            return

        try:
            sprite = self.spr_parser.load_from_bytes(data)

            if self._cancelled:
                return

            if sprite is None:
                self.preview_text.emit("❌ SPR Parse Failed\n\nThe SPR file could not be parsed.", info_text, self.file_path)
                return

            total_frames = sprite.get_total_frames()
            if total_frames <= 0:
                self.preview_text.emit("❌ SPR has 0 frames", info_text, self.file_path)
                return

            # SPR details
            info_text += "\n\nSPR Details:\n"
            info_text += f"Total Frames: {sprite.get_total_frames()}\n"
            info_text += f"Indexed: {sprite.get_indexed_count()}\n"
            info_text += f"RGBA: {sprite.get_rgba_count()}\n"

            # Auto-load matching ACT if it exists
            base = self.file_path.rsplit('.', 1)[0]
            act_path = base + ".act"

            if self.act_parser and self.vfs and self.vfs.file_exists(act_path):
                act_bytes = self.vfs.read_file(act_path)
                if act_bytes and not self._cancelled:
                    act = self.act_parser.load_from_bytes(act_bytes)
                    if act is not None and not self._cancelled:
                        info_text += "\n\n✅ Auto-loaded ACT for animation:\n"
                        info_text += f"{act_path}\n"
                        info_text += f"Actions: {act.get_action_count()}\n"
                        self.preview_act_ready.emit(act, sprite, info_text, self.file_path)
                        return

            # Fallback: static first frame
            img = sprite.get_frame_image(0)
            if img:
                info_text += "\n\n💡 Note: SPR files are frame containers.\n"
                info_text += "For ACT-driven animation, select the matching .act."
                self._emit_image(img, info_text)
            else:
                self.preview_text.emit(
                    f"SPR: {total_frames} frames\n⚠️ Frame 0 render failed",
                    info_text,
                    self.file_path
                )

        except Exception as e:
            if not self._cancelled:
                import traceback
                msg = f"❌ SPR Preview Error:\n{str(e)}"
                if self.debug_mode:
                    msg += f"\n\n{traceback.format_exc()}"
                self.preview_text.emit(msg, info_text, self.file_path)

    def _process_act(self, data: bytes, info_text: str):
        """Process ACT action file."""
        if self._cancelled:
            return

        try:
            act = self.act_parser.load_from_bytes(data)

            if self._cancelled:
                return

            if act is None:
                error_msg = "❌ ACT Parse Failed"
                self.preview_text.emit(error_msg, info_text, self.file_path)
                return

            # Try to load matching SPR file
            spr_path = self.file_path.replace('.act', '.spr')

            if self._cancelled:
                return

            if self.vfs.file_exists(spr_path) and self.spr_parser:
                spr_data = self.vfs.read_file(spr_path)

                if self._cancelled:
                    return

                if spr_data:
                    sprite = self.spr_parser.load_from_bytes(spr_data)

                    if self._cancelled:
                        return

                    if sprite and sprite.get_total_frames() > 0:
                        info_text += f"\n\nACT Details:\n"
                        info_text += f"Actions: {act.get_action_count()}\n"
                        info_text += f"Events: {len(act.events)}\n"
                        self.preview_act_ready.emit(act, sprite, info_text, self.file_path)
                        return

            # Fallback to text info
            info = f"ACT Version: {act.version}\n"
            info += f"Actions: {act.get_action_count()}\n"
            info += f"Events: {len(act.events)}"
            self.preview_text.emit(info, info_text, self.file_path)

        except Exception as e:
            if not self._cancelled:
                error_msg = f"❌ ACT Preview Error:\n{str(e)}"
                self.preview_text.emit(error_msg, info_text, self.file_path)

    def _process_image(self, data: bytes, info_text: str):
        """Process image file."""
        if self._cancelled:
            return

        try:
            img = Image.open(io.BytesIO(data))
            if not self._cancelled:
                self._emit_image(img, info_text)
        except Exception as e:
            if not self._cancelled:
                self.preview_text.emit(f"Image Preview Error: {e}", info_text, self.file_path)

    def _process_text(self, data: bytes, info_text: str):
        """Process text file."""
        if self._cancelled:
            return

        try:
            for encoding in ['utf-8', 'euc-kr', 'latin-1']:
                try:
                    text = data.decode(encoding)
                    if len(text) > 10000:
                        text = text[:10000] + "\n\n... (truncated)"
                    if not self._cancelled:
                        self.preview_text.emit(text, info_text, self.file_path)
                    return
                except UnicodeDecodeError:
                    continue

            # Fallback to hex
            self._process_hex(data, info_text)
        except Exception as e:
            if not self._cancelled:
                self.preview_text.emit(f"Text Preview Error: {e}", info_text, self.file_path)

    def _process_hex(self, data: bytes, info_text: str):
        """Process as hex dump."""
        if self._cancelled:
            return

        try:
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

            if not self._cancelled:
                self.preview_text.emit('\n'.join(hex_lines), info_text, self.file_path)
        except Exception as e:
            if not self._cancelled:
                self.preview_text.emit(f"Hex view error: {e}", info_text, self.file_path)


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
            
            print(f"[INFO] Indexing worker: Found {total} entries in archive")
            
            if total == 0:
                print("[WARN] Indexing worker: No entries found in archive")
                self.finished.emit(False, {})
                return
            
            # Build index with progress updates
            index = {}
            processed = 0
            skipped = 0
            progress_interval = max(1, total // 100)  # Update every 1%
            
            for entry in entries:
                if self._cancelled:
                    print("[INFO] Indexing worker: Cancelled")
                    self.finished.emit(False, {})
                    return
                
                try:
                    normalized_path = entry.path
                    if not normalized_path:
                        skipped += 1
                        continue
                    
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
                    skipped += 1
                    if skipped <= 5:  # Only print first few errors
                        print(f"[WARN] Indexing worker: Skipped invalid entry: {e}")
                    continue
            
            if self._cancelled:
                print("[INFO] Indexing worker: Cancelled after processing")
                self.finished.emit(False, {})
                return
            
            print(f"[INFO] Indexing worker: Processed {processed} entries, skipped {skipped}, index size: {len(index)}")
            
            # Return index data for UI thread
            self.finished.emit(True, index)
            
        except Exception as e:
            import traceback
            print(f"[ERROR] Indexing worker exception: {e}")
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
        self._preview_worker = None  # Worker for async preview loading
        self._current_archive = None  # Archive being indexed
        self._debug_mode = False  # Debug mode for showing parse failures
        
        # Check for NumPy availability and warn if missing
        try:
            import numpy
            self._numpy_available = True
        except ImportError:
            self._numpy_available = False
            print("=" * 60)
            print("[PERFORMANCE WARNING] NumPy is NOT installed!")
            print("SPR preview will be VERY SLOW without NumPy.")
            print("Install with: pip install numpy")
            print("=" * 60)
        
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

        # --- ActEditor-like preview: Canvas (zoom/pan/fit) + controls ---
        self.preview_canvas = CanvasPreviewWidget()
        self.preview_canvas.set_checkerboard(True)
        preview_layout.addWidget(self.preview_canvas)

        # Legacy text preview label (not added to layout; kept to avoid attribute errors)
        self.preview_label = QLabel("No file selected")

        canvas_controls = QHBoxLayout()
        self.btn_fit = QToolButton()
        self.btn_fit.setText("Fit")
        self.btn_fit.setToolTip("Fit image to view")
        self.btn_fit.clicked.connect(lambda: self.preview_canvas.fit_to_view())
        canvas_controls.addWidget(self.btn_fit)

        self.btn_reset_view = QToolButton()
        self.btn_reset_view.setText("1:1")
        self.btn_reset_view.setToolTip("Reset zoom/pan")
        self.btn_reset_view.clicked.connect(lambda: self.preview_canvas.reset_view())
        canvas_controls.addWidget(self.btn_reset_view)

        self.fixed_origin_check = QCheckBox("Fixed origin")
        self.fixed_origin_check.setToolTip("Show crosshair at canvas center (useful for motion offsets)")
        self.fixed_origin_check.toggled.connect(self._on_fixed_origin_toggled)
        canvas_controls.addWidget(self.fixed_origin_check)

        self.btn_sprite_sheet = QToolButton()
        self.btn_sprite_sheet.setText("Sprite Sheet")
        self.btn_sprite_sheet.setToolTip("Open sprite sheet viewer for SPR frames")
        self.btn_sprite_sheet.clicked.connect(self._open_sprite_sheet_viewer)
        canvas_controls.addWidget(self.btn_sprite_sheet)

        canvas_controls.addStretch()
        preview_layout.addLayout(canvas_controls)
        
        # ACT preview controls (animation)
        self.act_preview_controls = QHBoxLayout()
        self.act_preview_controls.addWidget(QLabel("Action:"))
        self.act_action_combo = QComboBox()
        self.act_action_combo.setMinimumContentsLength(28)
        self.act_action_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.act_action_combo.view().setMinimumWidth(280)
        self.act_action_combo.currentIndexChanged.connect(self._on_act_action_changed)
        self.act_preview_controls.addWidget(self.act_action_combo)
        self.act_play_btn = QPushButton("▶ Play")
        self.act_play_btn.clicked.connect(self._toggle_act_preview)
        self.act_preview_controls.addWidget(self.act_play_btn)
        
        self.act_preview_controls.addWidget(QLabel("Delay x"))
        self.act_delay_scale = QDoubleSpinBox()
        self.act_delay_scale.setRange(0.1, 5.0)
        self.act_delay_scale.setSingleStep(0.1)
        self.act_delay_scale.setValue(1.0)
        self.act_delay_scale.valueChanged.connect(self._on_act_delay_scale_changed)
        self.act_preview_controls.addWidget(self.act_delay_scale)
        
        self.act_debug_overlay = QCheckBox("Debug overlay")
        self.act_debug_overlay.toggled.connect(self._on_act_debug_toggled)
        self.act_preview_controls.addWidget(self.act_debug_overlay)

        self.act_show_spr_only = QCheckBox("SPR frame only")
        self.act_show_spr_only.setToolTip("When enabled: selecting a thumbnail shows that SPR frame only (no ACT compositing)")
        self.act_show_spr_only.toggled.connect(self._on_act_spr_only_toggled)
        self.act_preview_controls.addWidget(self.act_show_spr_only)

        self.act_preview_controls.addStretch()
        preview_layout.addLayout(self.act_preview_controls)

        timeline_row = QHBoxLayout()
        timeline_row.addWidget(QLabel("Frame:"))
        self.act_frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.act_frame_slider.setMinimum(0)
        self.act_frame_slider.setMaximum(0)
        self.act_frame_slider.setSingleStep(1)
        self.act_frame_slider.setPageStep(1)
        self.act_frame_slider.valueChanged.connect(self._on_act_frame_slider_changed)
        timeline_row.addWidget(self.act_frame_slider)
        self.act_frame_label = QLabel("0 / 0")
        self.act_frame_label.setMinimumWidth(72)
        timeline_row.addWidget(self.act_frame_label)
        preview_layout.addLayout(timeline_row)

        self.act_thumb_strip = QListWidget()
        self.act_thumb_strip.setViewMode(QListWidget.ViewMode.IconMode)
        self.act_thumb_strip.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.act_thumb_strip.setMovement(QListWidget.Movement.Static)
        self.act_thumb_strip.setWrapping(False)
        # Give more distance / breathing room between per-frame thumbnails (ActEditor-like strip)
        self.act_thumb_strip.setIconSize(QSize(56, 56))
        # Grid size controls item spacing much more reliably than setSpacing alone
        self.act_thumb_strip.setGridSize(QSize(72, 88))
        self.act_thumb_strip.setMinimumHeight(96)
        self.act_thumb_strip.setSpacing(10)
        self.act_thumb_strip.itemSelectionChanged.connect(self._on_act_thumbnail_selected)
        preview_layout.addWidget(self.act_thumb_strip)
        
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
        
        # ACT preview state
        self._act_preview_timer = QTimer(self)
        self._act_preview_timer.timeout.connect(self._advance_act_preview_frame)
        self._act_preview_act = None
        self._act_preview_sprite = None
        self._act_preview_action_idx = 0
        self._act_preview_frame_idx = 0
        self._act_preview_playing = False
        self._act_preview_file_path = None
        self._act_delay_scale = 1.0
        self._act_debug_overlay_enabled = False
        self._act_frame_cache = {}  # Cache rendered SPR frames: {sprite_idx: Image}
        self._preview_img_bytes = None  # Keep reference for QImage byte lifetime

        # ActEditor-like UI state
        self._act_selected_spr_idx: Optional[int] = None
        self._act_thumb_timer = QTimer(self)
        self._act_thumb_timer.timeout.connect(self._build_thumbnails_tick)
        self._act_thumb_pending: List[int] = []
        self._act_thumb_icon_cache: Dict[int, QIcon] = {}
    
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
            # Debug logging
            if self._debug_mode:
                print(f"[DEBUG] Indexing finished: {len(index)} entries")
                if len(index) > 0:
                    sample_paths = list(index.keys())[:5]
                    print(f"[DEBUG] Sample paths: {sample_paths}")
            
            # Merge index into VFS
            if self.vfs._file_index:
                # Merge with existing index (higher priority overrides)
                self.vfs.merge_file_index(index)
                if self._debug_mode:
                    print(f"[DEBUG] Merged index, total files: {len(self.vfs._file_index)}")
            else:
                # First GRF - set index directly
                self.vfs.set_file_index(index)
                if self._debug_mode:
                    print(f"[DEBUG] Set initial index, total files: {len(self.vfs._file_index)}")
            
            file_count = len(self.vfs._file_index)
            
            if file_count == 0:
                self.status_label.setText("Warning: GRF loaded but no files found in index")
                QMessageBox.warning(self, "Warning", 
                    f"GRF file loaded but no files were indexed.\n\n"
                    f"This may indicate:\n"
                    f"- The GRF file is empty\n"
                    f"- The file table is corrupted\n"
                    f"- There was an error during parsing\n\n"
                    f"Check console output for details.")
                self._current_archive = None
                return
            
            self.status_label.setText(f"Loaded {file_count:,} files")
            
            # Set current directory to root
            self.current_directory = ""
            
            # Build tree incrementally (lazy loading)
            try:
                self._build_tree_incremental()
                
                # Update file list for root directory
                self._update_file_list()
                
                self._update_status()
                
                if self._debug_mode:
                    print(f"[DEBUG] Tree built successfully, file list updated")
                
                QMessageBox.information(self, "Success", f"Loaded: {os.path.basename(grf_path)}\n\n{file_count:,} files indexed")
            except Exception as e:
                import traceback
                error_msg = f"Failed to build directory tree:\n{e}"
                if self._debug_mode:
                    print(f"[DEBUG] Tree build error:\n{traceback.format_exc()}")
                traceback.print_exc()
                QMessageBox.critical(self, "Error", error_msg)
                self.status_label.setText(f"Error building tree: {e}")
        else:
            error_msg = f"Failed to index GRF:\n{grf_path}"
            if self._debug_mode:
                print(f"[DEBUG] Indexing failed: success={success}, index_size={len(index) if index else 0}")
            self.status_label.setText("Failed to index GRF")
            QMessageBox.warning(self, "Error", 
                f"{error_msg}\n\nThe file may be corrupted or inaccessible.\n\n"
                f"Check console output for details.")
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
            if self._debug_mode:
                print("[DEBUG] Cannot build tree: VFS is None")
            return
        
        if not self.vfs._file_index:
            if self._debug_mode:
                print("[DEBUG] Cannot build tree: File index is empty")
            self.status_label.setText("No files in index - tree cannot be built")
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
            
            if self._debug_mode:
                print(f"[DEBUG] Building tree from {file_count:,} files")
            
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
            
            if self._debug_mode:
                print(f"[DEBUG] Tree built: {len(top_dirs)} directories, {len(top_files)} root files")
            
            if file_count > max_process:
                self.status_label.setText(f"Loaded {max_process:,}/{file_count:,} files (showing top-level only)")
            else:
                self.status_label.setText(f"Loaded {file_count:,} files")
                
        except Exception as e:
            import traceback
            error_msg = f"Error building tree: {e}"
            if self._debug_mode:
                print(f"[DEBUG] Tree build exception:\n{traceback.format_exc()}")
            traceback.print_exc()
            self.status_label.setText(error_msg)
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

        if not path:
            return
        
        # Check if this is a file or directory
        # Files don't end with '/' and exist in the file index
        # Directories end with '/' or have children
        is_directory = path.endswith('/') or path == ''
        
        # Also check if it's actually a file in the index
        if not is_directory and self.vfs and path in self.vfs._file_index:
            # It's a file - preview it instead of showing as directory
            if self._debug_mode:
                print(f"[DEBUG] Tree selection: File selected - {path}")
            self._current_file_path = path
            self._preview_file(path)
            return
        
        # It's a directory - update file list
        if self._debug_mode:
            print(f"[DEBUG] Tree selection: Directory selected - {path}")
        self.current_directory = path
        self._update_file_list()
    
    def _update_file_list(self):
        """Update file list for current directory."""
        if not self.vfs:
            if self._debug_mode:
                print("[DEBUG] Cannot update file list: VFS is None")
            return

        if not self.vfs._file_index:
            if self._debug_mode:
                print("[DEBUG] Cannot update file list: File index is empty")
            self.file_list.clear()
            self.file_list.addItem(QListWidgetItem("(No files in index)"))
            return

        self.file_list.clear()

        # Get files in current directory
        files = []
        dir_path = self.current_directory

        # Ensure directory path ends with '/' for proper matching
        # But don't add '/' if it's empty (root directory)
        if dir_path and not dir_path.endswith('/'):
            dir_path += '/'

        if self._debug_mode:
            print(f"[DEBUG] Updating file list for directory: '{dir_path}'")

        for file_path in self.vfs._file_index.keys():
            # For root directory (empty string), match files that don't have '/' in them
            if dir_path == '':
                if '/' not in file_path:
                    entry = self.vfs._file_index[file_path]
                    files.append((file_path, entry))
            elif file_path.startswith(dir_path):
                # Get relative path
                rel_path = file_path[len(dir_path):]
                # Only show immediate children (not subdirectories)
                if '/' not in rel_path:
                    entry = self.vfs._file_index[file_path]
                    files.append((rel_path, entry))

        # Sort files
        files.sort(key=lambda x: x[0].lower())

        if self._debug_mode:
            print(f"[DEBUG] Found {len(files)} files in directory")

        # Add to list
        for name, entry in files:
            # Format: "filename.ext (24 KB)"
            size_kb = entry.uncompressed_size / 1024
            size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"

            item = QListWidgetItem(f"{name} ({size_str})")
            item.setData(Qt.ItemDataRole.UserRole, entry.path)
            self.file_list.addItem(item)
        
        if len(files) == 0:
            self.file_list.addItem(QListWidgetItem("(No files in this directory)"))
    
    def _on_file_selection_changed(self):
        """Handle file list selection change."""
        # Cancel any running preview worker immediately
        self._cancel_preview_worker()
        self._reset_act_preview()

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

    def _cancel_preview_worker(self):
        """Cancel any running preview worker."""
        if self._preview_worker is not None:
            if self._preview_worker.isRunning():
                self._preview_worker.cancel()
                self._preview_worker.quit()
                self._preview_worker.wait(100)  # Brief wait
            self._preview_worker = None
    
    def _on_file_double_clicked(self, item: QListWidgetItem):
        """Handle file double-click."""
        file_path = item.data(Qt.ItemDataRole.UserRole)
        if file_path:
            self._preview_file(file_path)
    
    def _preview_file(self, file_path: str):
        """Preview a file with async loading for heavy files (SPR/ACT)."""
        if not self.vfs:
            return

        # Store current file path
        self._current_file_path = file_path

        # Check file extension
        ext = os.path.splitext(file_path)[1].lower()

        # For SPR/ACT files, use async worker to avoid blocking GUI
        if ext in ('.spr', '.act'):
            self._preview_file_async(file_path)
            return

        # For other file types, use sync preview (they're fast enough)
        self._preview_file_sync(file_path)

    def _preview_file_async(self, file_path: str):
        """Preview file using async worker thread (for heavy files like SPR/ACT)."""
        # Cancel any existing preview worker
        self._cancel_preview_worker()
        self._reset_act_preview()

        # Debug output
        if self._debug_mode:
            print(f"[DEBUG] Starting async preview for: {file_path}")
            print(f"[DEBUG] VFS loaded: {self.vfs is not None}")
            print(f"[DEBUG] SPR parser: {self.spr_parser is not None}")
            print(f"[DEBUG] ACT parser: {self.act_parser is not None}")
            print(f"[DEBUG] PIL available: {PIL_AVAILABLE}")

        # Show loading indicator
        self.preview_label.setText("Loading preview...")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_info.setText("Loading...")

        # Create and start preview worker
        self._preview_worker = PreviewWorker(
            self.vfs,
            file_path,
            self.spr_parser,
            self.act_parser,
            self._debug_mode
        )
        
        # Connect signals with debug wrappers if in debug mode
        if self._debug_mode:
            self._preview_worker.preview_ready.connect(
                lambda *args: self._debug_log_preview_ready(*args) or self._on_preview_ready(*args)
            )
        else:
            self._preview_worker.preview_ready.connect(self._on_preview_ready)
        
        self._preview_worker.preview_act_ready.connect(self._on_act_preview_ready)
        self._preview_worker.preview_text.connect(self._on_preview_text)
        self._preview_worker.error.connect(self._on_preview_error)
        self._preview_worker.start()
    
    def _debug_log_preview_ready(self, img_bytes: bytes, width: int, height: int, info_text: str, file_path: str):
        """Debug logging for preview ready signal."""
        print(f"[DEBUG] Preview ready signal received:")
        print(f"[DEBUG]   File: {file_path}")
        print(f"[DEBUG]   Dimensions: {width}x{height}")
        print(f"[DEBUG]   Bytes: {len(img_bytes)}")
        print(f"[DEBUG]   Expected: {width * height * 4}")
        return False  # Return False so lambda continues to _on_preview_ready

    def _on_preview_ready(self, img_bytes: bytes, width: int, height: int, info_text: str, file_path: str):
        """Handle preview image ready from worker."""
        # Only update if this is still the current file
        if file_path != self._current_file_path:
            return

        try:
            # Validate input
            expected_size = width * height * 4
            if len(img_bytes) != expected_size:
                error_msg = f"Image size mismatch: got {len(img_bytes)} bytes, expected {expected_size}"
                if self._debug_mode:
                    print(f"[DEBUG] {error_msg}")
                self.preview_label.setText(error_msg)
                return
            
            if width <= 0 or height <= 0:
                error_msg = f"Invalid dimensions: {width}x{height}"
                if self._debug_mode:
                    print(f"[DEBUG] {error_msg}")
                self.preview_label.setText(error_msg)
                return
            
            # Create QImage with explicit stride (bytes per line)
            stride = width * 4  # 4 bytes per pixel for RGBA
            
            # IMPORTANT: QImage doesn't copy the data, so we need to keep img_bytes alive
            # Store reference to prevent garbage collection
            self._preview_img_bytes = img_bytes
            
            qimg = QImage(self._preview_img_bytes, width, height, stride, QImage.Format.Format_RGBA8888)
            
            # Verify QImage was created successfully
            if qimg.isNull():
                error_msg = "Failed to create QImage from bytes"
                if self._debug_mode:
                    print(f"[DEBUG] {error_msg} - width={width}, height={height}, stride={stride}, bytes_len={len(img_bytes)}")
                self.preview_label.setText(error_msg)
                self._preview_img_bytes = None
                return
            
            # Now make a deep copy (this copies the pixel data)
            qimg = qimg.copy()
            
            # Clear the reference since we have a copy now
            self._preview_img_bytes = None
            
            pixmap = QPixmap.fromImage(qimg)
            
            if pixmap.isNull():
                error_msg = "Failed to create pixmap from QImage"
                if self._debug_mode:
                    print(f"[DEBUG] {error_msg}")
                self.preview_label.setText(error_msg)
                return

            # Scale if too large
            max_size = 800
            if pixmap.width() > max_size or pixmap.height() > max_size:
                pixmap = pixmap.scaled(max_size, max_size, 
                                       Qt.AspectRatioMode.KeepAspectRatio, 
                                       Qt.TransformationMode.SmoothTransformation)

            self.preview_canvas.set_pixmap(pixmap)
            # Default to 1:1 (user requested). Fit is manual.
            self.preview_canvas.reset_view()
            self.file_info.setText(info_text)
            
        except Exception as e:
            import traceback
            error_msg = f"Failed to display image:\n{e}"
            if self._debug_mode:
                error_msg += f"\n\n{traceback.format_exc()}"
            self.preview_label.setText(error_msg)
            self._preview_img_bytes = None

    def _on_preview_text(self, text: str, info_text: str, file_path: str):
        """Handle preview text ready from worker."""
        # Only update if this is still the current file
        if file_path != self._current_file_path:
            return

        self.preview_canvas.set_pixmap(None)
        self.file_info.setText(info_text)

    def _on_preview_error(self, error_msg: str, file_path: str):
        """Handle preview error from worker."""
        # Only update if this is still the current file
        if file_path != self._current_file_path:
            return
        
        self.preview_canvas.set_pixmap(None)
        self.file_info.setText("Error - see preview for details")
    
    def _on_act_preview_ready(self, act_data, spr_data, info_text: str, file_path: str):
        """Handle ACT preview ready from worker."""
        if file_path != self._current_file_path:
            return
        
        # Clear any existing cache first
        self._act_frame_cache.clear()
        
        self._act_preview_act = act_data
        self._act_preview_sprite = spr_data
        self._act_preview_file_path = file_path
        self.file_info.setText(info_text)
        
        # Validate sprite data is usable
        if not spr_data or spr_data.get_total_frames() == 0:
            error_msg = "❌ SPR has no frames - cannot preview ACT"
            if self._debug_mode:
                print(f"[DEBUG] ACT preview failed: {error_msg}")
            self.preview_canvas.set_pixmap(None)
            return
        
        # Populate action combo with frame counts
        self.act_action_combo.blockSignals(True)
        self.act_action_combo.clear()
        for idx in range(act_data.get_action_count()):
            action = act_data.get_action(idx)
            frame_count = action.get_frame_count() if action else 0
            display_text = f"Action {idx} ({frame_count} frames)"
            self.act_action_combo.addItem(display_text, idx)
            item_index = self.act_action_combo.count() - 1
            self.act_action_combo.setItemData(
                item_index,
                display_text,
                Qt.ItemDataRole.ToolTipRole
            )
        # Pick a sensible default action (first drawable), not always Action 0.
        best_action = self._find_first_drawable_action(act_data, spr_data)
        combo_index = self.act_action_combo.findData(best_action)
        if combo_index < 0:
            combo_index = 0
        self.act_action_combo.setCurrentIndex(combo_index)
        self.act_action_combo.blockSignals(False)

        self._act_preview_action_idx = self.act_action_combo.currentData() or 0
        self._act_preview_frame_idx = 0
        
        # Pre-cache first few sprite frames to ensure render works
        self._precache_sprite_frames(5)

        # Sync slider/thumbs at load time (requires spr_data)
        self._sync_act_timeline_and_thumbs_on_load()
        
        # Now render
        self._render_act_preview_frame()

    def _find_first_drawable_action(self, act_data, spr_data) -> int:
        """Find the first action that references at least one valid sprite index.

        Some archives have empty Action 0, or offsets that draw off-center.
        This avoids starting on an action that renders nothing.
        """
        try:
            indexed_count = spr_data.get_indexed_count()
            total = spr_data.get_total_frames()
            for a_idx in range(act_data.get_action_count()):
                action = act_data.get_action(a_idx)
                if not action or action.get_frame_count() <= 0:
                    continue
                # sample first few frames only (fast)
                sample = min(5, action.get_frame_count())
                for f_idx in range(sample):
                    frame = action.get_frame(f_idx)
                    if not frame:
                        continue
                    for layer in getattr(frame, "layers", []) or []:
                        sidx = getattr(layer, "sprite_index", -1)
                        if sidx is None or sidx < 0:
                            continue
                        if getattr(layer, "sprite_type", 0) == 1:
                            sidx += indexed_count
                        if 0 <= sidx < total:
                            return a_idx
        except Exception:
            pass
        return 0

    # ==============================================================================
    # Canvas preview + ActEditor-like controls
    # ==============================================================================
    def _on_fixed_origin_toggled(self, checked: bool):
        self.preview_canvas.set_fixed_origin(bool(checked))
        if self._act_preview_act and self._act_preview_sprite:
            self._render_act_preview_frame()

    def _on_act_spr_only_toggled(self, checked: bool):
        self._act_selected_spr_idx = None
        self._render_act_preview_frame()

    def _on_act_frame_slider_changed(self, value: int):
        if not self._act_preview_sprite:
            return
        total = self._act_preview_sprite.get_total_frames()
        if total <= 0:
            return
        v = max(0, min(int(value), total - 1))
        self._act_selected_spr_idx = v
        self._update_act_frame_label()
        self._select_thumbnail_index(v, from_slider=True)
        self._render_selected_spr_frame_only(v)

        # If user scrubs while playing, stop playback (ActEditor-like behavior)
        if getattr(self, "_act_preview_playing", False):
            self._act_preview_playing = False
            try:
                self._act_preview_timer.stop()
            except Exception:
                pass
            try:
                self.act_play_btn.setText("▶ Play")
            except Exception:
                pass

    def _on_act_thumbnail_selected(self):
        if not self._act_preview_sprite:
            return
        items = self.act_thumb_strip.selectedItems()
        if not items:
            return
        idx = items[0].data(Qt.ItemDataRole.UserRole)
        if idx is None:
            return
        try:
            idx = int(idx)
        except Exception:
            return
        self._act_selected_spr_idx = idx
        self._update_act_frame_label()
        self.act_frame_slider.blockSignals(True)
        self.act_frame_slider.setValue(idx)
        self.act_frame_slider.blockSignals(False)
        self._render_selected_spr_frame_only(idx)

        # If user clicks a thumbnail while playing, stop playback
        if getattr(self, "_act_preview_playing", False):
            self._act_preview_playing = False
            try:
                self._act_preview_timer.stop()
            except Exception:
                pass
            try:
                self.act_play_btn.setText("▶ Play")
            except Exception:
                pass

    def _update_act_frame_label(self):
        if not self._act_preview_sprite:
            self.act_frame_label.setText("0 / 0")
            return
        total = int(self._act_preview_sprite.get_total_frames() or 0)
        cur = int(self._act_selected_spr_idx or 0)
        if total <= 0:
            self.act_frame_label.setText("0 / 0")
        else:
            self.act_frame_label.setText(f"{cur} / {max(0, total - 1)}")

    def _select_thumbnail_index(self, idx: int, from_slider: bool = False):
        if idx < 0 or idx >= self.act_thumb_strip.count():
            return
        self.act_thumb_strip.blockSignals(True)
        self.act_thumb_strip.setCurrentRow(idx)
        self.act_thumb_strip.blockSignals(False)
        item = self.act_thumb_strip.item(idx)
        if item:
            self.act_thumb_strip.scrollToItem(item)

    def _sync_act_timeline_and_thumbs_on_load(self):
        if not self._act_preview_sprite:
            self.act_frame_slider.setMinimum(0)
            self.act_frame_slider.setMaximum(0)
            self.act_thumb_strip.clear()
            self.act_frame_label.setText("0 / 0")
            return

        total = int(self._act_preview_sprite.get_total_frames() or 0)
        if total <= 0:
            self.act_frame_slider.setMinimum(0)
            self.act_frame_slider.setMaximum(0)
            self.act_thumb_strip.clear()
            self.act_frame_label.setText("0 / 0")
            return

        self.act_frame_slider.blockSignals(True)
        self.act_frame_slider.setMinimum(0)
        self.act_frame_slider.setMaximum(total - 1)
        self.act_frame_slider.setValue(0)
        self.act_frame_slider.blockSignals(False)

        self._act_selected_spr_idx = 0
        self._update_act_frame_label()

        self._act_thumb_icon_cache.clear()
        self.act_thumb_strip.clear()
        self._act_thumb_pending = list(range(total))
        for i in range(total):
            it = QListWidgetItem(str(i))
            it.setData(Qt.ItemDataRole.UserRole, i)
            it.setToolTip(f"SPR frame {i}")
            self.act_thumb_strip.addItem(it)
        self._act_thumb_timer.stop()
        self._act_thumb_timer.start(5)

        self._select_thumbnail_index(0)

        # IMPORTANT: default to 1:1 on load (user requested)
        self.preview_canvas.reset_view()

    def _build_thumbnails_tick(self):
        if not self._act_preview_sprite or not PIL_AVAILABLE:
            self._act_thumb_timer.stop()
            return
        if not self._act_thumb_pending:
            self._act_thumb_timer.stop()
            return

        batch = 12
        total = int(self._act_preview_sprite.get_total_frames() or 0)
        for _ in range(batch):
            if not self._act_thumb_pending:
                break
            idx = self._act_thumb_pending.pop(0)
            if idx < 0 or idx >= total:
                continue
            if idx in self._act_thumb_icon_cache:
                continue
            try:
                pil_img = self._act_preview_sprite.get_frame_image(idx)
                if pil_img is None:
                    continue
                thumb = pil_img.convert("RGBA")
                thumb.thumbnail((48, 48), Image.Resampling.NEAREST)
                pm = self._pil_to_qpixmap(thumb)
                ico = QIcon(pm)
                self._act_thumb_icon_cache[idx] = ico
                item = self.act_thumb_strip.item(idx)
                if item:
                    item.setIcon(ico)
            except Exception:
                continue

    def _render_selected_spr_frame_only(self, spr_idx: int):
        if not self._act_preview_sprite or not PIL_AVAILABLE:
            return
        total = int(self._act_preview_sprite.get_total_frames() or 0)
        if spr_idx < 0 or spr_idx >= total:
            return
        try:
            pil_img = self._act_preview_sprite.get_frame_image(spr_idx)
            if pil_img is None:
                self.preview_canvas.set_pixmap(None)
                return
            pm = self._pil_to_qpixmap(pil_img.convert("RGBA"))
            self.preview_canvas.set_pixmap(pm)
            # Default to 1:1 (user requested). Fit is manual.
            self.preview_canvas.reset_view()
        except Exception as e:
            if self._debug_mode:
                print(f"[DEBUG] SPR frame render error: {e}")

    def _open_sprite_sheet_viewer(self):
        if not self._act_preview_sprite or not PIL_AVAILABLE:
            QMessageBox.information(self, "Sprite Sheet", "No SPR loaded (preview an ACT with matching SPR first).")
            return
        total = int(self._act_preview_sprite.get_total_frames() or 0)
        if total <= 0:
            QMessageBox.information(self, "Sprite Sheet", "SPR has 0 frames.")
            return
        try:
            cell = 64
            cols = 12
            rows = (total + cols - 1) // cols
            sheet = Image.new("RGBA", (cols * cell, rows * cell), (0, 0, 0, 0))
            for i in range(total):
                img = self._act_preview_sprite.get_frame_image(i)
                if img is None:
                    continue
                t = img.convert("RGBA")
                t.thumbnail((cell, cell), Image.Resampling.NEAREST)
                x = (i % cols) * cell + (cell - t.width) // 2
                y = (i // cols) * cell + (cell - t.height) // 2
                sheet.alpha_composite(t, (x, y))

            pm = self._pil_to_qpixmap(sheet)
            dlg = QDialog(self)
            dlg.setWindowTitle("Sprite Sheet Viewer (SPR Frames)")
            dlg.resize(900, 600)
            v = QVBoxLayout(dlg)
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            lbl = QLabel()
            lbl.setPixmap(pm)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            sa.setWidget(lbl)
            v.addWidget(sa)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Sprite Sheet", f"Failed to build sprite sheet:\n{e}")

    def _pil_to_qpixmap(self, pil_img: 'Image.Image') -> QPixmap:
        if pil_img is None:
            return QPixmap()
        img = pil_img.convert("RGBA")
        w, h = img.size
        buf = img.tobytes("raw", "RGBA")
        qimg = QImage(buf, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
        return QPixmap.fromImage(qimg)

    def _render_act_frame_pil(self, action_idx: int, act_frame_idx: int, fixed_origin: bool = False) -> Optional['Image.Image']:
        if not (self._act_preview_act and self._act_preview_sprite and PIL_AVAILABLE):
            return None
        action = self._act_preview_act.get_action(action_idx)
        if not action or action.get_frame_count() <= 0:
            return None
        frame = action.get_frame(act_frame_idx)
        if not frame:
            return None

        indexed_count = self._act_preview_sprite.get_indexed_count()
        total_frames = self._act_preview_sprite.get_total_frames()

        rendered = []
        min_x = 10**9
        min_y = 10**9
        max_x = -10**9
        max_y = -10**9

        for layer in getattr(frame, "layers", []) or []:
            sprite_idx = getattr(layer, "sprite_index", -1)
            if sprite_idx is None or sprite_idx < 0:
                continue
            if getattr(layer, "sprite_type", 0) == 1:
                sprite_idx += indexed_count
            if sprite_idx < 0 or sprite_idx >= total_frames:
                continue

            img = self._act_frame_cache.get(sprite_idx)
            if img is None:
                try:
                    img = self._act_preview_sprite.get_frame_image(sprite_idx)
                except Exception:
                    img = None
                if img is not None:
                    self._act_frame_cache[sprite_idx] = img
            if img is None:
                continue

            img = self._apply_layer_transforms(img, layer)
            left = int(getattr(layer, "x", 0) - (img.width // 2))
            top = int(getattr(layer, "y", 0) - (img.height // 2))
            right = left + img.width
            bottom = top + img.height

            min_x = min(min_x, left)
            min_y = min(min_y, top)
            max_x = max(max_x, right)
            max_y = max(max_y, bottom)
            rendered.append((img, left, top, sprite_idx, getattr(layer, "sprite_type", 0)))

        if not rendered:
            return None

        pad = 10
        if fixed_origin:
            canvas_w, canvas_h = 512, 512
            origin_x = canvas_w // 2
            origin_y = canvas_h // 2
            canvas = Image.new("RGBA", (canvas_w, canvas_h), (60, 60, 60, 255))
        else:
            canvas_w = max(1, int(max_x - min_x) + pad * 2)
            canvas_h = max(1, int(max_y - min_y) + pad * 2)
            origin_x = -min_x + pad
            origin_y = -min_y + pad
            canvas = Image.new("RGBA", (canvas_w, canvas_h), (60, 60, 60, 255))

        if ImageDraw:
            draw_bg = ImageDraw.Draw(canvas)
            tile = 16
            c1 = (55, 55, 55, 255)
            c2 = (75, 75, 75, 255)
            for y in range(0, canvas_h, tile):
                for x in range(0, canvas_w, tile):
                    draw_bg.rectangle([x, y, x + tile - 1, y + tile - 1],
                                      fill=(c1 if ((x // tile) + (y // tile)) % 2 == 0 else c2))
            if fixed_origin:
                draw_bg.line([origin_x - 12, origin_y, origin_x + 12, origin_y], fill=(220, 220, 220, 180))
                draw_bg.line([origin_x, origin_y - 12, origin_x, origin_y + 12], fill=(220, 220, 220, 180))

        for img, left, top, sprite_idx, spr_type in rendered:
            x = int(origin_x + left)
            y = int(origin_y + top)
            canvas.alpha_composite(img, (x, y))
            if self._act_debug_overlay_enabled and ImageDraw:
                d = ImageDraw.Draw(canvas)
                label = f"{sprite_idx} ({'RGBA' if spr_type == 1 else 'IDX'})"
                d.rectangle([x, y, x + img.width, y + img.height], outline=(255, 255, 0, 200))
                d.text((x + 2, y + 2), label, fill=(255, 255, 0, 220))

        return canvas
    
    def _precache_sprite_frames(self, count: int):
        """Pre-cache sprite frames for smoother preview."""
        if not self._act_preview_sprite:
            return
        
        if self._debug_mode:
            print(f"[DEBUG] Pre-caching {count} sprite frames...")
        
        cached = 0
        for i in range(min(count, self._act_preview_sprite.get_total_frames())):
            if i not in self._act_frame_cache:
                try:
                    img = self._act_preview_sprite.get_frame_image(i)
                    if img:
                        self._act_frame_cache[i] = img
                        cached += 1
                except Exception as e:
                    if self._debug_mode:
                        print(f"[DEBUG] Failed to cache frame {i}: {e}")
        
        if self._debug_mode:
            print(f"[DEBUG] Cached {cached} frames")
    
    def _reset_act_preview(self):
        """Reset ACT preview state."""
        self._act_preview_timer.stop()
        self._act_preview_act = None
        self._act_preview_sprite = None
        self._act_preview_action_idx = 0
        self._act_preview_frame_idx = 0
        self._act_preview_playing = False
        self._act_preview_file_path = None
        self.act_action_combo.clear()
        self.act_play_btn.setText("▶ Play")
        self._act_delay_scale = 1.0
        self.act_delay_scale.setValue(1.0)
        self._act_debug_overlay_enabled = False
        self.act_debug_overlay.setChecked(False)
        self._act_frame_cache.clear()  # Clear cache when resetting
        self._act_selected_spr_idx = None
        self.act_frame_slider.blockSignals(True)
        self.act_frame_slider.setMinimum(0)
        self.act_frame_slider.setMaximum(0)
        self.act_frame_slider.setValue(0)
        self.act_frame_slider.blockSignals(False)
        self.act_frame_label.setText("0 / 0")
        self.act_thumb_strip.clear()
        self._act_thumb_pending = []
        self._act_thumb_icon_cache.clear()
        self._act_thumb_timer.stop()
        self.preview_canvas.set_pixmap(None)
    
    def _toggle_act_preview(self):
        """
        Fix: Play button not responsive.
        Root cause in the ActEditor-like patch: selecting/scrubbing sets _act_selected_spr_idx,
        and _render_act_preview_frame() then always renders SPR-only, so animation appears stuck.

        Behavior:
          - Press Play: clears SPR-only selection and starts ACT animation timer
          - Press Pause: stops timer (keeps current view)
        """
        if not (self._act_preview_act and self._act_preview_sprite):
            return

        playing = bool(getattr(self, "_act_preview_playing", False))
        if not playing:
            # Start playing: ensure we are not in "SPR frame only" locked state
            self._act_selected_spr_idx = None
            self.act_show_spr_only.blockSignals(True)
            self.act_show_spr_only.setChecked(False)
            self.act_show_spr_only.blockSignals(False)

            self._act_preview_playing = True
            self.act_play_btn.setText("⏸ Pause")
            # Timer tick (existing _advance_act_preview_frame should advance + render)
            self._schedule_act_preview_frame()
            # Render immediately so user sees responsiveness
            self._render_act_preview_frame()
        else:
            # Pause
            self._act_preview_playing = False
            self.act_play_btn.setText("▶ Play")
            self._act_preview_timer.stop()
    
    def _on_act_delay_scale_changed(self, value: float):
        """Handle ACT delay scale change."""
        self._act_delay_scale = float(value)
        if self._act_preview_playing:
            self._schedule_act_preview_frame()
    
    def _on_act_debug_toggled(self, checked: bool):
        """Handle ACT debug overlay toggle."""
        self._act_debug_overlay_enabled = checked
        self._render_act_preview_frame()
    
    def _on_act_action_changed(self, index: int):
        """Handle ACT action dropdown change."""
        if index < 0 or not self._act_preview_act:
            return
        
        self._act_preview_action_idx = self.act_action_combo.currentData() or 0
        self._act_preview_frame_idx = 0
        self._render_act_preview_frame()
    
    def _advance_act_preview_frame(self):
        """Advance ACT preview to next frame."""
        if not self._act_preview_act:
            return
        
        action = self._act_preview_act.get_action(self._act_preview_action_idx)
        if not action or action.get_frame_count() == 0:
            return
        
        self._act_preview_frame_idx = (self._act_preview_frame_idx + 1) % action.get_frame_count()
        self._render_act_preview_frame()
        if self._act_preview_playing:
            self._schedule_act_preview_frame()
    
    def _schedule_act_preview_frame(self):
        """Schedule next ACT preview frame based on delay."""
        action = self._act_preview_act.get_action(self._act_preview_action_idx)
        if not action or action.get_frame_count() == 0:
            return
        
        frame = action.get_frame(self._act_preview_frame_idx)
        delay = int(getattr(frame, "delay", 0)) if frame else 0
        if delay <= 0:
            delay = 100  # Default 100ms if no delay specified
        delay = int(delay * self._act_delay_scale)
        if delay <= 0:
            delay = 1
        self._act_preview_timer.start(delay)
    
    def _render_act_preview_frame(self):
        """Render current ACT preview frame to the CanvasPreviewWidget (ActEditor-like)."""
        if not (self._act_preview_act and self._act_preview_sprite):
            return

        if not PIL_AVAILABLE:
            self.file_info.setText(self.file_info.text() + "\n\nPIL not available — preview disabled")
            self.preview_canvas.set_pixmap(None)
            return

        if self._act_selected_spr_idx is not None:
            self._render_selected_spr_frame_only(int(self._act_selected_spr_idx))
            return

        action = self._act_preview_act.get_action(self._act_preview_action_idx)
        if not action or action.get_frame_count() == 0:
            self.preview_canvas.set_pixmap(None)
            return

        if self._act_preview_frame_idx < 0 or self._act_preview_frame_idx >= action.get_frame_count():
            self.preview_canvas.set_pixmap(None)
            return

        fixed_origin = bool(self.fixed_origin_check.isChecked())
        pil_canvas = self._render_act_frame_pil(self._act_preview_action_idx, self._act_preview_frame_idx, fixed_origin=fixed_origin)
        if pil_canvas is None:
            self.preview_canvas.set_pixmap(None)
            return
        pm = self._pil_to_qpixmap(pil_canvas)
        self.preview_canvas.set_pixmap(pm)
        # Default to 1:1 (user requested). Do not auto-fit during preview/animation.
        # Users can press Fit manually anytime.
    
    def _apply_layer_transforms(self, img: Image.Image, layer) -> Image.Image:
        """Apply layer transforms (width/height override, mirror, scale, rotation, color tint) to image."""
        # NOTE: ACT v2.5 stores width/height fields, but GRFEditor/ActEditor override
        # them with the real sprite dimensions for rendering. Resizing here causes distortion.

        # Mirror
        if getattr(layer, "mirror", False):
            img = ImageOps.mirror(img)
        
        # Scale
        scale_x = getattr(layer, "scale_x", 1.0)
        scale_y = getattr(layer, "scale_y", 1.0)
        if scale_x != 1.0 or scale_y != 1.0:
            new_w = max(1, int(round(img.width * float(scale_x))))
            new_h = max(1, int(round(img.height * float(scale_y))))
            img = img.resize((new_w, new_h), resample=Image.Resampling.NEAREST)
        
        # Rotation (degrees)
        rotation = int(getattr(layer, "rotation", 0) or 0)
        if rotation:
            img = img.rotate(-rotation, expand=True, resample=Image.Resampling.NEAREST)
        
        # Color tint (RGBA)
        color = getattr(layer, "color", (255, 255, 255, 255))
        if color and color != (255, 255, 255, 255):
            img = self._apply_color_tint(img, color)
        
        return img
    
    def _apply_color_tint(self, img: Image.Image, color: tuple) -> Image.Image:
        """Apply color tint to image."""
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        r_t, g_t, b_t, a_t = color
        r, g, b, a = img.split()
        r = r.point(lambda p: (p * r_t) // 255)
        g = g.point(lambda p: (p * g_t) // 255)
        b = b.point(lambda p: (p * b_t) // 255)
        if a_t < 255:
            a = a.point(lambda p: (p * a_t) // 255)
        return Image.merge("RGBA", (r, g, b, a))

    def _preview_file_sync(self, file_path: str):
        """Preview a file synchronously (for fast file types)."""
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

            # Preview based on file type - with individual error handling
            try:
                if ext in ('.bmp', '.jpg', '.jpeg', '.png', '.tga') and PIL_AVAILABLE:
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
        """Preview SPR sprite file with timeout protection and progress feedback."""
        # Show loading indicator immediately
        self.preview_label.setText("Loading SPR preview...")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        QApplication.processEvents()  # Force UI update
        
        # Check PIL availability
        if not PIL_AVAILABLE:
            error_msg = "⚠️ Pillow (PIL) not installed\n\n"
            error_msg += "Image preview is disabled.\n"
            error_msg += "Install Pillow with: pip install Pillow"
            self.preview_label.setText(error_msg)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            return

        if not self.spr_parser:
            error_msg = "⚠️ SPR Parser not available"
            self.preview_label.setText(error_msg)
            return

        try:
            # Quick validation before parsing
            if len(data) < 8:
                self.preview_label.setText("❌ SPR file too small (< 8 bytes)")
                return
            
            # Check signature
            if data[0:2] != b'SP':
                self.preview_label.setText(f"❌ Invalid SPR signature: {data[0:2]}")
                self._preview_hex(data)
                return
            
            # Parse SPR
            self.preview_label.setText("Parsing SPR structure...")
            QApplication.processEvents()
            
            sprite = self.spr_parser.load_from_bytes(data)
            
            # Handle parse failure
            if sprite is None:
                error_msg = "❌ SPR Parse Failed\n\n"
                error_msg += "The SPR file could not be parsed.\n"
                error_msg += "Possible reasons:\n"
                error_msg += "  • File is corrupted\n"
                error_msg += "  • Invalid format or version\n"
                error_msg += "  • Data is truncated\n\n"
                error_msg += "Showing hex dump:"
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
            
            # Update status before rendering (rendering can be slow without numpy)
            self.preview_label.setText(f"Rendering frame 1/{total_frames}...")
            QApplication.processEvents()
            
            # Try to render first frame
            try:
                img = sprite.get_frame_image(0)
                if img and PIL_AVAILABLE:
                    self._display_image(img)
                    # Update file info with sprite details
                    info = self.file_info.text()
                    info += f"\n\nSPR Details:\n"
                    info += f"Frames: {total_frames}\n"
                    info += f"Indexed: {sprite.get_indexed_count()}\n"
                    info += f"RGBA: {sprite.get_rgba_count()}"
                    if total_frames > 0:
                        frame = sprite.get_frame(0)
                        if frame:
                            info += f"\nFrame 0: {frame.width}x{frame.height}"
                    self.file_info.setText(info)
                    return
                else:
                    error_msg = f"SPR: {total_frames} frames\n"
                    error_msg += "⚠️ Frame rendering returned None\n"
                    error_msg += "(Frame may be empty or corrupted)"
                    self.preview_label.setText(error_msg)
                    
            except Exception as img_error:
                error_msg = f"SPR: {total_frames} frames\n"
                error_msg += f"⚠️ Render error: {str(img_error)[:100]}"
                self.preview_label.setText(error_msg)
                if self._debug_mode:
                    import traceback
                    print(f"[DEBUG] SPR render error: {traceback.format_exc()}")
                
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

