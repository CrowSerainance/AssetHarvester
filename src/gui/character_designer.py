# ==============================================================================
# CHARACTER DESIGNER MODULE
# ==============================================================================
# Visual character designer for Ragnarok Online sprites.
#
# This module focuses on VISUAL PREVIEW and COMPOSITION of character sprites.
# It is separate from the ACT/SPR Editor which handles binary file editing.
#
# FEATURES:
#   1. Visual sprite composition and preview
#   2. Side-by-side comparison view (vanilla vs custom)
#   3. Auto-detect custom sprites (database integration)
#   4. Batch export (all headgear/jobs as sprite sheets)
#   5. Item database lookup (headgear names)
#
# The designer works with extracted RO data files. Point it to a folder
# containing the extracted 'data/sprite' directory structure from GRF files.
#
# Dependencies:
#   - PyQt6 for the GUI
#   - Pillow for image manipulation
#   - SPR/ACT parsers (included in this package)
# ==============================================================================

import os
import sys
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

# ==============================================================================
# PyQt6 IMPORTS
# ==============================================================================
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QGroupBox, QLabel, QPushButton, QComboBox, QSpinBox,
        QSlider, QCheckBox, QLineEdit, QFileDialog, QFrame,
        QSplitter, QScrollArea, QTabWidget, QListWidget,
        QListWidgetItem, QMessageBox, QProgressDialog,
        QDialog, QDialogButtonBox, QTextEdit, QTableWidget,
        QTableWidgetItem, QHeaderView, QAbstractItemView,
        QMenu, QInputDialog, QTreeWidget, QTreeWidgetItem
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize, QThread
    from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QFont, QAction
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("[ERROR] PyQt6 is not installed")

# ==============================================================================
# PIL IMPORT
# ==============================================================================
try:
    from PIL import Image
    from PIL.ImageQt import ImageQt
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[WARN] Pillow not installed. Image rendering disabled.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from src.parsers.spr_parser import SPRParser, SPRSprite, load_palette
    from src.parsers.act_parser import ACTParser, ACTData, ActionIndex
    from src.parsers.item_database import ItemDatabase, get_item_database
    from src.parsers.sprite_catalog import SpriteCatalog
    from src.parsers.batch_exporter import BatchExporter, SpritesheetConfig, ExportResult
    PARSERS_AVAILABLE = True
except ImportError:
    PARSERS_AVAILABLE = False
    print("[WARN] SPR/ACT parsers not available")

# Try to import database for custom detection
try:
    from src.core.database import Database
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False


# ==============================================================================
# JOB DATA
# ==============================================================================

JOB_DATA = {
    # Basic Jobs
    "Novice": {"folder": "초보자", "id": 0, "gender_split": True},
    "Swordman": {"folder": "검사", "id": 1, "gender_split": True},
    "Mage": {"folder": "마법사", "id": 2, "gender_split": True},
    "Archer": {"folder": "궁수", "id": 3, "gender_split": True},
    "Acolyte": {"folder": "성직자", "id": 4, "gender_split": True},
    "Merchant": {"folder": "상인", "id": 5, "gender_split": True},
    "Thief": {"folder": "도둑", "id": 6, "gender_split": True},
    
    # 2-1 Jobs
    "Knight": {"folder": "기사", "id": 7, "gender_split": True},
    "Priest": {"folder": "프리스트", "id": 8, "gender_split": True},
    "Wizard": {"folder": "위저드", "id": 9, "gender_split": True},
    "Blacksmith": {"folder": "제철공", "id": 10, "gender_split": True},
    "Hunter": {"folder": "헌터", "id": 11, "gender_split": True},
    "Assassin": {"folder": "어세신", "id": 12, "gender_split": True},
    
    # 2-2 Jobs
    "Crusader": {"folder": "크루세이더", "id": 14, "gender_split": True},
    "Monk": {"folder": "몽크", "id": 15, "gender_split": True},
    "Sage": {"folder": "세이지", "id": 16, "gender_split": True},
    "Rogue": {"folder": "로그", "id": 17, "gender_split": True},
    "Alchemist": {"folder": "연금술사", "id": 18, "gender_split": True},
    "Bard": {"folder": "바드", "id": 19, "gender_split": False, "gender": "male"},
    "Dancer": {"folder": "무희", "id": 20, "gender_split": False, "gender": "female"},
    
    # Transcendent Jobs
    "Lord Knight": {"folder": "로드나이트", "id": 4008, "gender_split": True},
    "High Priest": {"folder": "하이프리스트", "id": 4009, "gender_split": True},
    "High Wizard": {"folder": "하이위저드", "id": 4010, "gender_split": True},
    "Whitesmith": {"folder": "화이트스미스", "id": 4011, "gender_split": True},
    "Sniper": {"folder": "스나이퍼", "id": 4012, "gender_split": True},
    "Assassin Cross": {"folder": "어쌔신 크로스", "id": 4013, "gender_split": True},
    "Paladin": {"folder": "팔라딘", "id": 4015, "gender_split": True},
    "Champion": {"folder": "챔피언", "id": 4016, "gender_split": True},
    "Professor": {"folder": "프로페서", "id": 4017, "gender_split": True},
    "Stalker": {"folder": "스토커", "id": 4018, "gender_split": True},
    "Creator": {"folder": "크리에이터", "id": 4019, "gender_split": True},
    "Clown": {"folder": "클라운", "id": 4020, "gender_split": False, "gender": "male"},
    "Gypsy": {"folder": "집시", "id": 4021, "gender_split": False, "gender": "female"},
}

ACTION_NAMES = {
    0: "Stand", 8: "Walk", 16: "Sit", 24: "Pick Up",
    32: "Ready (Combat)", 40: "Attack 1", 48: "Hurt",
    56: "Freeze", 64: "Dead", 72: "Cast",
    80: "Attack 2", 88: "Attack 3",
}

DIRECTION_NAMES = ["South", "SW", "West", "NW", "North", "NE", "East", "SE"]


# ==============================================================================
# SPRITE COMPOSITOR (Enhanced)
# ==============================================================================

class SpriteCompositor:
    """
    Composites multiple sprite layers to create a complete character render.
    Enhanced version with support for comparison and batch operations.
    """
    
    def __init__(self, resource_path: str = ""):
        self.resource_path = resource_path
        self.spr_parser = SPRParser() if PARSERS_AVAILABLE else None
        self.act_parser = ACTParser() if PARSERS_AVAILABLE else None
        self.cache: Dict[str, Tuple[SPRSprite, ACTData]] = {}
        
        # Current character state
        self.job = "Novice"
        self.gender = "male"
        self.head_id = 1
        self.hair_color = 0
        self.headgear_top = 0
        self.headgear_mid = 0
        self.headgear_low = 0
        self.weapon = 0
        self.shield = 0
        self.garment = 0
        self.body_palette = -1
    
    def set_resource_path(self, path: str):
        """
        Set the resource path and clear cache.
        
        Auto-detects if user selected the 'data' folder instead of parent.
        The path should be the folder CONTAINING 'data/sprite/', not 'data' itself.
        """
        # Normalize path
        path = os.path.normpath(path)
        
        # Auto-detect: if user selected 'data' folder, go up one level
        # Check if path ends with 'data' and contains 'sprite' subfolder
        if os.path.basename(path).lower() == 'data':
            sprite_check = os.path.join(path, 'sprite')
            if os.path.isdir(sprite_check):
                # User selected 'data' folder - go up one level
                path = os.path.dirname(path)
                print(f"[INFO] Auto-corrected path to parent: {path}")
        
        # Also check if data/sprite exists at expected location
        expected_sprite = os.path.join(path, 'data', 'sprite')
        if not os.path.isdir(expected_sprite):
            # Try alternative: maybe sprites are directly in path/sprite
            alt_sprite = os.path.join(path, 'sprite')
            if os.path.isdir(alt_sprite):
                print(f"[INFO] Found sprites at {alt_sprite} - adjusting paths")
        
        self.resource_path = path
        self.cache.clear()
        print(f"[INFO] Resource path set to: {path}")
    
    def get_sprite_path(self, sprite_type: str, sprite_id: int = 0) -> str:
        """
        Get the full path to a sprite file for comparison purposes.
        
        Args:
            sprite_type: 'body', 'head', 'headgear', 'weapon', 'shield'
            sprite_id: ID for headgear/weapon/shield
            
        Returns:
            Full path to the sprite file
        """
        gender_kr = "남" if self.gender == "male" else "여"
        
        if sprite_type == "body":
            job_data = JOB_DATA.get(self.job)
            if job_data:
                folder = job_data["folder"]
                return os.path.join(self.resource_path, 
                    f"data/sprite/인간족/몸통/{gender_kr}/{folder}_{gender_kr}.spr")
        
        elif sprite_type == "head":
            return os.path.join(self.resource_path,
                f"data/sprite/인간족/머리통/{gender_kr}/{self.head_id}_{gender_kr}.spr")
        
        elif sprite_type == "headgear":
            return os.path.join(self.resource_path,
                f"data/sprite/악세사리/{gender_kr}/{gender_kr}_{sprite_id}.spr")
        
        return ""
    
    def load_sprite(self, relative_path: str) -> Optional[Tuple[SPRSprite, ACTData]]:
        """
        Load a sprite and its action file.
        
        Args:
            relative_path: Path relative to resource folder (without extension)
                          Example: "data/sprite/인간족/몸통/남/초보자_남"
        
        Returns:
            Tuple of (SPRSprite, ACTData) or None if not found
        """
        if not self.spr_parser or not self.act_parser:
            print("[ERROR] Parsers not available")
            return None
        
        # Check cache first
        if relative_path in self.cache:
            return self.cache[relative_path]
        
        # Build full paths
        base_path = os.path.join(self.resource_path, relative_path)
        spr_path = base_path + ".spr"
        act_path = base_path + ".act"
        
        # Debug: show what we're looking for
        if not os.path.exists(spr_path):
            print(f"[DEBUG] SPR not found: {spr_path}")
            # Try to help diagnose the issue
            parent_dir = os.path.dirname(base_path)
            if os.path.isdir(parent_dir):
                print(f"[DEBUG] Parent folder exists: {parent_dir}")
                try:
                    files = os.listdir(parent_dir)[:5]  # Show first 5 files
                    print(f"[DEBUG] Sample files in folder: {files}")
                except:
                    pass
            else:
                print(f"[DEBUG] Parent folder NOT found: {parent_dir}")
            return None
        
        if not os.path.exists(act_path):
            print(f"[DEBUG] ACT not found: {act_path}")
            return None
        
        # Load the files
        sprite = self.spr_parser.load(spr_path)
        action = self.act_parser.load(act_path)
        
        if sprite and action:
            self.cache[relative_path] = (sprite, action)
            print(f"[DEBUG] Loaded: {relative_path}")
            return (sprite, action)
        else:
            print(f"[DEBUG] Failed to parse: {relative_path}")
        
        return None
    
    def get_body_path(self) -> str:
        """Get the sprite path for the current body."""
        job_data = JOB_DATA.get(self.job)
        if not job_data:
            return ""
        
        folder = job_data["folder"]
        gender_kr = "남" if self.gender == "male" else "여"
        return f"data/sprite/인간족/몸통/{gender_kr}/{folder}_{gender_kr}"
    
    def get_head_path(self) -> str:
        """Get the sprite path for the current head."""
        gender_kr = "남" if self.gender == "male" else "여"
        return f"data/sprite/인간족/머리통/{gender_kr}/{self.head_id}_{gender_kr}"
    
    def get_headgear_path(self, headgear_id: int) -> str:
        """Get the sprite path for a headgear."""
        gender_kr = "남" if self.gender == "male" else "여"
        return f"data/sprite/악세사리/{gender_kr}/{gender_kr}_{headgear_id}"
    
    def render_frame(self, action_index: int = 0, 
                     frame_index: int = 0,
                     direction: int = 0) -> Optional[Image.Image]:
        """Render a complete character frame."""
        if not PIL_AVAILABLE:
            return None
        
        actual_action = action_index + direction
        canvas_size = 500
        center = canvas_size // 2
        
        canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        
        # Load and draw body
        body_path = self.get_body_path()
        body_data = self.load_sprite(body_path)
        
        if body_data:
            sprite, action_data = body_data
            self._draw_sprite_layer(canvas, sprite, action_data, 
                                   actual_action, frame_index, center, center)
        
        # Load and draw head
        head_path = self.get_head_path()
        head_data = self.load_sprite(head_path)
        
        if head_data:
            sprite, action_data = head_data
            head_offset_x, head_offset_y = 0, 0
            
            if body_data:
                body_sprite, body_action = body_data
                body_act = body_action.get_action(actual_action)
                if body_act:
                    body_frame = body_act.get_frame(frame_index % body_act.get_frame_count())
                    if body_frame and body_frame.anchors:
                        anchor = body_frame.anchors[0]
                        head_offset_x = anchor.x
                        head_offset_y = anchor.y
            
            self._draw_sprite_layer(canvas, sprite, action_data,
                                   actual_action, frame_index,
                                   center + head_offset_x, 
                                   center + head_offset_y)
        
        # Draw headgear
        for hg_id in [self.headgear_low, self.headgear_mid, self.headgear_top]:
            if hg_id > 0:
                hg_path = self.get_headgear_path(hg_id)
                hg_data = self.load_sprite(hg_path)
                if hg_data:
                    sprite, action_data = hg_data
                    self._draw_sprite_layer(canvas, sprite, action_data,
                                           actual_action, frame_index,
                                           center, center)
        
        # Crop to content
        bbox = canvas.getbbox()
        if bbox:
            padding = 10
            x1, y1, x2, y2 = bbox
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = min(canvas_size, x2 + padding)
            y2 = min(canvas_size, y2 + padding)
            canvas = canvas.crop((x1, y1, x2, y2))
        
        return canvas
    
    def _draw_sprite_layer(self, canvas: Image.Image, 
                           sprite: SPRSprite, action_data: ACTData,
                           action_index: int, frame_index: int,
                           offset_x: int, offset_y: int):
        """Draw a sprite layer onto the canvas."""
        action = action_data.get_action(action_index)
        if not action:
            action = action_data.get_action(action_index % action_data.get_action_count())
        
        if not action:
            return
        
        frame = action.get_frame(frame_index % action.get_frame_count())
        if not frame:
            return
        
        for layer in frame.layers:
            sprite_idx = layer.sprite_index
            if sprite_idx < 0:
                continue
            
            if layer.sprite_type == 1:
                sprite_idx += sprite.get_indexed_count()
            
            img = sprite.get_frame_image(sprite_idx)
            if not img:
                continue
            
            if layer.mirror:
                img = img.transpose(Image.FLIP_LEFT_RIGHT)
            
            if layer.scale_x != 1.0 or layer.scale_y != 1.0:
                new_w = max(1, int(img.width * abs(layer.scale_x)))
                new_h = max(1, int(img.height * abs(layer.scale_y)))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            if layer.rotation != 0:
                img = img.rotate(-layer.rotation, expand=True, 
                               resample=Image.Resampling.BILINEAR)
            
            x = offset_x + layer.x - img.width // 2
            y = offset_y + layer.y - img.height // 2
            
            canvas.paste(img, (x, y), img)


# ==============================================================================
# BATCH EXPORT WORKER THREAD
# ==============================================================================

class BatchExportWorker(QThread):
    """Worker thread for batch export operations."""
    
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, exporter: BatchExporter, operation: str, **kwargs):
        super().__init__()
        self.exporter = exporter
        self.operation = operation
        self.kwargs = kwargs
        self._cancelled = False
    
    def cancel(self):
        """Request cancellation."""
        self._cancelled = True
    
    def run(self):
        try:
            result = None
            
            if self._cancelled:
                return
            
            if self.operation == "headgear":
                result = self.exporter.export_all_headgear(
                    self.kwargs.get('headgear_ids', []),
                    self.kwargs.get('gender', 'male'),
                    self._progress
                )
            
            elif self.operation == "headgear_sheet":
                result = self.exporter.export_headgear_spritesheet(
                    self.kwargs.get('headgear_ids', []),
                    self.kwargs.get('gender', 'male'),
                    self.kwargs.get('config'),
                    self._progress
                )
            
            elif self.operation == "job_sheet":
                result = self.exporter.export_job_spritesheet(
                    self.kwargs.get('job_name', 'Novice'),
                    self.kwargs.get('gender', 'male'),
                    self.kwargs.get('actions'),
                    self.kwargs.get('config'),
                    self._progress
                )
            
            elif self.operation == "all_jobs":
                result = self.exporter.export_all_jobs_preview(
                    self.kwargs.get('job_names', []),
                    self.kwargs.get('gender', 'male'),
                    self._progress
                )
            
            elif self.operation == "comparison":
                result = self.exporter.export_comparison_sheet(
                    self.kwargs.get('vanilla_compositor'),
                    self.kwargs.get('custom_compositor'),
                    self.kwargs.get('items', []),
                    self._progress
                )
            
            if not self._cancelled:
                self.finished.emit(result)
            
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))
    
    def _progress(self, current, total, message):
        """Progress callback - checks for cancellation."""
        if self._cancelled:
            return  # Stop processing if cancelled
        self.progress.emit(current, total, message)


# ==============================================================================
# CUSTOM SPRITE DETECTOR
# ==============================================================================

class CustomSpriteDetector:
    """
    Detects which sprites are custom vs vanilla.
    
    Integrates with the Asset Harvester comparison database to mark
    sprites as vanilla, modified, or new (custom).
    """
    
    def __init__(self, database=None, baseline: Dict = None):
        """
        Initialize detector.
        
        Args:
            database: Asset Harvester Database instance
            baseline: Dictionary of vanilla file hashes {path: hash}
        """
        self.database = database
        self.baseline = baseline or {}
        self.custom_cache: Dict[str, str] = {}  # path -> status
    
    def set_baseline(self, baseline: Dict):
        """Set vanilla baseline hashes."""
        self.baseline = baseline
        self.custom_cache.clear()
    
    def load_baseline_from_db(self, game_id: int):
        """Load baseline from database."""
        if self.database:
            try:
                vanilla_files = self.database.get_vanilla_files(game_id)
                self.baseline = {
                    f.path.lower(): f.hash_md5 
                    for f in vanilla_files
                }
                print(f"[INFO] Loaded {len(self.baseline)} vanilla file hashes")
            except Exception as e:
                print(f"[ERROR] Failed to load baseline: {e}")
    
    def check_sprite(self, sprite_path: str) -> str:
        """
        Check if a sprite is custom or vanilla.
        
        Args:
            sprite_path: Full path to sprite file
            
        Returns:
            Status: 'vanilla', 'modified', 'new', or 'unknown'
        """
        if not sprite_path:
            return 'unknown'
        
        # Check cache
        path_lower = sprite_path.lower()
        if path_lower in self.custom_cache:
            return self.custom_cache[path_lower]
        
        # Extract relative path
        # Look for 'data/' in path
        rel_path = path_lower
        data_idx = path_lower.find('data/')
        if data_idx >= 0:
            rel_path = path_lower[data_idx:]
        
        # Check against baseline
        if not self.baseline:
            return 'unknown'
        
        if rel_path not in self.baseline:
            # Not in vanilla = new custom content
            status = 'new'
        else:
            # In vanilla - need to check hash
            # For now, assume file exists = identical (would need hash check)
            if os.path.exists(sprite_path):
                status = 'vanilla'  # Simplified - would need actual hash comparison
            else:
                status = 'vanilla'
        
        self.custom_cache[path_lower] = status
        return status
    
    def get_custom_sprites(self, sprite_paths: List[str]) -> Dict[str, str]:
        """
        Check multiple sprites and return their status.
        
        Args:
            sprite_paths: List of sprite paths
            
        Returns:
            Dictionary of {path: status}
        """
        return {path: self.check_sprite(path) for path in sprite_paths}


# ==============================================================================
# COMPARISON VIEW WIDGET
# ==============================================================================

class ComparisonViewWidget(QWidget):
    """
    Side-by-side comparison view widget.
    
    Shows vanilla sprite on the left and custom sprite on the right.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.vanilla_compositor = None
        self.custom_compositor = None
        self.current_image_vanilla = None
        self.current_image_custom = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Build the UI."""
        layout = QVBoxLayout(self)
        
        # Path selectors
        paths_layout = QHBoxLayout()
        
        # Vanilla path
        vanilla_group = QGroupBox("Vanilla Data")
        vanilla_layout = QHBoxLayout(vanilla_group)
        self.vanilla_path_edit = QLineEdit()
        self.vanilla_path_edit.setPlaceholderText("Path to vanilla extracted data...")
        vanilla_layout.addWidget(self.vanilla_path_edit)
        vanilla_browse = QPushButton("Browse")
        vanilla_browse.clicked.connect(self._browse_vanilla)
        vanilla_layout.addWidget(vanilla_browse)
        paths_layout.addWidget(vanilla_group)
        
        # Custom path
        custom_group = QGroupBox("Custom Data")
        custom_layout = QHBoxLayout(custom_group)
        self.custom_path_edit = QLineEdit()
        self.custom_path_edit.setPlaceholderText("Path to custom/server extracted data...")
        custom_layout.addWidget(self.custom_path_edit)
        custom_browse = QPushButton("Browse")
        custom_browse.clicked.connect(self._browse_custom)
        custom_layout.addWidget(custom_browse)
        paths_layout.addWidget(custom_group)
        
        layout.addLayout(paths_layout)
        
        # Comparison view
        comparison_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Vanilla preview
        vanilla_preview = QGroupBox("Vanilla")
        vanilla_preview_layout = QVBoxLayout(vanilla_preview)
        self.vanilla_label = QLabel("No sprite loaded")
        self.vanilla_label.setMinimumSize(250, 300)
        self.vanilla_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.vanilla_label.setStyleSheet("""
            QLabel {
                background-color: #1a3d1a;
                border: 2px solid #2d5d2d;
                border-radius: 8px;
            }
        """)
        vanilla_preview_layout.addWidget(self.vanilla_label)
        self.vanilla_status = QLabel("Status: Unknown")
        vanilla_preview_layout.addWidget(self.vanilla_status)
        comparison_splitter.addWidget(vanilla_preview)
        
        # Custom preview
        custom_preview = QGroupBox("Custom")
        custom_preview_layout = QVBoxLayout(custom_preview)
        self.custom_label = QLabel("No sprite loaded")
        self.custom_label.setMinimumSize(250, 300)
        self.custom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.custom_label.setStyleSheet("""
            QLabel {
                background-color: #3d3d1a;
                border: 2px solid #5d5d2d;
                border-radius: 8px;
            }
        """)
        custom_preview_layout.addWidget(self.custom_label)
        self.custom_status = QLabel("Status: Unknown")
        custom_preview_layout.addWidget(self.custom_status)
        comparison_splitter.addWidget(custom_preview)
        
        layout.addWidget(comparison_splitter)
        
        # Difference indicator
        diff_layout = QHBoxLayout()
        self.diff_label = QLabel("")
        self.diff_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        diff_layout.addWidget(self.diff_label)
        diff_layout.addStretch()
        layout.addLayout(diff_layout)
    
    def _browse_vanilla(self):
        """Browse for vanilla data path."""
        path = QFileDialog.getExistingDirectory(self, "Select Vanilla Data Folder")
        if path:
            self.vanilla_path_edit.setText(path)
            self._update_vanilla_compositor()
    
    def _browse_custom(self):
        """Browse for custom data path."""
        path = QFileDialog.getExistingDirectory(self, "Select Custom Data Folder")
        if path:
            self.custom_path_edit.setText(path)
            self._update_custom_compositor()
    
    def _update_vanilla_compositor(self):
        """Update the vanilla compositor."""
        path = self.vanilla_path_edit.text()
        if path and os.path.isdir(path):
            if not self.vanilla_compositor:
                self.vanilla_compositor = SpriteCompositor()
            self.vanilla_compositor.set_resource_path(path)
    
    def _update_custom_compositor(self):
        """Update the custom compositor."""
        path = self.custom_path_edit.text()
        if path and os.path.isdir(path):
            if not self.custom_compositor:
                self.custom_compositor = SpriteCompositor()
            self.custom_compositor.set_resource_path(path)
    
    def set_character_state(self, job: str, gender: str, head_id: int,
                           headgear_top: int, headgear_mid: int, headgear_low: int):
        """Set character state on both compositors."""
        for comp in [self.vanilla_compositor, self.custom_compositor]:
            if comp:
                comp.job = job
                comp.gender = gender
                comp.head_id = head_id
                comp.headgear_top = headgear_top
                comp.headgear_mid = headgear_mid
                comp.headgear_low = headgear_low
    
    def render_comparison(self, action_index: int = 0, 
                         frame_index: int = 0, direction: int = 0):
        """Render both vanilla and custom sprites."""
        # Render vanilla
        if self.vanilla_compositor and self.vanilla_compositor.resource_path:
            img = self.vanilla_compositor.render_frame(action_index, frame_index, direction)
            if img:
                self._display_image(self.vanilla_label, img)
                self.current_image_vanilla = img
                self.vanilla_status.setText("Status: ✅ Loaded")
                self.vanilla_status.setStyleSheet("color: #4caf50;")
            else:
                self.vanilla_label.setText("Sprite not found")
                self.vanilla_status.setText("Status: ❌ Missing")
                self.vanilla_status.setStyleSheet("color: #f44336;")
                self.current_image_vanilla = None
        else:
            self.vanilla_label.setText("Set vanilla path")
            self.current_image_vanilla = None
        
        # Render custom
        if self.custom_compositor and self.custom_compositor.resource_path:
            img = self.custom_compositor.render_frame(action_index, frame_index, direction)
            if img:
                self._display_image(self.custom_label, img)
                self.current_image_custom = img
                self.custom_status.setText("Status: ✅ Loaded")
                self.custom_status.setStyleSheet("color: #4caf50;")
            else:
                self.custom_label.setText("Sprite not found")
                self.custom_status.setText("Status: ❌ Missing")
                self.custom_status.setStyleSheet("color: #f44336;")
                self.current_image_custom = None
        else:
            self.custom_label.setText("Set custom path")
            self.current_image_custom = None
        
        # Update difference indicator
        self._update_diff_indicator()
    
    def _display_image(self, label: QLabel, img: Image.Image):
        """Display PIL image in a QLabel."""
        if not PIL_AVAILABLE:
            return
        
        # Scale up for visibility
        zoom = 2.0
        new_size = (int(img.width * zoom), int(img.height * zoom))
        display_img = img.resize(new_size, Image.Resampling.NEAREST)
        
        qim = ImageQt(display_img)
        pixmap = QPixmap.fromImage(qim)
        label.setPixmap(pixmap)
    
    def _update_diff_indicator(self):
        """Update the difference indicator."""
        if not self.current_image_vanilla and not self.current_image_custom:
            self.diff_label.setText("")
            return
        
        if not self.current_image_vanilla:
            self.diff_label.setText("⭐ NEW: Custom sprite not in vanilla!")
            self.diff_label.setStyleSheet("color: #2196f3; font-weight: bold;")
        elif not self.current_image_custom:
            self.diff_label.setText("❌ Missing: No custom version found")
            self.diff_label.setStyleSheet("color: #ff9800; font-weight: bold;")
        else:
            # Both exist - compare sizes (simple comparison)
            v_size = self.current_image_vanilla.size
            c_size = self.current_image_custom.size
            
            if v_size != c_size:
                self.diff_label.setText(f"⚠️ DIFFERENT: Size changed ({v_size} → {c_size})")
                self.diff_label.setStyleSheet("color: #ff9800; font-weight: bold;")
            else:
                # Would need pixel comparison for accurate diff
                self.diff_label.setText("✓ Same size (may still differ in content)")
                self.diff_label.setStyleSheet("color: #4caf50; font-weight: bold;")


# ==============================================================================
# BATCH EXPORT DIALOG
# ==============================================================================

class BatchExportDialog(QDialog):
    """Dialog for batch export options."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Export")
        self.setMinimumWidth(500)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Export type selection
        type_group = QGroupBox("Export Type")
        type_layout = QVBoxLayout(type_group)
        
        self.export_type = QComboBox()
        self.export_type.addItems([
            "All Headgear (Individual PNGs)",
            "Headgear Sprite Sheet",
            "Job Animation Sheet",
            "All Jobs Preview",
            "Comparison Sheet"
        ])
        type_layout.addWidget(self.export_type)
        layout.addWidget(type_group)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QGridLayout(options_group)
        
        options_layout.addWidget(QLabel("Gender:"), 0, 0)
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Male", "Female", "Both"])
        options_layout.addWidget(self.gender_combo, 0, 1)
        
        options_layout.addWidget(QLabel("Columns:"), 1, 0)
        self.columns_spin = QSpinBox()
        self.columns_spin.setRange(1, 20)
        self.columns_spin.setValue(8)
        options_layout.addWidget(self.columns_spin, 1, 1)
        
        options_layout.addWidget(QLabel("Cell Size:"), 2, 0)
        self.cell_size_spin = QSpinBox()
        self.cell_size_spin.setRange(50, 300)
        self.cell_size_spin.setValue(100)
        options_layout.addWidget(self.cell_size_spin, 2, 1)
        
        self.include_labels = QCheckBox("Include Labels")
        self.include_labels.setChecked(True)
        options_layout.addWidget(self.include_labels, 3, 0, 1, 2)
        
        layout.addWidget(options_group)
        
        # Output path
        output_group = QGroupBox("Output")
        output_layout = QHBoxLayout(output_group)
        
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Select output folder...")
        output_layout.addWidget(self.output_path)
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(browse_btn)
        
        layout.addWidget(output_group)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.output_path.setText(path)
    
    def get_config(self) -> dict:
        """Get export configuration."""
        return {
            'export_type': self.export_type.currentIndex(),
            'gender': ['male', 'female', 'both'][self.gender_combo.currentIndex()],
            'columns': self.columns_spin.value(),
            'cell_size': self.cell_size_spin.value(),
            'include_labels': self.include_labels.isChecked(),
            'output_path': self.output_path.text()
        }


# ==============================================================================
# CHARACTER DESIGNER WIDGET (Enhanced)
# ==============================================================================

class CharacterDesignerWidget(QWidget):
    """
    Visual Character Designer for Ragnarok Online sprites.
    
    Focuses on visual preview, composition, and comparison of character sprites.
    For binary editing of ACT/SPR files, use the separate ACT/SPR Editor tab.
    
    Features:
    1. Visual sprite composition and preview
    2. Side-by-side comparison view (vanilla vs custom)
    3. Auto-detect custom sprites (database integration)
    4. Batch export (all headgear/jobs as sprite sheets)
    5. Item database lookup (headgear names)
    """
    
    sprite_loaded = pyqtSignal(str)
    export_complete = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize components
        self.compositor = SpriteCompositor()
        self.item_db = get_item_database() if PARSERS_AVAILABLE else None
        # CustomSpriteDetector will be connected to database/baseline by parent MainWindow
        self.custom_detector = CustomSpriteDetector()
        self.sprite_catalog = None

        # Note: ACT/SPR Editor has been moved to a standalone top-level tab

        # Animation state
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._on_animation_tick)
        self.current_frame = 0
        self.is_animating = False

        # Batch export
        self.batch_worker = None
        
        # Build UI
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Build the user interface."""
        main_layout = QVBoxLayout(self)
        
        # Create tab widget for different views
        self.view_tabs = QTabWidget()
        
        # Tab 1: Standard Designer
        designer_tab = QWidget()
        self._setup_designer_tab(designer_tab)
        self.view_tabs.addTab(designer_tab, "🎨 Designer")
        
        # Tab 2: Comparison View
        self.comparison_view = ComparisonViewWidget()
        self.view_tabs.addTab(self.comparison_view, "⚖️ Compare")
        
        # Tab 3: Batch Export
        batch_tab = QWidget()
        self._setup_batch_tab(batch_tab)
        self.view_tabs.addTab(batch_tab, "📦 Batch Export")
        
        # Tab 4: Item Browser
        browser_tab = QWidget()
        self._setup_browser_tab(browser_tab)
        self.view_tabs.addTab(browser_tab, "🔍 Item Browser")

        # Note: ACT/SPR Editor has been moved to a standalone top-level tab

        main_layout.addWidget(self.view_tabs)
    
    def _setup_designer_tab(self, tab: QWidget):
        """Setup the main designer tab."""
        main_layout = QHBoxLayout(tab)

        # === LEFT PANEL: Controls ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(320)
        left_panel.setMaximumWidth(400)
        
        # Resource Path
        path_group = QGroupBox("Resource Path")
        path_layout = QHBoxLayout(path_group)
        
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Path to extracted RO data...")
        path_layout.addWidget(self.path_edit)
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._on_browse_path)
        path_layout.addWidget(browse_btn)
        
        left_layout.addWidget(path_group)
        
        # Character Settings
        char_group = QGroupBox("Character")
        char_layout = QGridLayout(char_group)
        char_layout.setColumnStretch(1, 1)  # Make input column expand

        char_layout.addWidget(QLabel("Job:"), 0, 0)
        self.job_combo = QComboBox()
        self.job_combo.addItems(sorted(JOB_DATA.keys()))
        self.job_combo.setCurrentText("Novice")
        self.job_combo.setMinimumWidth(120)
        char_layout.addWidget(self.job_combo, 0, 1)

        char_layout.addWidget(QLabel("Gender:"), 1, 0)
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Male", "Female"])
        self.gender_combo.setMinimumWidth(120)
        char_layout.addWidget(self.gender_combo, 1, 1)

        char_layout.addWidget(QLabel("Head:"), 2, 0)
        self.head_spin = QSpinBox()
        self.head_spin.setRange(1, 30)
        self.head_spin.setValue(1)
        self.head_spin.setMinimumWidth(80)
        char_layout.addWidget(self.head_spin, 2, 1)

        char_layout.addWidget(QLabel("Hair Color:"), 3, 0)
        self.hair_spin = QSpinBox()
        self.hair_spin.setRange(0, 8)
        self.hair_spin.setValue(0)
        self.hair_spin.setMinimumWidth(80)
        char_layout.addWidget(self.hair_spin, 3, 1)

        left_layout.addWidget(char_group)
        
        # Equipment (with item names!)
        equip_group = QGroupBox("Equipment")
        equip_layout = QGridLayout(equip_group)
        equip_layout.setColumnStretch(1, 1)  # Make SpinBox column expand
        equip_layout.setColumnStretch(2, 2)  # Item name column gets more space

        # Headgear Top
        equip_layout.addWidget(QLabel("Headgear Top:"), 0, 0)
        self.hg_top_spin = QSpinBox()
        self.hg_top_spin.setRange(0, 99999)
        self.hg_top_spin.setSpecialValueText("None")
        self.hg_top_spin.setMinimumWidth(70)
        self.hg_top_spin.valueChanged.connect(self._update_hg_name)
        equip_layout.addWidget(self.hg_top_spin, 0, 1)
        self.hg_top_name = QLabel("")
        self.hg_top_name.setStyleSheet("color: #888; font-style: italic;")
        equip_layout.addWidget(self.hg_top_name, 0, 2)

        # Headgear Mid
        equip_layout.addWidget(QLabel("Headgear Mid:"), 1, 0)
        self.hg_mid_spin = QSpinBox()
        self.hg_mid_spin.setRange(0, 99999)
        self.hg_mid_spin.setSpecialValueText("None")
        self.hg_mid_spin.setMinimumWidth(70)
        self.hg_mid_spin.valueChanged.connect(self._update_hg_name)
        equip_layout.addWidget(self.hg_mid_spin, 1, 1)
        self.hg_mid_name = QLabel("")
        self.hg_mid_name.setStyleSheet("color: #888; font-style: italic;")
        equip_layout.addWidget(self.hg_mid_name, 1, 2)

        # Headgear Low
        equip_layout.addWidget(QLabel("Headgear Low:"), 2, 0)
        self.hg_low_spin = QSpinBox()
        self.hg_low_spin.setRange(0, 99999)
        self.hg_low_spin.setSpecialValueText("None")
        self.hg_low_spin.setMinimumWidth(70)
        self.hg_low_spin.valueChanged.connect(self._update_hg_name)
        equip_layout.addWidget(self.hg_low_spin, 2, 1)
        self.hg_low_name = QLabel("")
        self.hg_low_name.setStyleSheet("color: #888; font-style: italic;")
        equip_layout.addWidget(self.hg_low_name, 2, 2)

        # Weapon
        equip_layout.addWidget(QLabel("Weapon:"), 3, 0)
        self.weapon_spin = QSpinBox()
        self.weapon_spin.setRange(0, 999)
        self.weapon_spin.setSpecialValueText("None")
        self.weapon_spin.setMinimumWidth(70)
        equip_layout.addWidget(self.weapon_spin, 3, 1)

        # Shield
        equip_layout.addWidget(QLabel("Shield:"), 4, 0)
        self.shield_spin = QSpinBox()
        self.shield_spin.setRange(0, 999)
        self.shield_spin.setSpecialValueText("None")
        self.shield_spin.setMinimumWidth(70)
        equip_layout.addWidget(self.shield_spin, 4, 1)

        left_layout.addWidget(equip_group)
        
        # Animation Controls
        anim_group = QGroupBox("Animation")
        anim_layout = QGridLayout(anim_group)
        anim_layout.setColumnStretch(1, 1)  # Make input column expand

        anim_layout.addWidget(QLabel("Action:"), 0, 0)
        self.action_combo = QComboBox()
        for idx, name in sorted(ACTION_NAMES.items()):
            self.action_combo.addItem(name, idx)
        self.action_combo.setMinimumWidth(120)
        anim_layout.addWidget(self.action_combo, 0, 1)

        anim_layout.addWidget(QLabel("Direction:"), 1, 0)
        self.direction_combo = QComboBox()
        for i, name in enumerate(DIRECTION_NAMES):
            self.direction_combo.addItem(f"{i}: {name}", i)
        self.direction_combo.setMinimumWidth(120)
        anim_layout.addWidget(self.direction_combo, 1, 1)

        anim_layout.addWidget(QLabel("Frame:"), 2, 0)
        self.frame_spin = QSpinBox()
        self.frame_spin.setRange(0, 99)
        self.frame_spin.setMinimumWidth(80)
        anim_layout.addWidget(self.frame_spin, 2, 1)
        
        anim_btn_layout = QHBoxLayout()
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._on_play)
        anim_btn_layout.addWidget(self.play_btn)
        
        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self._on_stop)
        anim_btn_layout.addWidget(self.stop_btn)
        anim_layout.addLayout(anim_btn_layout, 3, 0, 1, 2)
        
        anim_layout.addWidget(QLabel("Speed:"), 4, 0)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(10, 200)
        self.speed_slider.setValue(100)
        anim_layout.addWidget(self.speed_slider, 4, 1)
        
        left_layout.addWidget(anim_group)
        
        # Actions
        action_group = QGroupBox("Actions")
        action_layout = QVBoxLayout(action_group)
        
        render_btn = QPushButton("🔄 Render")
        render_btn.clicked.connect(self._on_render)
        action_layout.addWidget(render_btn)
        
        export_btn = QPushButton("💾 Export PNG")
        export_btn.clicked.connect(self._on_export)
        action_layout.addWidget(export_btn)
        
        export_gif_btn = QPushButton("📹 Export GIF")
        export_gif_btn.clicked.connect(self._on_export_gif)
        action_layout.addWidget(export_gif_btn)
        
        # Sync to comparison button
        sync_btn = QPushButton("⚖️ Sync to Comparison")
        sync_btn.clicked.connect(self._sync_to_comparison)
        action_layout.addWidget(sync_btn)
        
        left_layout.addWidget(action_group)
        left_layout.addStretch()
        
        main_layout.addWidget(left_panel)
        
        # === RIGHT PANEL: Preview ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Preview area
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(400, 400)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #2d2d4d;
                border: 2px solid #3d3d5c;
                border-radius: 8px;
            }
        """)
        preview_layout.addWidget(self.preview_label)
        
        # Custom status indicator
        self.custom_status_label = QLabel("")
        self.custom_status_label.setStyleSheet("font-weight: bold;")
        preview_layout.addWidget(self.custom_status_label)
        
        # Zoom
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(100, 400)
        self.zoom_slider.setValue(200)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)
        self.zoom_label = QLabel("200%")
        zoom_layout.addWidget(self.zoom_label)
        preview_layout.addLayout(zoom_layout)
        
        right_layout.addWidget(preview_group)
        
        # Info
        info_group = QGroupBox("Sprite Info")
        info_layout = QVBoxLayout(info_group)
        self.info_label = QLabel("No sprite loaded")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)
        right_layout.addWidget(info_group)
        
        main_layout.addWidget(right_panel)
    
    def _setup_batch_tab(self, tab: QWidget):
        """Setup the batch export tab."""
        layout = QVBoxLayout(tab)
        
        # Instructions
        instructions = QLabel(
            "<h3>Batch Export</h3>"
            "<p>Export multiple sprites at once as individual files or sprite sheets.</p>"
            "<ul>"
            "<li><b>All Headgear</b>: Export every headgear as individual PNG</li>"
            "<li><b>Headgear Sheet</b>: All headgear in one sprite sheet</li>"
            "<li><b>Job Sheet</b>: All animations for a job class</li>"
            "<li><b>All Jobs</b>: Preview image of all job classes</li>"
            "</ul>"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Quick export buttons
        buttons_group = QGroupBox("Quick Export")
        buttons_layout = QGridLayout(buttons_group)
        
        btn_all_hg = QPushButton("📁 Export All Headgear")
        btn_all_hg.clicked.connect(lambda: self._start_batch_export("headgear"))
        buttons_layout.addWidget(btn_all_hg, 0, 0)
        
        btn_hg_sheet = QPushButton("🖼️ Headgear Sprite Sheet")
        btn_hg_sheet.clicked.connect(lambda: self._start_batch_export("headgear_sheet"))
        buttons_layout.addWidget(btn_hg_sheet, 0, 1)
        
        btn_job_sheet = QPushButton("🎭 Job Animation Sheet")
        btn_job_sheet.clicked.connect(lambda: self._start_batch_export("job_sheet"))
        buttons_layout.addWidget(btn_job_sheet, 1, 0)
        
        btn_all_jobs = QPushButton("👥 All Jobs Preview")
        btn_all_jobs.clicked.connect(lambda: self._start_batch_export("all_jobs"))
        buttons_layout.addWidget(btn_all_jobs, 1, 1)
        
        btn_comparison = QPushButton("⚖️ Comparison Sheet")
        btn_comparison.clicked.connect(lambda: self._start_batch_export("comparison"))
        buttons_layout.addWidget(btn_comparison, 2, 0, 1, 2)
        
        layout.addWidget(buttons_group)
        
        # Progress
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.batch_progress_label = QLabel("Ready")
        progress_layout.addWidget(self.batch_progress_label)
        
        from PyQt6.QtWidgets import QProgressBar
        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.setVisible(False)
        progress_layout.addWidget(self.batch_progress_bar)
        
        self.batch_log = QTextEdit()
        self.batch_log.setReadOnly(True)
        self.batch_log.setMaximumHeight(150)
        progress_layout.addWidget(self.batch_log)
        
        layout.addWidget(progress_group)
        layout.addStretch()
    
    def _setup_browser_tab(self, tab: QWidget):
        """Setup the item browser tab."""
        layout = QVBoxLayout(tab)
        
        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search headgear by name or ID...")
        self.search_edit.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)
        
        # Results table
        self.item_table = QTableWidget()
        self.item_table.setColumnCount(4)
        self.item_table.setHorizontalHeaderLabels(["ID", "Name", "Slot", "Actions"])
        self.item_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.item_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.item_table.cellDoubleClicked.connect(self._on_item_double_click)
        layout.addWidget(self.item_table)
        
        # Load default items
        self._populate_item_table()
    

    def _connect_signals(self):
        """Connect UI signals."""
        self.job_combo.currentTextChanged.connect(self._on_character_changed)
        self.gender_combo.currentIndexChanged.connect(self._on_character_changed)
        self.head_spin.valueChanged.connect(self._on_character_changed)
        self.hair_spin.valueChanged.connect(self._on_character_changed)
        
        self.hg_top_spin.valueChanged.connect(self._on_character_changed)
        self.hg_mid_spin.valueChanged.connect(self._on_character_changed)
        self.hg_low_spin.valueChanged.connect(self._on_character_changed)
        self.weapon_spin.valueChanged.connect(self._on_character_changed)
        self.shield_spin.valueChanged.connect(self._on_character_changed)
        
        self.action_combo.currentIndexChanged.connect(self._on_animation_changed)
        self.direction_combo.currentIndexChanged.connect(self._on_animation_changed)
        self.frame_spin.valueChanged.connect(self._on_animation_changed)
    
    def _update_hg_name(self):
        """Update headgear name labels from database."""
        if not self.item_db:
            return
        
        # Top headgear
        hg_id = self.hg_top_spin.value()
        if hg_id > 0:
            name = self.item_db.get_headgear_name(hg_id)
            self.hg_top_name.setText(name[:20] if len(name) > 20 else name)
        else:
            self.hg_top_name.setText("")
        
        # Mid headgear
        hg_id = self.hg_mid_spin.value()
        if hg_id > 0:
            name = self.item_db.get_headgear_name(hg_id)
            self.hg_mid_name.setText(name[:20] if len(name) > 20 else name)
        else:
            self.hg_mid_name.setText("")
        
        # Low headgear
        hg_id = self.hg_low_spin.value()
        if hg_id > 0:
            name = self.item_db.get_headgear_name(hg_id)
            self.hg_low_name.setText(name[:20] if len(name) > 20 else name)
        else:
            self.hg_low_name.setText("")
    
    def _populate_item_table(self):
        """Populate item browser table."""
        if not self.item_db:
            return
        
        items = self.item_db.get_all_headgear()
        self.item_table.setRowCount(len(items))
        
        for i, item in enumerate(items):
            self.item_table.setItem(i, 0, QTableWidgetItem(str(item.id)))
            self.item_table.setItem(i, 1, QTableWidgetItem(item.name))
            self.item_table.setItem(i, 2, QTableWidgetItem(item.slot))
            
            # Action button
            use_btn = QPushButton("Use")
            use_btn.clicked.connect(lambda checked, id=item.id: self._use_headgear(id))
            self.item_table.setCellWidget(i, 3, use_btn)
    
    def _on_search(self, query: str):
        """Filter item table by search query."""
        if not self.item_db:
            return
        
        if query:
            items = self.item_db.search_headgear(query)
        else:
            items = self.item_db.get_all_headgear()
        
        self.item_table.setRowCount(len(items))
        
        for i, item in enumerate(items):
            self.item_table.setItem(i, 0, QTableWidgetItem(str(item.id)))
            self.item_table.setItem(i, 1, QTableWidgetItem(item.name))
            self.item_table.setItem(i, 2, QTableWidgetItem(item.slot))
            
            use_btn = QPushButton("Use")
            use_btn.clicked.connect(lambda checked, id=item.id: self._use_headgear(id))
            self.item_table.setCellWidget(i, 3, use_btn)
    
    def _on_item_double_click(self, row: int, col: int):
        """Handle double-click on item in table."""
        item_id = int(self.item_table.item(row, 0).text())
        self._use_headgear(item_id)
    
    def _use_headgear(self, headgear_id: int):
        """Set a headgear from the browser."""
        self.hg_top_spin.setValue(headgear_id)
        self.view_tabs.setCurrentIndex(0)  # Switch to designer tab
        self._on_render()
    
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    
    def _on_browse_path(self):
        """Handle browse button click."""
        path = QFileDialog.getExistingDirectory(
            self, "Select Extracted RO Data Folder"
        )
        if path:
            # Auto-correct if user selected 'data' folder
            if os.path.basename(path).lower() == 'data':
                sprite_check = os.path.join(path, 'sprite')
                if os.path.isdir(sprite_check):
                    # Go up one level
                    path = os.path.dirname(path)
                    QMessageBox.information(self, "Path Corrected",
                        f"Auto-corrected path to:\n{path}\n\n"
                        "(You selected the 'data' folder - the path should be the parent folder)")
            
            self.path_edit.setText(path)
            self.compositor.set_resource_path(path)
            
            # Verify the path structure
            sprite_path = os.path.join(path, 'data', 'sprite')
            if not os.path.isdir(sprite_path):
                QMessageBox.warning(self, "Path Warning",
                    f"Expected folder not found:\n{sprite_path}\n\n"
                    "Make sure you selected the folder that CONTAINS the 'data' folder.")
            
            self._on_render()
    
    def _on_character_changed(self):
        """Handle character setting changes."""
        self.compositor.job = self.job_combo.currentText()
        self.compositor.gender = "male" if self.gender_combo.currentIndex() == 0 else "female"
        self.compositor.head_id = self.head_spin.value()
        self.compositor.hair_color = self.hair_spin.value()
        self.compositor.headgear_top = self.hg_top_spin.value()
        self.compositor.headgear_mid = self.hg_mid_spin.value()
        self.compositor.headgear_low = self.hg_low_spin.value()
        self.compositor.weapon = self.weapon_spin.value()
        self.compositor.shield = self.shield_spin.value()
        
        self._update_hg_name()
        self._on_render()
    
    def _on_animation_changed(self):
        """Handle animation setting changes."""
        self._on_render()
    
    def _on_render(self):
        """Render the current character state."""
        if not PIL_AVAILABLE:
            self.info_label.setText("Error: Pillow not installed")
            return
        
        action_idx = self.action_combo.currentData() or 0
        direction = self.direction_combo.currentData() or 0
        frame = self.frame_spin.value()
        
        img = self.compositor.render_frame(action_idx, frame, direction)
        
        if img:
            self._display_image(img)
            
            # Update info
            self.info_label.setText(
                f"Job: {self.compositor.job}\n"
                f"Gender: {self.compositor.gender}\n"
                f"Head: {self.compositor.head_id}\n"
                f"Action: {ACTION_NAMES.get(action_idx, f'Action {action_idx}')}\n"
                f"Direction: {DIRECTION_NAMES[direction]}\n"
                f"Frame: {frame}\n"
                f"Size: {img.width}x{img.height}"
            )
            
            # Check custom status
            self._update_custom_status()
            
            self.sprite_loaded.emit(f"{self.compositor.job}_{action_idx}_{direction}")
        else:
            self.preview_label.setText("No sprite found\n\nSet resource path first")
            self.info_label.setText("No sprite loaded - check resource path")
            self.custom_status_label.setText("")
    
    def _update_custom_status(self):
        """Update the custom sprite status indicator."""
        # Check body sprite
        body_path = self.compositor.get_sprite_path("body")
        body_status = self.custom_detector.check_sprite(body_path)
        
        # Check headgear if equipped
        hg_status = None
        if self.compositor.headgear_top > 0:
            hg_path = self.compositor.get_sprite_path("headgear", self.compositor.headgear_top)
            hg_status = self.custom_detector.check_sprite(hg_path)
        
        # Update label
        status_parts = []
        if body_status == 'new':
            status_parts.append("⭐ Body: CUSTOM")
        elif body_status == 'modified':
            status_parts.append("⚠️ Body: Modified")
        
        if hg_status == 'new':
            status_parts.append("⭐ Headgear: CUSTOM")
        elif hg_status == 'modified':
            status_parts.append("⚠️ Headgear: Modified")
        
        if status_parts:
            self.custom_status_label.setText(" | ".join(status_parts))
            self.custom_status_label.setStyleSheet("color: #ff9800; font-weight: bold;")
        else:
            self.custom_status_label.setText("✓ All sprites: Vanilla")
            self.custom_status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
    
    def _display_image(self, img: Image.Image):
        """Display a PIL Image in the preview label."""
        if not PIL_AVAILABLE:
            return

        zoom = self.zoom_slider.value() / 100.0
        new_size = (int(img.width * zoom), int(img.height * zoom))
        display_img = img.resize(new_size, Image.Resampling.NEAREST)

        # Keep reference to prevent garbage collection before pixmap is displayed
        self._current_qimage = ImageQt(display_img)
        pixmap = QPixmap.fromImage(self._current_qimage)
        self.preview_label.setPixmap(pixmap)
    
    def _on_zoom_changed(self):
        """Handle zoom slider change."""
        self.zoom_label.setText(f"{self.zoom_slider.value()}%")
        self._on_render()
    
    def _on_play(self):
        """Start animation playback."""
        self.is_animating = True
        self.current_frame = 0
        speed = self.speed_slider.value()
        interval = int(100 * 100 / speed)
        self.animation_timer.start(interval)
        self.play_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
    
    def _on_stop(self):
        """Stop animation playback."""
        self.is_animating = False
        self.animation_timer.stop()
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
    
    def _on_animation_tick(self):
        """Handle animation timer tick."""
        self.current_frame += 1
        if self.current_frame > 99:
            self.current_frame = 0
        self.frame_spin.setValue(self.current_frame)
    
    def _on_export(self):
        """Export current frame as PNG."""
        if not PIL_AVAILABLE:
            QMessageBox.warning(self, "Error", "Pillow not installed")
            return
        
        action_idx = self.action_combo.currentData() or 0
        direction = self.direction_combo.currentData() or 0
        frame = self.frame_spin.value()
        
        img = self.compositor.render_frame(action_idx, frame, direction)
        
        if not img:
            QMessageBox.warning(self, "Error", "No sprite to export")
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PNG", 
            f"{self.compositor.job}_{action_idx}_{frame}.png",
            "PNG Images (*.png)"
        )
        
        if path:
            img.save(path, "PNG")
            self.export_complete.emit(path)
            QMessageBox.information(self, "Success", f"Exported to:\n{path}")
    
    def _on_export_gif(self):
        """Export animation as GIF."""
        if not PIL_AVAILABLE:
            QMessageBox.warning(self, "Error", "Pillow not installed")
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Save GIF",
            f"{self.compositor.job}_animation.gif",
            "GIF Images (*.gif)"
        )
        
        if not path:
            return
        
        action_idx = self.action_combo.currentData() or 0
        direction = self.direction_combo.currentData() or 0
        
        frames = []
        for i in range(8):
            img = self.compositor.render_frame(action_idx, i, direction)
            if img:
                rgb_img = Image.new("RGB", img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])
                frames.append(rgb_img)
        
        if not frames:
            QMessageBox.warning(self, "Error", "No frames to export")
            return
        
        speed = self.speed_slider.value()
        duration = int(100 * 100 / speed)
        
        frames[0].save(
            path, save_all=True, append_images=frames[1:],
            duration=duration, loop=0
        )
        
        self.export_complete.emit(path)
        QMessageBox.information(self, "Success", f"Exported {len(frames)} frames to:\n{path}")
    
    def _sync_to_comparison(self):
        """Sync current settings to comparison view."""
        self.comparison_view.set_character_state(
            self.compositor.job,
            self.compositor.gender,
            self.compositor.head_id,
            self.compositor.headgear_top,
            self.compositor.headgear_mid,
            self.compositor.headgear_low
        )
        
        action_idx = self.action_combo.currentData() or 0
        direction = self.direction_combo.currentData() or 0
        frame = self.frame_spin.value()
        
        self.comparison_view.render_comparison(action_idx, frame, direction)
        self.view_tabs.setCurrentIndex(1)  # Switch to comparison tab
    
    def _start_batch_export(self, export_type: str):
        """Start a batch export operation."""
        if not PIL_AVAILABLE:
            QMessageBox.warning(self, "Error", "Pillow not installed")
            return
        
        if not self.compositor.resource_path:
            QMessageBox.warning(self, "Error", "Set resource path first")
            return
        
        # Get output path
        output_path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if not output_path:
            return
        
        # Create exporter
        exporter = BatchExporter(self.compositor, output_path, self.item_db)
        
        # Prepare parameters based on export type
        kwargs = {}
        
        if export_type == "headgear":
            # Get list of headgear IDs to export
            if self.item_db:
                kwargs['headgear_ids'] = [hg.id for hg in self.item_db.get_all_headgear()]
            else:
                kwargs['headgear_ids'] = list(range(2201, 2300)) + list(range(5000, 5100))
            kwargs['gender'] = self.compositor.gender
        
        elif export_type == "headgear_sheet":
            if self.item_db:
                kwargs['headgear_ids'] = [hg.id for hg in self.item_db.get_all_headgear()]
            else:
                kwargs['headgear_ids'] = list(range(2201, 2250))
            kwargs['gender'] = self.compositor.gender
            kwargs['config'] = SpritesheetConfig(columns=10, cell_width=80, cell_height=100)
        
        elif export_type == "job_sheet":
            kwargs['job_name'] = self.compositor.job
            kwargs['gender'] = self.compositor.gender
            kwargs['config'] = SpritesheetConfig(columns=8, cell_width=80, cell_height=100)
        
        elif export_type == "all_jobs":
            kwargs['job_names'] = list(JOB_DATA.keys())
            kwargs['gender'] = self.compositor.gender
        
        elif export_type == "comparison":
            if not self.comparison_view.vanilla_compositor or not self.comparison_view.custom_compositor:
                QMessageBox.warning(self, "Error", 
                    "Set both vanilla and custom paths in the Comparison tab first")
                return
            kwargs['vanilla_compositor'] = self.comparison_view.vanilla_compositor
            kwargs['custom_compositor'] = self.comparison_view.custom_compositor
            # Get items to compare
            items = [("headgear", hg_id) for hg_id in [2220, 2221, 2222, 2230, 2236]]
            kwargs['items'] = items
        
        # Show progress
        self.batch_progress_bar.setVisible(True)
        self.batch_progress_bar.setValue(0)
        self.batch_cancel_btn.setVisible(True)
        self.batch_log.clear()
        self.batch_log.append(f"Starting {export_type} export...")
        
        # Start worker thread
        self.batch_worker = BatchExportWorker(exporter, export_type, **kwargs)
        self.batch_worker.progress.connect(self._on_batch_progress)
        self.batch_worker.finished.connect(self._on_batch_finished)
        self.batch_worker.error.connect(self._on_batch_error)
        self.batch_worker.start()
    
    def _on_batch_progress(self, current: int, total: int, message: str):
        """Handle batch export progress."""
        if total > 0:
            self.batch_progress_bar.setMaximum(total)
            self.batch_progress_bar.setValue(current)
        self.batch_progress_label.setText(message)
    
    def _on_batch_cancel(self):
        """Cancel batch export."""
        if self.batch_worker and self.batch_worker.isRunning():
            self.batch_worker.cancel()
            self.batch_log.append("\n⚠️ Cancelling export...")
    
    def _on_batch_finished(self, result: ExportResult):
        """Handle batch export completion."""
        self.batch_progress_bar.setVisible(False)
        self.batch_cancel_btn.setVisible(False)
        
        if result and result.success:
            self.batch_log.append(f"\n✅ Export complete!")
            self.batch_log.append(f"Output: {result.output_path}")
            self.batch_log.append(f"Exported: {result.count} items")
            
            if result.skipped:
                self.batch_log.append(f"\nSkipped {len(result.skipped)} items")
            
            self.batch_progress_label.setText("Export complete!")
            QMessageBox.information(self, "Success", 
                f"Exported {result.count} items to:\n{result.output_path}")
        else:
            self.batch_log.append("\n❌ Export failed")
            if result and result.errors:
                for error in result.errors:
                    self.batch_log.append(f"  Error: {error}")
            self.batch_progress_label.setText("Export failed")
    
    def _on_batch_error(self, error: str):
        """Handle batch export error."""
        self.batch_progress_bar.setVisible(False)
        self.batch_cancel_btn.setVisible(False)
        self.batch_log.append(f"\n❌ Error: {error}")
        self.batch_progress_label.setText("Export failed")
        QMessageBox.critical(self, "Error", f"Export failed:\n{error}")


# ==============================================================================
# STANDALONE TEST
# ==============================================================================

if __name__ == "__main__":
    if not PYQT_AVAILABLE:
        print("[ERROR] PyQt6 required")
        sys.exit(1)
    
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    window = CharacterDesignerWidget()
    window.setWindowTitle("RO Character Designer - Enhanced")
    window.resize(1200, 800)
    window.show()
    
    sys.exit(app.exec())
