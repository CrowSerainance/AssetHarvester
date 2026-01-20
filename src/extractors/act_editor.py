# ==============================================================================
# ACT EDITOR MODULE
# ==============================================================================
# Editor for Ragnarok Online ACT (Action) files.
# Provides high-level methods to modify animation properties:
# - Position (offsets)
# - Scaling (magnify)
# - Rotation
# - Color/Tint
# - Mirroring
# - Sound Events
#
# This module implements the functionality of tools like ActOR and ActOR2.
# ==============================================================================

from typing import Optional, Tuple, List
from src.parsers.act_parser import ACTParser, ACTData, ACTAction, ACTFrame, ACTLayer, ACTEvent

class ACTEditor:
    """
    Editor for modifying Ragnarok Online ACT files.
    """
    
    def __init__(self):
        self.parser = ACTParser()
        self.act_data: Optional[ACTData] = None
        self.filepath: Optional[str] = None
        self.modified = False
        
    def open(self, filepath: str) -> bool:
        """
        Open an ACT file for editing.
        """
        self.act_data = self.parser.load(filepath)
        if self.act_data:
            self.filepath = filepath
            self.modified = False
            return True
        return False
        
    def save(self, filepath: Optional[str] = None) -> bool:
        """
        Save the ACT file.
        """
        target_path = filepath or self.filepath
        if not target_path or not self.act_data:
            return False
            
        return self.parser.save(self.act_data, target_path)
        
    def get_layer(self, action_idx: int, frame_idx: int, layer_idx: int) -> Optional[ACTLayer]:
        """
        Get a specific layer.
        """
        if not self.act_data: return None
        frame = self.act_data.get_frame(action_idx, frame_idx)
        if frame and 0 <= layer_idx < len(frame.layers):
            return frame.layers[layer_idx]
        return None

    # ==========================================================================
    # EDITING METHODS
    # ==========================================================================

    def set_offset(self, action_idx: int, frame_idx: int, layer_idx: int, x: int, y: int) -> bool:
        """Set layer position offset."""
        layer = self.get_layer(action_idx, frame_idx, layer_idx)
        if layer:
            layer.x = int(x)
            layer.y = int(y)
            self.modified = True
            return True
        return False

    def set_scale(self, action_idx: int, frame_idx: int, layer_idx: int, 
                 scale_x: float, scale_y: Optional[float] = None) -> bool:
        """Set layer scale (magnify)."""
        layer = self.get_layer(action_idx, frame_idx, layer_idx)
        if layer:
            layer.scale_x = float(scale_x)
            if scale_y is not None:
                layer.scale_y = float(scale_y)
            else:
                layer.scale_y = float(scale_x) # Uniform scale
            self.modified = True
            return True
        return False

    def set_rotation(self, action_idx: int, frame_idx: int, layer_idx: int, angle: int) -> bool:
        """Set layer rotation (0-360)."""
        layer = self.get_layer(action_idx, frame_idx, layer_idx)
        if layer:
            layer.rotation = int(angle)
            self.modified = True
            return True
        return False
        
    def set_mirror(self, action_idx: int, frame_idx: int, layer_idx: int, mirror: bool) -> bool:
        """Set layer mirroring."""
        layer = self.get_layer(action_idx, frame_idx, layer_idx)
        if layer:
            layer.mirror = mirror
            self.modified = True
            return True
        return False

    def set_color(self, action_idx: int, frame_idx: int, layer_idx: int, 
                 r: int, g: int, b: int, a: int = 255) -> bool:
        """Set layer color/tint (RGBA)."""
        layer = self.get_layer(action_idx, frame_idx, layer_idx)
        if layer:
            layer.color = (int(r), int(g), int(b), int(a))
            # Ensure version supports color (2.0+)
            if self.act_data.version < (2, 0):
                self.act_data.version = (2, 0)
            self.modified = True
            return True
        return False
        
    def add_sound_event(self, name: str) -> int:
        """
        Add a sound event to the event list.
        Returns the event ID (index).
        """
        if not self.act_data: return -1
        
        # Check if already exists
        for i, event in enumerate(self.act_data.events):
            if event.name == name:
                return i
                
        # Add new
        self.act_data.events.append(ACTEvent(name=name))
        
        # Upgrade version if needed (events supported in 2.1+)
        if self.act_data.version < (2, 1):
            self.act_data.version = (2, 1)
            
        self.modified = True
        return len(self.act_data.events) - 1

    def set_frame_event(self, action_idx: int, frame_idx: int, event_name: Optional[str]) -> bool:
        """
        Set the sound event for a specific frame.
        Pass event_name=None to remove event.
        """
        if not self.act_data: return False
        
        frame = self.act_data.get_frame(action_idx, frame_idx)
        if not frame: return False
        
        if event_name is None:
            frame.event_id = -1
        else:
            event_id = self.add_sound_event(event_name)
            frame.event_id = event_id
            
        self.modified = True
        return True

    def set_frame_delay(self, action_idx: int, frame_idx: int, delay: float):
        """Set the duration (delay) of a specific frame."""
        if not self.act_data: return False
        frame = self.act_data.get_frame(action_idx, frame_idx)
        if frame:
            frame.delay = delay
            self.modified = True
            return True
        return False

if __name__ == "__main__":
    # Test stub
    print("ACT Editor Module Initialized")
