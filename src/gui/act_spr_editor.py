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
        QCheckBox, QSpinBox
    )
    from PyQt6.QtCore import Qt
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
        
        spr_browse = QPushButton("Browse")
        spr_browse.clicked.connect(self._browse_spr_file)
        file_layout.addWidget(spr_browse, 0, 2)
        
        file_layout.addWidget(QLabel("ACT File:"), 1, 0)
        self.act_path_edit = QLineEdit()
        self.act_path_edit.setPlaceholderText("Path to .act file (auto-filled)...")
        file_layout.addWidget(self.act_path_edit, 1, 1)
        
        act_browse = QPushButton("Browse")
        act_browse.clicked.connect(self._browse_act_file)
        file_layout.addWidget(act_browse, 1, 2)
        
        load_btn = QPushButton("📂 Load ACT/SPR")
        load_btn.clicked.connect(self._load_files)
        file_layout.addWidget(load_btn, 2, 0, 1, 3)
        
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
        
        # Load SPR
        if self.spr_parser:
            self.loaded_spr_data = self.spr_parser.load(spr_path)
            if not self.loaded_spr_data:
                QMessageBox.warning(self, "Error", "Failed to load SPR file")
                return
        
        # Load ACT
        if self.act_parser:
            self.loaded_act_data = self.act_parser.load(act_path)
            self.loaded_act_path = act_path
            
            if not self.loaded_act_data:
                QMessageBox.critical(self, "Error", "Failed to load ACT file")
                return
        
        # Populate tree
        self._populate_tree()
        self.status_label.setText(
            f"Loaded: {os.path.basename(act_path)} "
            f"({self.loaded_act_data.get_action_count()} actions)"
        )
        self.status_label.setStyleSheet("color: #4caf50; font-weight: bold;")
    
    def _populate_tree(self):
        """Populate the ACT structure tree."""
        self.act_tree.clear()
        
        if not self.loaded_act_data:
            return
        
        # Add each action
        for action_idx in range(self.loaded_act_data.get_action_count()):
            action = self.loaded_act_data.get_action(action_idx)
            action_item = QTreeWidgetItem(
                self.act_tree,
                [f"Action {action_idx}", f"{action.get_frame_count()} frames"]
            )
            
            # Add frames
            for frame_idx in range(action.get_frame_count()):
                frame = action.get_frame(frame_idx)
                frame_item = QTreeWidgetItem(
                    action_item,
                    [f"Frame {frame_idx}", 
                     f"{frame.get_layer_count()} layers, delay={frame.delay}ms"]
                )
                
                # Add layers
                for layer_idx, layer in enumerate(frame.layers):
                    layer_text = f"Layer {layer_idx}"
                    layer_details = f"sprite={layer.sprite_index}, pos=({layer.x},{layer.y})"
                    layer_item = QTreeWidgetItem(frame_item, [layer_text, layer_details])
                    layer_item.setData(0, Qt.ItemDataRole.UserRole, 
                                     ('layer', action_idx, frame_idx, layer_idx))
                
                frame_item.setData(0, Qt.ItemDataRole.UserRole, 
                                 ('frame', action_idx, frame_idx))
            
            action_item.setData(0, Qt.ItemDataRole.UserRole, ('action', action_idx))
        
        self.act_tree.expandAll()
    
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
        elif element_type == 'action':
            _, action_idx = data
            self._show_action_properties(action_idx)
    
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

