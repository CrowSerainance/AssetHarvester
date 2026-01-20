# ==============================================================================
# ACT PARSER MODULE
# ==============================================================================
# Parser for Ragnarok Online ACT (Action) files.
#
# ACT files define how sprites are animated and displayed. They work together
# with SPR files to create animated characters, monsters, and effects.
#
# Key Concepts:
#   - Action: A complete animation (e.g., "walk", "attack", "die")
#   - Frame: A single moment in an animation (one "frame" of animation)
#   - Layer: A sprite layer within a frame (characters have body, head, etc.)
#   - Anchor: Attachment points for connecting sprites together
#
# File Structure:
#   - Header: Signature "AC" + version + action count
#   - Actions: Each action contains multiple frames
#   - Frames: Each frame contains multiple layers + timing info
#   - Layers: Each layer references an SPR frame with transform data
#   - Events: Sound/effect triggers (in later versions)
#   - Anchors: Attachment points for combining sprites
#
# References:
#   - https://ragnarokresearchlab.github.io/file-formats/act/
#   - https://github.com/vthibault/roBrowser
#   - https://github.com/zhad3/zrenderer
#
# Usage Example:
#   parser = ACTParser()
#   action_data = parser.load("data/sprite/npc/merchant.act")
#   
#   # Get frame 0 of action 0 (usually "stand")
#   frame = action_data.get_frame(action_index=0, frame_index=0)
#   
#   # Iterate through layers to composite the sprite
#   for layer in frame.layers:
#       print(f"SPR frame {layer.sprite_index} at ({layer.x}, {layer.y})")
# ==============================================================================

import struct
from typing import List, Optional, Tuple, BinaryIO
from dataclasses import dataclass, field


# ==============================================================================
# CONSTANTS
# ==============================================================================

# ACT file signature (first 2 bytes)
ACT_SIGNATURE = b"AC"

# ACT version constants
ACT_VERSION_2_0 = (2, 0)  # Basic version
ACT_VERSION_2_1 = (2, 1)  # Added sound events
ACT_VERSION_2_2 = (2, 2)  # Added per-action animation speed (interval)
ACT_VERSION_2_3 = (2, 3)  # Added more layer properties
ACT_VERSION_2_4 = (2, 4)  # Added anchors
ACT_VERSION_2_5 = (2, 5)  # Current version with all features


# ==============================================================================
# STANDARD ACTION INDICES
# ==============================================================================
# These are the standard action indices used by player characters in RO.
# Monster and NPC actions may differ.

class ActionIndex:
    """
    Standard action indices for player characters.
    
    RO uses a consistent action numbering for player sprites:
    - 8 directions per action (south, SW, west, NW, north, NE, east, SE)
    - Actions repeat every 8 indices for each direction
    
    Direction order:
        0 = South (facing camera)
        1 = South-West
        2 = West
        3 = North-West
        4 = North (facing away)
        5 = North-East
        6 = East
        7 = South-East
    """
    # Standing/Idle - Actions 0-7
    STAND_S = 0
    STAND_SW = 1
    STAND_W = 2
    STAND_NW = 3
    STAND_N = 4
    STAND_NE = 5
    STAND_E = 6
    STAND_SE = 7
    
    # Walking - Actions 8-15
    WALK_S = 8
    WALK_SW = 9
    WALK_W = 10
    WALK_NW = 11
    WALK_N = 12
    WALK_NE = 13
    WALK_E = 14
    WALK_SE = 15
    
    # Sitting - Actions 16-23
    SIT_S = 16
    SIT_SW = 17
    SIT_W = 18
    SIT_NW = 19
    SIT_N = 20
    SIT_NE = 21
    SIT_E = 22
    SIT_SE = 23
    
    # Picking up item - Actions 24-31
    PICKUP_S = 24
    PICKUP_SW = 25
    PICKUP_W = 26
    PICKUP_NW = 27
    PICKUP_N = 28
    PICKUP_NE = 29
    PICKUP_E = 30
    PICKUP_SE = 31
    
    # Ready stance (combat) - Actions 32-39
    READY_S = 32
    READY_SW = 33
    READY_W = 34
    READY_NW = 35
    READY_N = 36
    READY_NE = 37
    READY_E = 38
    READY_SE = 39
    
    # Attack 1 - Actions 40-47
    ATTACK1_S = 40
    ATTACK1_SW = 41
    ATTACK1_W = 42
    ATTACK1_NW = 43
    ATTACK1_N = 44
    ATTACK1_NE = 45
    ATTACK1_E = 46
    ATTACK1_SE = 47
    
    # Hurt/Receiving damage - Actions 48-55
    HURT_S = 48
    HURT_SW = 49
    HURT_W = 50
    HURT_NW = 51
    HURT_N = 52
    HURT_NE = 53
    HURT_E = 54
    HURT_SE = 55
    
    # Freeze/Stun - Actions 56-63 (varies by class)
    
    # Dead/Lying - Actions 64-71
    DEAD_S = 64
    DEAD_SW = 65
    DEAD_W = 66
    DEAD_NW = 67
    DEAD_N = 68
    DEAD_NE = 69
    DEAD_E = 70
    DEAD_SE = 71
    
    # Casting - Actions 72-79
    CAST_S = 72
    CAST_SW = 73
    CAST_W = 74
    CAST_NW = 75
    CAST_N = 76
    CAST_NE = 77
    CAST_E = 78
    CAST_SE = 79
    
    # Attack 2 - Actions 80-87
    ATTACK2_S = 80
    ATTACK2_SW = 81
    ATTACK2_W = 82
    ATTACK2_NW = 83
    ATTACK2_N = 84
    ATTACK2_NE = 85
    ATTACK2_E = 86
    ATTACK2_SE = 87
    
    # Attack 3 - Actions 88-95
    ATTACK3_S = 88
    ATTACK3_SW = 89
    ATTACK3_W = 90
    ATTACK3_NW = 91
    ATTACK3_N = 92
    ATTACK3_NE = 93
    ATTACK3_E = 94
    ATTACK3_SE = 95


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class ACTLayer:
    """
    Represents a single sprite layer within an animation frame.
    
    Each layer draws one sprite (from the SPR file) at a specific position
    with optional transformations like flipping, rotation, scaling, and tinting.
    
    Multiple layers are composited back-to-front to form the complete frame.
    For example, a character might have separate layers for shadow, body,
    head, and headgear.
    
    Attributes:
        x (int):            X offset from frame center
        y (int):            Y offset from frame center
        sprite_index (int): Index of the sprite frame in the SPR file
        mirror (bool):      Whether to flip the sprite horizontally
        scale_x (float):    Horizontal scale factor (1.0 = normal)
        scale_y (float):    Vertical scale factor (1.0 = normal)
        rotation (int):     Rotation in degrees (0-360)
        sprite_type (int):  0 = indexed sprite, 1 = RGBA sprite
        width (int):        Display width (if different from sprite)
        height (int):       Display height (if different from sprite)
        color (tuple):      RGBA color tint (255, 255, 255, 255 = no tint)
    """
    x: int = 0
    y: int = 0
    sprite_index: int = 0
    mirror: bool = False
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation: int = 0
    sprite_type: int = 0  # 0 = indexed, 1 = rgba
    width: int = 0
    height: int = 0
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)  # RGBA tint
    
    def is_flipped(self) -> bool:
        """Check if layer is horizontally mirrored."""
        return self.mirror
    
    def get_scale(self) -> Tuple[float, float]:
        """Get scale factors as (x, y) tuple."""
        return (self.scale_x, self.scale_y)


@dataclass
class ACTAnchor:
    """
    Represents an anchor point for attaching sprites together.
    
    Anchors are used to connect different sprite parts:
    - Body anchor connects to head
    - Head anchor connects to headgear
    - Weapon anchors position weapon sprites
    
    Attributes:
        x (int): X coordinate of anchor point
        y (int): Y coordinate of anchor point
        attr (int): Anchor attribute/type (unknown purpose)
    """
    x: int = 0
    y: int = 0
    attr: int = 0


@dataclass
class ACTEvent:
    """
    Represents a sound or effect event trigger.
    
    Events are triggered at specific frames during animation playback.
    They're typically used for footstep sounds, attack impact sounds, etc.
    
    Attributes:
        name (str): Sound file name or event identifier
    """
    name: str = ""


@dataclass
class ACTFrame:
    """
    Represents a single frame within an action.
    
    A frame is one "moment" in an animation. It contains:
    - Multiple layers (sprites) composited together
    - Timing information (how long to display)
    - Event triggers (sounds, effects)
    - Anchor points (for connecting sprites)
    
    Attributes:
        layers (list):      List of ACTLayer objects to draw
        event_id (int):     Index into the events list (-1 = no event)
        anchors (list):     List of ACTAnchor points
        delay (float):      Frame delay in milliseconds (25ms default)
                           This is actually "interval" - frames are shown
                           for this duration before advancing
    """
    layers: List[ACTLayer] = field(default_factory=list)
    event_id: int = -1
    anchors: List[ACTAnchor] = field(default_factory=list)
    delay: float = 25.0  # Default 25ms = 40 FPS
    
    def get_layer_count(self) -> int:
        """Get number of layers in this frame."""
        return len(self.layers)
    
    def get_anchor(self, index: int) -> Optional[ACTAnchor]:
        """Get anchor by index."""
        if 0 <= index < len(self.anchors):
            return self.anchors[index]
        return None


@dataclass
class ACTAction:
    """
    Represents a complete animation action.
    
    An action is a sequence of frames that play in order to create
    an animation. Examples: walking cycle, attack animation, idle loop.
    
    Attributes:
        frames (list): List of ACTFrame objects in playback order
    """
    frames: List[ACTFrame] = field(default_factory=list)
    
    def get_frame_count(self) -> int:
        """Get number of frames in this action."""
        return len(self.frames)
    
    def get_frame(self, index: int) -> Optional[ACTFrame]:
        """Get frame by index."""
        if 0 <= index < len(self.frames):
            return self.frames[index]
        return None
    
    def get_total_duration(self) -> float:
        """
        Calculate total animation duration in milliseconds.
        
        Returns:
            Sum of all frame delays
        """
        return sum(frame.delay for frame in self.frames)


@dataclass
class ACTData:
    """
    Represents a complete ACT file.
    
    Contains all actions, events, and frame intervals for a sprite.
    
    Attributes:
        version (tuple):      ACT format version as (major, minor)
        actions (list):       List of ACTAction objects
        events (list):        List of ACTEvent objects (sound names)
        frame_intervals (list): Default intervals for each action
        filepath (str):       Original file path (for reference)
    """
    version: Tuple[int, int] = (2, 5)
    actions: List[ACTAction] = field(default_factory=list)
    events: List[ACTEvent] = field(default_factory=list)
    frame_intervals: List[float] = field(default_factory=list)
    filepath: str = ""
    
    def get_action_count(self) -> int:
        """Get total number of actions."""
        return len(self.actions)
    
    def get_action(self, index: int) -> Optional[ACTAction]:
        """Get action by index."""
        if 0 <= index < len(self.actions):
            return self.actions[index]
        return None
    
    def get_frame(self, action_index: int, frame_index: int) -> Optional[ACTFrame]:
        """
        Get a specific frame from an action.
        
        Args:
            action_index: Index of the action (0-based)
            frame_index: Index of the frame within the action (0-based)
            
        Returns:
            ACTFrame if valid indices, None otherwise
        """
        action = self.get_action(action_index)
        if action:
            return action.get_frame(frame_index)
        return None
    
    def get_event_name(self, event_id: int) -> str:
        """Get event/sound name by ID."""
        if 0 <= event_id < len(self.events):
            return self.events[event_id].name
        return ""


# ==============================================================================
# ACT PARSER CLASS
# ==============================================================================

class ACTParser:
    """
    Parser for Ragnarok Online ACT action/animation files.
    
    This class handles reading and decoding ACT files, including:
    - Version detection and handling
    - Action, frame, and layer parsing
    - Event and anchor extraction
    - Frame interval calculations
    
    Usage:
        parser = ACTParser()
        
        # Load from file path
        act_data = parser.load("path/to/sprite.act")
        
        # Or load from bytes
        act_data = parser.load_from_bytes(act_bytes)
        
        # Access animation data
        action = act_data.get_action(0)
        frame = action.get_frame(0)
        for layer in frame.layers:
            print(f"Draw sprite {layer.sprite_index}")
    """
    
    def __init__(self):
        """Initialize the ACT parser."""
        pass
    
    def load(self, filepath: str) -> Optional[ACTData]:
        """
        Load an ACT file from disk.
        
        Args:
            filepath: Path to the .act file
            
        Returns:
            ACTData object if successful, None on error
        """
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            
            act_data = self.load_from_bytes(data)
            if act_data:
                act_data.filepath = filepath
            return act_data
            
        except FileNotFoundError:
            print(f"[ERROR] ACT file not found: {filepath}")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to load ACT {filepath}: {e}")
            return None
    
    def load_from_bytes(self, data: bytes) -> Optional[ACTData]:
        """
        Load ACT data from raw bytes with full error handling.
        
        This is useful when reading directly from GRF archives.
        
        Args:
            data: Raw ACT file bytes
            
        Returns:
            ACTData object if successful, None on error
        """
        if not data or len(data) < 16:
            # Silently fail - might be incomplete data from GRF
            return None
        
        try:
            # Check signature
            if data[0:2] != ACT_SIGNATURE:
                # Silently fail - might be wrong file type
                return None
            
            # Read version (minor byte, major byte - little endian)
            version_minor = data[2]
            version_major = data[3]
            version = (version_major, version_minor)
            
            # Validate version (reasonable range: 1.0 to 3.0)
            if version_major < 1 or version_major > 3:
                # Invalid version - might be corrupted data
                return None
            
            # Read action count
            action_count = struct.unpack('<H', data[4:6])[0]
            
            # Validate action count (sanity)
            if action_count > 200:
                return None
            
            # Skip reserved bytes (10 bytes of zeros)
            offset = 16
            
            # Create ACT data object
            act_data = ACTData(version=version)
            
            # Parse each action
            for i in range(action_count):
                if offset >= len(data):
                    # Data truncated - stop silently
                    break
                try:
                    action, offset = self._read_action(data, offset, version)
                    if action:  # Only append if action was successfully parsed
                        act_data.actions.append(action)
                except (struct.error, ValueError) as e:
                    # Data corruption detected - stop parsing silently
                    # Don't spam errors for corrupted files
                    break
                except Exception as e:
                    # Unexpected error - stop parsing
                    break
            
            # Validate we got some actions
            if len(act_data.actions) == 0:
                # No valid actions parsed - file is likely corrupted
                return None
            
            # Read events (sound names) if version supports it
            if version >= ACT_VERSION_2_1 and offset < len(data):
                event_count = struct.unpack('<I', data[offset:offset + 4])[0]
                offset += 4
                
                for i in range(event_count):
                    event_name, offset = self._read_string(data, offset, 40)
                    act_data.events.append(ACTEvent(name=event_name))

            # Read animation speed per action (ACT v2.2+)
            # GRFEditor stores this as Action.AnimationSpeed, and the per-frame interval is (AnimationSpeed * 25ms).
            if version >= ACT_VERSION_2_2 and offset < len(data):
                speeds = []
                last_speed = 1.0
                for _ in act_data.actions:
                    if offset + 4 <= len(data):
                        last_speed = struct.unpack('<f', data[offset:offset + 4])[0]
                        offset += 4
                    speeds.append(last_speed)

                # Store per-action interval (ms) and also apply as default delay for every frame in that action
                act_data.frame_intervals = []
                for action, spd in zip(act_data.actions, speeds):
                    try:
                        interval_ms = float(spd) * 25.0
                    except Exception:
                        interval_ms = 25.0
                    if interval_ms <= 0:
                        interval_ms = 25.0
                    act_data.frame_intervals.append(interval_ms)
                    for fr in action.frames:
                        fr.delay = interval_ms

            # If no animation speeds exist (older versions or truncated tail), default to RO-ish interval (6 * 25ms = 150ms)
            else:
                default_interval = 150.0
                act_data.frame_intervals = []
                for action in act_data.actions:
                    act_data.frame_intervals.append(default_interval)
                    for fr in action.frames:
                        fr.delay = default_interval
            
            return act_data
            
        except Exception as e:
            print(f"[ERROR] Failed to parse ACT data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _read_action(self, data: bytes, offset: int, 
                     version: Tuple[int, int]) -> Tuple[ACTAction, int]:
        """
        Read a single action from ACT data with safety limits.
        
        Args:
            data: Full ACT file data
            offset: Current read position
            version: ACT file version
            
        Returns:
            Tuple of (ACTAction, new_offset)
        """
        action = ACTAction()
        
        # Read frame count
        if offset + 4 > len(data):
            raise struct.error(f"Not enough data for frame count at offset {offset}")
        
        frame_count = struct.unpack('<i', data[offset:offset + 4])[0]
        offset += 4
        
        # CRITICAL: Validate frame count to prevent infinite loops
        # Reasonable max: ~100 frames per action for RO sprites
        if frame_count > 200:
            raise ValueError(f"Invalid frame count: {frame_count} (max: 200)")
        if frame_count == 0xFFFFFFFF or frame_count > 0x7FFFFFFF:
            raise ValueError(f"Corrupted frame count: {frame_count}")
        
        # Parse each frame with progress check
        for i in range(frame_count):
            if offset >= len(data):
                # Data truncated - return what we have
                break
            try:
                frame, offset = self._read_frame(data, offset, version)
                action.frames.append(frame)
            except (struct.error, ValueError) as e:
                # Stop on error - don't continue with corrupted data
                break
        
        return action, offset
    
    def _read_frame(self, data: bytes, offset: int,
                    version: Tuple[int, int]) -> Tuple[ACTFrame, int]:
        """
        Read a single frame from ACT data.
        
        Args:
            data: Full ACT file data
            offset: Current read position
            version: ACT file version
            
        Returns:
            Tuple of (ACTFrame, new_offset)
        """
        frame = ACTFrame()
        
        # Validate offset for frame header / padding block
        if offset + 32 > len(data):
            raise struct.error(
                f"Not enough data for frame padding at offset {offset} (need 32 bytes, have {len(data) - offset})"
            )

        # Skip frame padding block (32 bytes)
        offset += 32
        
        # Validate offset for layer count
        if offset + 4 > len(data):
            raise struct.error(f"Not enough data for layer count at offset {offset} (need 4 bytes, have {len(data) - offset})")
        
        # Read layer count
        layer_count = struct.unpack('<i', data[offset:offset + 4])[0]
        offset += 4

        if layer_count < 0:
            raise ValueError(f"Invalid layer count: {layer_count}")
        
        # Validate layer count (sanity check - max reasonable is ~50 layers per frame)
        if layer_count > 100:
            # Invalid layer count - data is corrupted
            raise ValueError(f"Invalid layer count: {layer_count} (max expected: 100)")
        
        # Also check for negative values when interpreted as signed
        if layer_count == 0xFFFFFFFF or layer_count > 0x7FFFFFFF:
            raise ValueError(f"Invalid layer count (likely corruption): {layer_count}")
        
        # Parse each layer
        for i in range(layer_count):
            layer, offset = self._read_layer(data, offset, version)
            frame.layers.append(layer)
        
        # Read event ID (int32, -1 = no event)
        if version >= ACT_VERSION_2_0:
            if offset + 4 > len(data):
                raise struct.error(f"Not enough data for event_id at offset {offset} (need 4 bytes, have {len(data) - offset})")
            frame.event_id = struct.unpack('<i', data[offset:offset + 4])[0]
            offset += 4
        
        # Anchors (ACT v2.3+)
        if version >= ACT_VERSION_2_3:
            # Anchor section begins with an int32 count
            if offset + 4 <= len(data):
                anchor_count = struct.unpack('<I', data[offset:offset + 4])[0]
                offset += 4

                # Sanity cap
                if anchor_count > 2000:
                    anchor_count = 0

                for _ in range(anchor_count):
                    # Each anchor: 4 bytes unknown + x(int32) + y(int32) + other(int32)
                    if offset + 16 > len(data):
                        break
                    offset += 4  # unknown
                    x = struct.unpack('<i', data[offset:offset + 4])[0]
                    offset += 4
                    y = struct.unpack('<i', data[offset:offset + 4])[0]
                    offset += 4
                    other = struct.unpack('<i', data[offset:offset + 4])[0]
                    offset += 4
                    frame.anchors.append(ACTAnchor(x=x, y=y, attr=other))
        
        return frame, offset
    
    def _read_layer(self, data: bytes, offset: int,
                    version: Tuple[int, int]) -> Tuple[ACTLayer, int]:
        """
        Read a single layer from ACT data.
        
        Args:
            data: Full ACT file data
            offset: Current read position
            version: ACT file version
            
        Returns:
            Tuple of (ACTLayer, new_offset)
        """
        layer = ACTLayer()
        
        # Validate offset for position x
        if offset + 4 > len(data):
            raise struct.error(f"Not enough data for layer.x at offset {offset} (need 4 bytes, have {len(data) - offset})")
        
        # Read position (x, y as int32)
        layer.x = struct.unpack('<i', data[offset:offset + 4])[0]
        offset += 4
        
        if offset + 4 > len(data):
            raise struct.error(f"Not enough data for layer.y at offset {offset} (need 4 bytes, have {len(data) - offset})")
        
        layer.y = struct.unpack('<i', data[offset:offset + 4])[0]
        offset += 4
        
        # Read sprite index (int32)
        if offset + 4 > len(data):
            raise struct.error(f"Not enough data for layer.sprite_index at offset {offset} (need 4 bytes, have {len(data) - offset})")
        
        layer.sprite_index = struct.unpack('<i', data[offset:offset + 4])[0]
        offset += 4
        
        # Read mirror flag (int32, 0 or 1)
        if offset + 4 > len(data):
            raise struct.error(f"Not enough data for layer.mirror at offset {offset} (need 4 bytes, have {len(data) - offset})")
        
        mirror_val = struct.unpack('<i', data[offset:offset + 4])[0]
        layer.mirror = (mirror_val != 0)
        offset += 4
        
        # Version 2.0+ has additional properties
        if version >= ACT_VERSION_2_0:
            # Color (RGBA, 4 bytes)
            if offset + 4 > len(data):
                raise struct.error(
                    f"Not enough data for layer.color at offset {offset} (need 4 bytes, have {len(data) - offset})"
                )

            r = data[offset]
            g = data[offset + 1]
            b = data[offset + 2]
            a = data[offset + 3]
            layer.color = (r, g, b, a)
            offset += 4

            # ScaleX (float32)
            if offset + 4 > len(data):
                raise struct.error(
                    f"Not enough data for layer.scale_x at offset {offset} (need 4 bytes, have {len(data) - offset})"
                )

            layer.scale_x = struct.unpack('<f', data[offset:offset + 4])[0]
            offset += 4

            # ScaleY:
            # - Versions 2.0–2.3 do NOT store ScaleY; it is identical to ScaleX
            # - Version 2.4+ stores ScaleY as an additional float32
            layer.scale_y = layer.scale_x
            if version >= ACT_VERSION_2_4:
                if offset + 4 > len(data):
                    raise struct.error(
                        f"Not enough data for layer.scale_y at offset {offset} (need 4 bytes, have {len(data) - offset})"
                    )

                layer.scale_y = struct.unpack('<f', data[offset:offset + 4])[0]
                offset += 4

            # Read rotation (int32, degrees)
            if offset + 4 > len(data):
                raise struct.error(
                    f"Not enough data for layer.rotation at offset {offset} (need 4 bytes, have {len(data) - offset})"
                )

            layer.rotation = struct.unpack('<i', data[offset:offset + 4])[0]
            offset += 4

            # Read sprite type (int32, 0 = indexed, 1 = rgba)
            if offset + 4 > len(data):
                raise struct.error(
                    f"Not enough data for layer.sprite_type at offset {offset} (need 4 bytes, have {len(data) - offset})"
                )

            layer.sprite_type = struct.unpack('<i', data[offset:offset + 4])[0]
            offset += 4

            # Version 2.5+ has width/height fields (but many renderers override these with real sprite size)
            if version >= ACT_VERSION_2_5:
                if offset + 8 > len(data):
                    raise struct.error(
                        f"Not enough data for layer.width/height at offset {offset} (need 8 bytes, have {len(data) - offset})"
                    )

                layer.width = struct.unpack('<i', data[offset:offset + 4])[0]
                offset += 4
                layer.height = struct.unpack('<i', data[offset:offset + 4])[0]
                offset += 4
        
        return layer, offset
    
    def save(self, act_data: ACTData, filepath: str) -> bool:
        """
        Save ACT data to a file.
        
        Args:
            act_data: Data to save
            filepath: Output path
            
        Returns:
            True if successful
        """
        try:
            data = self.save_to_bytes(act_data)
            if not data:
                return False
                
            with open(filepath, 'wb') as f:
                f.write(data)
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save ACT to {filepath}: {e}")
            return False

    def save_to_bytes(self, act_data: ACTData) -> Optional[bytes]:
        """
        Serialize ACT data to bytes.
        
        Args:
            act_data: Data to serialize
            
        Returns:
            Bytes object or None on error
        """
        try:
            out = bytearray()
            
            # 1. Header
            out.extend(ACT_SIGNATURE)
            
            # Version (default to 2.5 if not specified, or use existing)
            # We force 2.5 to ensure all features (scale, color, anchors) work
            ver_major, ver_minor = act_data.version
            if ver_major < 2 or (ver_major == 2 and ver_minor < 5):
                # Upgrade to 2.5 to support new features
                ver_major, ver_minor = 2, 5
            
            out.append(ver_minor)
            out.append(ver_major)
            
            # Action count
            action_count = len(act_data.actions)
            out.extend(struct.pack('<H', action_count))
            
            # Reserved (10 bytes)
            out.extend(b'\x00' * 10)
            
            # 2. Actions
            for action in act_data.actions:
                self._write_action(out, action, (ver_major, ver_minor))
                
            # 3. Events (Sound) - Version 2.1+
            if (ver_major > 2) or (ver_major == 2 and ver_minor >= 1):
                event_count = len(act_data.events)
                out.extend(struct.pack('<I', event_count))
                for event in act_data.events:
                    # Write fixed length string (40 chars)
                    name_bytes = event.name.encode('latin-1')[:39]
                    out.extend(name_bytes)
                    out.extend(b'\x00' * (40 - len(name_bytes)))
            
            # 4. Animation Speeds - Version 2.2+
            if (ver_major > 2) or (ver_major == 2 and ver_minor >= 2):
                # We need to reconstruct delays per action.
                # ACT format uses a multiplier float, where detail = multiplier * 25ms
                # We'll take the average delay of frames in action 
                for action in act_data.actions:
                    avg_delay = 25.0
                    if action.frames:
                        avg_delay = sum(f.delay for f in action.frames) / len(action.frames)
                    
                    factor = avg_delay / 25.0
                    out.extend(struct.pack('<f', factor))
                    
            return bytes(out)
            
        except Exception as e:
            print(f"[ERROR] Failed to serialize ACT data: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _write_action(self, out: bytearray, action: ACTAction, version: Tuple[int, int]):
        """Write action data."""
        # Frame count
        frame_count = len(action.frames)
        out.extend(struct.pack('<i', frame_count))
        
        for frame in action.frames:
            self._write_frame(out, frame, version)
            
    def _write_frame(self, out: bytearray, frame: ACTFrame, version: Tuple[int, int]):
        """Write frame data."""
        # Frame padding (32 bytes unknown)
        out.extend(b'\x00' * 32)
        
        # Layer count
        layer_count = len(frame.layers)
        out.extend(struct.pack('<i', layer_count))
        
        for layer in frame.layers:
            self._write_layer(out, layer, version)
            
        # Event ID - Version 2.0+
        if version >= ACT_VERSION_2_0:
            out.extend(struct.pack('<i', frame.event_id))
            
        # Anchors - Version 2.3+
        if version >= ACT_VERSION_2_3:
            anchor_count = len(frame.anchors)
            out.extend(struct.pack('<i', anchor_count))
            
            for anchor in frame.anchors:
                # 4 bytes unknown (reserved)
                out.extend(b'\x00\x00\x00\x00')
                out.extend(struct.pack('<i', anchor.x))
                out.extend(struct.pack('<i', anchor.y))
                out.extend(struct.pack('<i', anchor.attr))

    def _write_layer(self, out: bytearray, layer: ACTLayer, version: Tuple[int, int]):
        """Write layer data."""
        # Position
        out.extend(struct.pack('<i', layer.x))
        out.extend(struct.pack('<i', layer.y))
        
        # Sprite index
        out.extend(struct.pack('<i', layer.sprite_index))
        
        # Mirror
        out.extend(struct.pack('<i', 1 if layer.mirror else 0))
        
        # Version 2.0+ extra fields
        if version >= ACT_VERSION_2_0:
            # Color (RGBA)
            out.append(layer.color[0]) # R
            out.append(layer.color[1]) # G
            out.append(layer.color[2]) # B
            out.append(layer.color[3]) # A
            
            # Scale X
            out.extend(struct.pack('<f', layer.scale_x))
            
            # Scale Y - Version 2.4+
            if version >= ACT_VERSION_2_4:
                out.extend(struct.pack('<f', layer.scale_y))
                
            # Rotation
            out.extend(struct.pack('<i', layer.rotation))
            
            # Sprite Type
            out.extend(struct.pack('<i', layer.sprite_type))
            
            # Width/Height - Version 2.5+
            if version >= ACT_VERSION_2_5:
                out.extend(struct.pack('<i', layer.width))
                out.extend(struct.pack('<i', layer.height))

    def _read_string(self, data: bytes, offset: int, 
                     max_length: int) -> Tuple[str, int]:
        """
        Read a fixed-length null-terminated string.
        
        Args:
            data: Data buffer
            offset: Start position
            max_length: Maximum string length
            
        Returns:
            Tuple of (string, new_offset)
        """
        end = offset + max_length
        
        # Find null terminator
        string_bytes = data[offset:end]
        null_pos = string_bytes.find(b'\x00')
        
        if null_pos >= 0:
            string_bytes = string_bytes[:null_pos]
        
        # Try different encodings
        try:
            result = string_bytes.decode('utf-8')
        except:
            try:
                result = string_bytes.decode('euc-kr')
            except:
                result = string_bytes.decode('latin-1')
        
        return result, end


# ==============================================================================
# STANDALONE TEST
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        parser = ACTParser()
        act_data = parser.load(sys.argv[1])
        
        if act_data:
            print(f"ACT Version: {act_data.version}")
            print(f"Actions: {act_data.get_action_count()}")
            print(f"Events: {len(act_data.events)}")
            
            # Show first action info
            action = act_data.get_action(0)
            if action:
                print(f"\nAction 0 has {action.get_frame_count()} frames")
                
                frame = action.get_frame(0)
                if frame:
                    print(f"  Frame 0 has {frame.get_layer_count()} layers")
                    for i, layer in enumerate(frame.layers):
                        print(f"    Layer {i}: sprite {layer.sprite_index} at ({layer.x}, {layer.y})")
    else:
        print("Usage: python act_parser.py <action.act>")
