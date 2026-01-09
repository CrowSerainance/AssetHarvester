# ==============================================================================
# ACT/SPR EDITOR MODULE
# ==============================================================================
# Standalone editor for Ragnarok Online ACT (Action) and SPR (Sprite) files.
#
# This module provides direct binary editing of ACT/SPR files:
#   - Load ACT/SPR file pairs
#   - View action/frame/layer structure
#   - Edit layer properties (position, rotation, scale, mirror)
#   - Edit frame delays
#   - Add/remove frames and layers (placeholder)
#   - Save ACT files (ACT writer not yet implemented)
#
# This is a low-level binary file editor for custom content creation.
# ==============================================================================

import os
import sys
from typing import Optional

# ==============================================================================
# PyQt6 IMPORTS
# ==============================================================================
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QGroupBox, QLabel, QPushButton, QLineEdit, QFileDialog,
        QMessageBox, QTreeWidget, QTreeWidgetItem, QScrollArea,
        QCheckBox, QSpinBox, QComboBox, QDoubleSpinBox
    )
    from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal, QTimer
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("[ERROR] PyQt6 is not installed")

# ==============================================================================
# PARSER IMPORTS
# ==============================================================================
try:
    from src.parsers.spr_parser import SPRParser, SPRSprite
    from src.parsers.act_parser import ACTParser, ACTData
    PARSERS_AVAILABLE = True
except ImportError:
    PARSERS_AVAILABLE = False
    print("[WARN] ACT/SPR parsers not available")

# Pillow for rendering
try:
    from PIL import Image, ImageOps, ImageDraw
    from PIL.ImageQt import ImageQt
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ==============================================================================
# ACT/SPR EDITOR WIDGET
# ==============================================================================

class ACTSPREditorWidget(QWidget):
    """
    Standalone editor for ACT and SPR files.
    
    Provides binary-level editing of Ragnarok Online action and sprite files.
    This is separate from the Character Designer which focuses on visual preview.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize parsers
        self.spr_parser = SPRParser() if PARSERS_AVAILABLE else None
        self.act_parser = ACTParser() if PARSERS_AVAILABLE else None
        
        # Loaded file data
        self.loaded_act_data = None
        self.loaded_spr_data = None
        self.loaded_act_path = None
        
        # Loading state
        self._load_thread: Optional[QThread] = None
        self._load_worker = None
        self._is_loading = False
        
        # Animation state
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._advance_animation_frame)
        self._anim_playing = False
        self._anim_action_idx = 0
        self._anim_frame_idx = 0
        self._anim_delay_scale = 1.0
        self._debug_overlay = False
        
        # Build UI
        self._setup_ui()
    
    def _setup_ui(self):
        """Build the user interface."""
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel(
            "<h3>✏️ ACT/SPR Editor - Binary File Editor</h3>"
            "<p>Direct editing of Ragnarok Online action (ACT) and sprite (SPR) files.</p>"
            "<p><b>Warning:</b> This is an advanced feature. Incorrect edits may cause game crashes.</p>"
            "<p><b>Note:</b> ACT file saving is not yet implemented. This editor is currently read-only for inspection.</p>"
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # File selection
        file_group = QGroupBox("File Selection")
        file_layout = QGridLayout(file_group)
        
        file_layout.addWidget(QLabel("SPR File:"), 0, 0)
        self.spr_path_edit = QLineEdit()
        self.spr_path_edit.setPlaceholderText("Path to .spr file...")
        file_layout.addWidget(self.spr_path_edit, 0, 1)
        
        self.spr_browse = QPushButton("Browse")
        self.spr_browse.clicked.connect(self._browse_spr_file)
        file_layout.addWidget(self.spr_browse, 0, 2)
        
        file_layout.addWidget(QLabel("ACT File:"), 1, 0)
        self.act_path_edit = QLineEdit()
        self.act_path_edit.setPlaceholderText("Path to .act file (auto-filled)...")
        file_layout.addWidget(self.act_path_edit, 1, 1)
        
        self.act_browse = QPushButton("Browse")
        self.act_browse.clicked.connect(self._browse_act_file)
        file_layout.addWidget(self.act_browse, 1, 2)
        
        self.load_btn = QPushButton("📂 Load ACT/SPR")
        self.load_btn.clicked.connect(self._load_files)
        file_layout.addWidget(self.load_btn, 2, 0, 1, 3)
        
        self.lazy_load_check = QCheckBox("Lazy-load frames/layers (recommended for large files)")
        self.lazy_load_check.setChecked(True)
        file_layout.addWidget(self.lazy_load_check, 3, 0, 1, 3)
        
        layout.addWidget(file_group)
        
        # Splitter for tree view and properties
        from PyQt6.QtWidgets import QSplitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left: Action/Frame/Layer tree
        tree_group = QGroupBox("Structure")
        tree_layout = QVBoxLayout(tree_group)
        
        self.act_tree = QTreeWidget()
        self.act_tree.setHeaderLabels(["Element", "Details"])
        self.act_tree.itemClicked.connect(self._on_tree_item_clicked)
        self.act_tree.itemExpanded.connect(self._on_tree_item_expanded)
        tree_layout.addWidget(self.act_tree)
        
        tree_buttons = QHBoxLayout()
        add_frame_btn = QPushButton("➕ Frame")
        add_frame_btn.clicked.connect(self._add_frame)
        tree_buttons.addWidget(add_frame_btn)
        
        add_layer_btn = QPushButton("➕ Layer")
        add_layer_btn.clicked.connect(self._add_layer)
        tree_buttons.addWidget(add_layer_btn)
        
        remove_btn = QPushButton("🗑️ Remove")
        remove_btn.clicked.connect(self._remove_element)
        tree_buttons.addWidget(remove_btn)
        tree_buttons.addStretch()
        
        tree_layout.addLayout(tree_buttons)
        splitter.addWidget(tree_group)
        
        # Right: Properties panel
        props_group = QGroupBox("Properties")
        props_layout = QVBoxLayout(props_group)
        
        self.props_widget = QWidget()
        props_scroll = QScrollArea()
        props_scroll.setWidget(self.props_widget)
        props_scroll.setWidgetResizable(True)
        
        self.props_layout = QGridLayout(self.props_widget)
        self.props_layout.addWidget(QLabel("Select an element to edit properties"), 0, 0)
        
        props_layout.addWidget(props_scroll)
        splitter.addWidget(props_group)
        
        layout.addWidget(splitter)
        
        # Preview + animation controls
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_label = QLabel("No preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(240)
        self.preview_label.setStyleSheet("background: #1b1f2a; border: 1px solid #2b3245;")
        preview_layout.addWidget(self.preview_label)
        
        anim_controls = QHBoxLayout()
        anim_controls.addWidget(QLabel("Action:"))
        self.action_combo = QComboBox()
        self.action_combo.currentIndexChanged.connect(self._on_action_selected)
        anim_controls.addWidget(self.action_combo)
        
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.clicked.connect(self._toggle_animation)
        anim_controls.addWidget(self.play_btn)
        
        anim_controls.addWidget(QLabel("Delay x"))
        self.delay_scale_spin = QDoubleSpinBox()
        self.delay_scale_spin.setRange(0.1, 5.0)
        self.delay_scale_spin.setSingleStep(0.1)
        self.delay_scale_spin.setValue(self._anim_delay_scale)
        self.delay_scale_spin.valueChanged.connect(self._on_delay_scale_changed)
        anim_controls.addWidget(self.delay_scale_spin)
        
        self.debug_overlay_check = QCheckBox("Debug overlay")
        self.debug_overlay_check.toggled.connect(self._on_debug_overlay_toggled)
        anim_controls.addWidget(self.debug_overlay_check)
        
        anim_controls.addStretch()
        preview_layout.addLayout(anim_controls)
        
        layout.addWidget(preview_group)
        
        # Action buttons
        action_buttons = QHBoxLayout()
        
        save_act_btn = QPushButton("💾 Save ACT")
        save_act_btn.clicked.connect(self._save_act)
        action_buttons.addWidget(save_act_btn)
        
        save_as_btn = QPushButton("💾 Save ACT As...")
        save_as_btn.clicked.connect(self._save_act_as)
        action_buttons.addWidget(save_as_btn)
        
        action_buttons.addStretch()
        layout.addLayout(action_buttons)
        
        # Status
        self.status_label = QLabel("No file loaded")
        self.status_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.status_label)
    
    def _browse_spr_file(self):
        """Browse for SPR file."""
        path, _ = QFileDialog.getOpenFileName(self, "Select SPR File", "", "SPR Files (*.spr)")
        if path:
            self.spr_path_edit.setText(path)
            # Auto-fill ACT path
            act_path = path.replace('.spr', '.act')
            if os.path.exists(act_path):
                self.act_path_edit.setText(act_path)
    
    def _browse_act_file(self):
        """Browse for ACT file."""
        path, _ = QFileDialog.getOpenFileName(self, "Select ACT File", "", "ACT Files (*.act)")
        if path:
            self.act_path_edit.setText(path)
    
    def _load_files(self):
        """Load ACT and SPR files for editing."""
        if self._is_loading:
            return
        
        spr_path = self.spr_path_edit.text().strip()
        act_path = self.act_path_edit.text().strip()
        
        if not spr_path or not act_path:
            QMessageBox.warning(self, "Error", "Select both SPR and ACT files")
            return
        
        if not os.path.exists(spr_path):
            QMessageBox.warning(self, "Error", f"SPR file not found: {spr_path}")
            return
        
        if not os.path.exists(act_path):
            QMessageBox.warning(self, "Error", f"ACT file not found: {act_path}")
            return
        
        self._set_loading_state(True, "Loading ACT/SPR in background...")
        
        self._load_thread = QThread(self)
        self._load_worker = ACTSPRLoadWorker(spr_path, act_path)
        self._load_worker.moveToThread(self._load_thread)
        self._load_thread.started.connect(self._load_worker.run)
        self._load_worker.finished.connect(self._on_load_finished)
        self._load_worker.error.connect(self._on_load_error)
        self._load_worker.finished.connect(self._load_thread.quit)
        self._load_worker.finished.connect(self._load_worker.deleteLater)
        self._load_thread.finished.connect(self._load_thread.deleteLater)
        self._load_thread.start()
    
    def _populate_tree(self):
        """Populate the ACT structure tree."""
        self.act_tree.clear()
        
        if not self.loaded_act_data:
            return
        
        self.act_tree.setUpdatesEnabled(False)
        
        # Add each action
        for action_idx in range(self.loaded_act_data.get_action_count()):
            action = self.loaded_act_data.get_action(action_idx)
            action_item = QTreeWidgetItem(
                self.act_tree,
                [f"Action {action_idx}", f"{action.get_frame_count()} frames"]
            )
            action_item.setData(0, Qt.ItemDataRole.UserRole, ('action', action_idx))
            
            if self.lazy_load_check.isChecked():
                action_item.setChildIndicatorPolicy(
                    QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
                )
                placeholder = QTreeWidgetItem(action_item, ["Loading...", ""])
                placeholder.setData(0, Qt.ItemDataRole.UserRole, ('placeholder',))
            else:
                self._populate_action_frames(action_item, action_idx)
        
        self.act_tree.setUpdatesEnabled(True)
        
        # Populate action dropdown
        self.action_combo.blockSignals(True)
        self.action_combo.clear()
        for action_idx in range(self.loaded_act_data.get_action_count()):
            self.action_combo.addItem(f"Action {action_idx}", action_idx)
        self.action_combo.setCurrentIndex(0)
        self.action_combo.blockSignals(False)
        
        # Reset animation to action 0
        self._anim_action_idx = 0
        self._anim_frame_idx = 0
        self._render_current_frame()
    
    def _on_tree_item_clicked(self, item, column):
        """Handle click on tree item - show properties."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if not data:
            return
        
        # Clear existing properties
        for i in reversed(range(self.props_layout.count())):
            widget = self.props_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        element_type = data[0]
        
        if element_type == 'layer':
            _, action_idx, frame_idx, layer_idx = data
            self._show_layer_properties(action_idx, frame_idx, layer_idx)
        elif element_type == 'frame':
            _, action_idx, frame_idx = data
            self._show_frame_properties(action_idx, frame_idx)
            self._anim_action_idx = action_idx
            self._anim_frame_idx = frame_idx
            self.action_combo.setCurrentIndex(action_idx)
            self._render_current_frame()
        elif element_type == 'action':
            _, action_idx = data
            self._show_action_properties(action_idx)
            self._anim_action_idx = action_idx
            self._anim_frame_idx = 0
            self.action_combo.setCurrentIndex(action_idx)
            self._render_current_frame()
    
    def _on_tree_item_expanded(self, item):
        """Handle tree item expansion (lazy loading)."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        
        element_type = data[0]
        if element_type == 'action':
            # Populate frames lazily
            if item.childCount() == 1:
                child_data = item.child(0).data(0, Qt.ItemDataRole.UserRole)
                if child_data == ('placeholder',):
                    item.takeChildren()
                    _, action_idx = data
                    self._populate_action_frames(item, action_idx)
        elif element_type == 'frame':
            # Populate layers lazily
            if item.childCount() == 1:
                child_data = item.child(0).data(0, Qt.ItemDataRole.UserRole)
                if child_data == ('placeholder',):
                    item.takeChildren()
                    _, action_idx, frame_idx = data
                    self._populate_frame_layers(item, action_idx, frame_idx)
    
    def _populate_action_frames(self, action_item, action_idx: int):
        """Populate frames for an action (lazy loading)."""
        action = self.loaded_act_data.get_action(action_idx)
        if not action:
            return
        
        for frame_idx in range(action.get_frame_count()):
            frame = action.get_frame(frame_idx)
            frame_item = QTreeWidgetItem(
                action_item,
                [f"Frame {frame_idx}",
                 f"{frame.get_layer_count()} layers, delay={frame.delay}ms"]
            )
            frame_item.setData(0, Qt.ItemDataRole.UserRole,
                               ('frame', action_idx, frame_idx))
            
            if self.lazy_load_check.isChecked():
                frame_item.setChildIndicatorPolicy(
                    QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
                )
                placeholder = QTreeWidgetItem(frame_item, ["Loading...", ""])
                placeholder.setData(0, Qt.ItemDataRole.UserRole, ('placeholder',))
            else:
                self._populate_frame_layers(frame_item, action_idx, frame_idx)
    
    def _populate_frame_layers(self, frame_item, action_idx: int, frame_idx: int):
        """Populate layers for a frame (lazy loading)."""
        frame = self.loaded_act_data.get_frame(action_idx, frame_idx)
        if not frame:
            return
        
        for layer_idx, layer in enumerate(frame.layers):
            layer_text = f"Layer {layer_idx}"
            layer_details = f"sprite={layer.sprite_index}, pos=({layer.x},{layer.y})"
            layer_item = QTreeWidgetItem(frame_item, [layer_text, layer_details])
            layer_item.setData(0, Qt.ItemDataRole.UserRole,
                               ('layer', action_idx, frame_idx, layer_idx))
    
    def _set_loading_state(self, is_loading: bool, message: str = ""):
        """Set loading state and update UI."""
        self._is_loading = is_loading
        self.load_btn.setEnabled(not is_loading)
        self.spr_browse.setEnabled(not is_loading)
        self.act_browse.setEnabled(not is_loading)
        self.spr_path_edit.setEnabled(not is_loading)
        self.act_path_edit.setEnabled(not is_loading)
        self.lazy_load_check.setEnabled(not is_loading)
        if message:
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: #ff9800; font-weight: bold;")
    
    def _on_load_finished(self, spr_data, act_data, act_path):
        """Handle async load completion."""
        self.loaded_spr_data = spr_data
        self.loaded_act_data = act_data
        self.loaded_act_path = act_path
        
        if not self.loaded_spr_data or not self.loaded_act_data:
            self._set_loading_state(False)
            QMessageBox.critical(self, "Error", "Failed to load ACT/SPR data")
            return
        
        self._populate_tree()
        self.status_label.setText(
            f"Loaded: {os.path.basename(act_path)} "
            f"({self.loaded_act_data.get_action_count()} actions)"
        )
        self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        self._set_loading_state(False)
        
        # Render first frame on load
        self._anim_action_idx = 0
        self._anim_frame_idx = 0
        self._render_current_frame()
    
    def _on_load_error(self, message: str):
        """Handle async load error."""
        self._set_loading_state(False)
        QMessageBox.critical(self, "Error", message)
    
    def _on_action_selected(self, index: int):
        """Handle action dropdown selection."""
        if index < 0:
            return
        self._anim_action_idx = self.action_combo.currentData() or 0
        self._anim_frame_idx = 0
        self._render_current_frame()
    
    def _on_delay_scale_changed(self, value: float):
        """Handle delay scale change."""
        self._anim_delay_scale = float(value)
        if self._anim_playing:
            self._schedule_next_frame()
    
    def _on_debug_overlay_toggled(self, checked: bool):
        """Handle debug overlay toggle."""
        self._debug_overlay = checked
        self._render_current_frame()
    
    def _toggle_animation(self):
        """Toggle animation play/pause."""
        if not self.loaded_act_data or not self.loaded_spr_data:
            return
        
        self._anim_playing = not self._anim_playing
        if self._anim_playing:
            self.play_btn.setText("⏸ Pause")
            self._schedule_next_frame()
        else:
            self.play_btn.setText("▶ Play")
            self._anim_timer.stop()
    
    def _advance_animation_frame(self):
        """Advance to next animation frame."""
        if not self.loaded_act_data:
            return
        
        action = self.loaded_act_data.get_action(self._anim_action_idx)
        if not action or action.get_frame_count() == 0:
            return
        
        self._anim_frame_idx = (self._anim_frame_idx + 1) % action.get_frame_count()
        self._render_current_frame()
        if self._anim_playing:
            self._schedule_next_frame()
    
    def _schedule_next_frame(self):
        """Schedule next frame based on frame delay."""
        action = self.loaded_act_data.get_action(self._anim_action_idx)
        if not action or action.get_frame_count() == 0:
            return
        
        frame = action.get_frame(self._anim_frame_idx)
        delay = int(getattr(frame, "delay", 0)) if frame else 0
        if delay <= 0:
            delay = 100  # Default 100ms if no delay specified
        delay = int(delay * self._anim_delay_scale)
        if delay <= 0:
            delay = 1
        self._anim_timer.start(delay)
    
    def _render_current_frame(self):
        """Render the current action/frame in the preview."""
        if not (self.loaded_act_data and self.loaded_spr_data):
            self.preview_label.setText("No preview")
            return
        
        if not PIL_AVAILABLE:
            self.preview_label.setText("PIL not available — preview disabled")
            return
        
        action = self.loaded_act_data.get_action(self._anim_action_idx)
        if not action or action.get_frame_count() == 0:
            self.preview_label.setText("No frames to render")
            return
        
        frame = action.get_frame(self._anim_frame_idx)
        if not frame:
            self.preview_label.setText("Invalid frame")
            return
        
        # Composite layers onto a canvas
        canvas_size = 512
        canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        center = canvas_size // 2
        
        for layer in frame.layers:
            sprite_idx = layer.sprite_index
            if sprite_idx < 0:
                continue
            
            if layer.sprite_type == 1:
                sprite_idx += self.loaded_spr_data.get_indexed_count()
            
            if sprite_idx >= self.loaded_spr_data.get_total_frames():
                continue
            
            img = self.loaded_spr_data.get_frame_image(sprite_idx)
            if img is None:
                continue
            
            img = self._apply_layer_transforms(img, layer)
            
            # Apply transform basics (position only)
            x = center + layer.x - (img.width // 2)
            y = center + layer.y - (img.height // 2)
            canvas.alpha_composite(img, (x, y))
            
            if self._debug_overlay:
                draw = ImageDraw.Draw(canvas)
                label = f"{sprite_idx} ({'RGBA' if layer.sprite_type == 1 else 'IDX'})"
                draw.rectangle([x, y, x + img.width, y + img.height], outline=(255, 255, 0, 200))
                draw.text((x + 2, y + 2), label, fill=(255, 255, 0, 220))
        
        # Convert to QPixmap and display
        try:
            from PyQt6.QtGui import QPixmap
            qimage = ImageQt.ImageQt(canvas)
            pixmap = QPixmap.fromImage(qimage)
            
            # Scale if too large
            max_size = 512
            if pixmap.width() > max_size or pixmap.height() > max_size:
                pixmap = pixmap.scaled(max_size, max_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            self.preview_label.setPixmap(pixmap)
        except Exception as e:
            self.preview_label.setText(f"Render error: {e}")
    
    def _apply_layer_transforms(self, img: Image.Image, layer) -> Image.Image:
        """Apply layer transforms (width/height override, mirror, scale, rotation, color tint) to image."""
        # Width/height override (if provided in ACT)
        if getattr(layer, "width", 0) > 0 and getattr(layer, "height", 0) > 0:
            img = img.resize((layer.width, layer.height), resample=Image.Resampling.BICUBIC)
        
        # Mirror
        if getattr(layer, "mirror", False):
            img = ImageOps.mirror(img)
        
        # Scale
        scale_x = getattr(layer, "scale_x", 1.0)
        scale_y = getattr(layer, "scale_y", 1.0)
        if scale_x != 1.0 or scale_y != 1.0:
            new_w = max(1, int(img.width * scale_x))
            new_h = max(1, int(img.height * scale_y))
            img = img.resize((new_w, new_h), resample=Image.Resampling.BICUBIC)
        
        # Rotation (degrees)
        rotation = getattr(layer, "rotation", 0)
        if rotation:
            img = img.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
        
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
    
    def _show_layer_properties(self, action_idx: int, frame_idx: int, layer_idx: int):
        """Show editable properties for a layer."""
        frame = self.loaded_act_data.get_frame(action_idx, frame_idx)
        if not frame or layer_idx >= len(frame.layers):
            return
        
        layer = frame.layers[layer_idx]
        
        row = 0
        self.props_layout.addWidget(QLabel(f"<b>Layer {layer_idx}</b>"), row, 0, 1, 2)
        row += 1
        
        # Sprite index
        self.props_layout.addWidget(QLabel("Sprite Index:"), row, 0)
        sprite_spin = QSpinBox()
        sprite_spin.setRange(-1, 9999)
        sprite_spin.setValue(layer.sprite_index)
        self.props_layout.addWidget(sprite_spin, row, 1)
        row += 1
        
        # Position X
        self.props_layout.addWidget(QLabel("X Position:"), row, 0)
        x_spin = QSpinBox()
        x_spin.setRange(-1000, 1000)
        x_spin.setValue(layer.x)
        self.props_layout.addWidget(x_spin, row, 1)
        row += 1
        
        # Position Y
        self.props_layout.addWidget(QLabel("Y Position:"), row, 0)
        y_spin = QSpinBox()
        y_spin.setRange(-1000, 1000)
        y_spin.setValue(layer.y)
        self.props_layout.addWidget(y_spin, row, 1)
        row += 1
        
        # Mirror
        self.props_layout.addWidget(QLabel("Mirror:"), row, 0)
        mirror_check = QCheckBox()
        mirror_check.setChecked(layer.mirror)
        self.props_layout.addWidget(mirror_check, row, 1)
        row += 1
        
        # Rotation
        self.props_layout.addWidget(QLabel("Rotation (degrees):"), row, 0)
        rot_spin = QSpinBox()
        rot_spin.setRange(-360, 360)
        rot_spin.setValue(layer.rotation)
        self.props_layout.addWidget(rot_spin, row, 1)
        row += 1
        
        # Apply button
        apply_btn = QPushButton("Apply Changes")
        apply_btn.clicked.connect(lambda: self._apply_layer_changes(
            action_idx, frame_idx, layer_idx,
            sprite_spin.value(), x_spin.value(), y_spin.value(),
            mirror_check.isChecked(), rot_spin.value()
        ))
        self.props_layout.addWidget(apply_btn, row, 0, 1, 2)
    
    def _show_frame_properties(self, action_idx: int, frame_idx: int):
        """Show editable properties for a frame."""
        frame = self.loaded_act_data.get_frame(action_idx, frame_idx)
        if not frame:
            return
        
        row = 0
        self.props_layout.addWidget(QLabel(f"<b>Frame {frame_idx}</b>"), row, 0, 1, 2)
        row += 1
        
        self.props_layout.addWidget(QLabel("Delay (ms):"), row, 0)
        delay_spin = QSpinBox()
        delay_spin.setRange(1, 1000)
        delay_spin.setValue(int(frame.delay))
        self.props_layout.addWidget(delay_spin, row, 1)
        row += 1
        
        self.props_layout.addWidget(QLabel(f"Layers: {frame.get_layer_count()}"), row, 0, 1, 2)
        row += 1
        
        apply_btn = QPushButton("Apply Changes")
        apply_btn.clicked.connect(lambda: self._apply_frame_changes(
            action_idx, frame_idx, delay_spin.value()
        ))
        self.props_layout.addWidget(apply_btn, row, 0, 1, 2)
    
    def _show_action_properties(self, action_idx: int):
        """Show properties for an action."""
        action = self.loaded_act_data.get_action(action_idx)
        if not action:
            return
        
        row = 0
        self.props_layout.addWidget(QLabel(f"<b>Action {action_idx}</b>"), row, 0, 1, 2)
        row += 1
        
        self.props_layout.addWidget(QLabel(f"Frames: {action.get_frame_count()}"), row, 0, 1, 2)
        row += 1
        
        duration = action.get_total_duration()
        self.props_layout.addWidget(QLabel(f"Duration: {duration:.0f} ms"), row, 0, 1, 2)
    
    def _apply_layer_changes(self, action_idx: int, frame_idx: int, layer_idx: int,
                            sprite_idx: int, x: int, y: int, mirror: bool, rotation: int):
        """Apply changes to a layer."""
        frame = self.loaded_act_data.get_frame(action_idx, frame_idx)
        if frame and layer_idx < len(frame.layers):
            layer = frame.layers[layer_idx]
            layer.sprite_index = sprite_idx
            layer.x = x
            layer.y = y
            layer.mirror = mirror
            layer.rotation = rotation
            
            self._populate_tree()  # Refresh tree
            self.status_label.setText("Layer modified (not saved)")
            self.status_label.setStyleSheet("color: #ff9800; font-weight: bold;")
    
    def _apply_frame_changes(self, action_idx: int, frame_idx: int, delay: int):
        """Apply changes to a frame."""
        frame = self.loaded_act_data.get_frame(action_idx, frame_idx)
        if frame:
            frame.delay = float(delay)
            
            self._populate_tree()
            self.status_label.setText("Frame modified (not saved)")
            self.status_label.setStyleSheet("color: #ff9800; font-weight: bold;")
    
    def _add_frame(self):
        """Add a new frame to selected action."""
        QMessageBox.information(self, "Info", 
            "Add frame feature - select an action first")
    
    def _add_layer(self):
        """Add a new layer to selected frame."""
        QMessageBox.information(self, "Info", 
            "Add layer feature - select a frame first")
    
    def _remove_element(self):
        """Remove selected element."""
        QMessageBox.information(self, "Info", 
            "Remove feature - select an element first")
    
    def _save_act(self):
        """Save ACT file to original location."""
        if not self.loaded_act_data or not self.loaded_act_path:
            QMessageBox.warning(self, "Error", "No ACT file loaded")
            return
        
        # Note: ACT writer not yet implemented
        QMessageBox.information(self, "Info",
            "ACT saving is not yet implemented.\n"
            "The ACT format writer needs to be created.\n"
            "For now, this editor is read-only for inspection.")
    
    def _save_act_as(self):
        """Save ACT file to new location."""
        if not self.loaded_act_data:
            QMessageBox.warning(self, "Error", "No ACT file loaded")
            return
        
        QMessageBox.information(self, "Info", 
            "Save As feature - ACT writer not yet implemented")


# ==============================================================================
# LOAD WORKER (ASYNC)
# ==============================================================================

class ACTSPRLoadWorker(QObject):
    """Worker for loading ACT/SPR files in background thread."""
    
    finished = pyqtSignal(object, object, str)  # spr_data, act_data, act_path
    error = pyqtSignal(str)
    
    def __init__(self, spr_path: str, act_path: str):
        super().__init__()
        self.spr_path = spr_path
        self.act_path = act_path
    
    def run(self):
        """Load files in background thread."""
        try:
            if not PARSERS_AVAILABLE:
                self.error.emit("ACT/SPR parsers are not available.")
                return
            
            spr_parser = SPRParser()
            act_parser = ACTParser()
            
            spr_data = spr_parser.load(self.spr_path)
            if not spr_data:
                self.error.emit("Failed to load SPR file.")
                return
            
            act_data = act_parser.load(self.act_path)
            if not act_data:
                self.error.emit("Failed to load ACT file.")
                return
            
            self.finished.emit(spr_data, act_data, self.act_path)
        except Exception as exc:
            self.error.emit(f"Unexpected load error: {exc}")


# ==============================================================================
# STANDALONE TEST
# ==============================================================================

if __name__ == "__main__":
    if not PYQT_AVAILABLE:
        print("[ERROR] PyQt6 required")
        sys.exit(1)
    
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    window = ACTSPREditorWidget()
    window.setWindowTitle("ACT/SPR Editor")
    window.resize(1000, 700)
    window.show()
    
    sys.exit(app.exec())

