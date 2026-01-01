# ==============================================================================
# SPR PARSER MODULE
# ==============================================================================
# Parser for Ragnarok Online SPR (Sprite) files.
#
# SPR files contain 2D sprite images used for characters, monsters, items,
# and effects in Ragnarok Online. The format supports:
#
#   - Indexed color images (256 colors using a palette)
#   - RGBA images (32-bit true color, added in later versions)
#   - Multiple frames per sprite file
#   - RLE compression for indexed images
#
# File Format Versions:
#   - Version 1.0: Basic indexed sprites
#   - Version 1.1: Added RLE compression for indexed sprites
#   - Version 2.0: Added RGBA sprite support
#   - Version 2.1: Current version with both indexed and RGBA
#
# References:
#   - https://ragnarokresearchlab.github.io/file-formats/spr/
#   - https://github.com/vthibault/roBrowser
#   - https://github.com/zhad3/zrenderer
#
# Usage Example:
#   parser = SPRParser()
#   sprite = parser.load("data/sprite/npc/merchant.spr")
#   
#   # Get a specific frame as a PIL Image
#   image = sprite.get_frame_image(0)
#   image.save("frame_0.png")
#   
#   # Apply a custom palette
#   sprite.set_palette(custom_palette_data)
#   recolored = sprite.get_frame_image(0)
# ==============================================================================

import struct
from typing import List, Optional, Tuple, BinaryIO
from dataclasses import dataclass, field

# ==============================================================================
# Try to import PIL/Pillow for image handling
# If not available, the parser will still work but image conversion won't
# ==============================================================================
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[WARN] Pillow not installed. Image conversion disabled.")
    print("       Install with: pip install Pillow")


# ==============================================================================
# CONSTANTS
# ==============================================================================

# SPR file signature (first 2 bytes)
SPR_SIGNATURE = b"SP"

# SPR version constants
# Version is stored as two bytes: minor, major
# So version 2.1 is stored as bytes [1, 2]
SPR_VERSION_1_0 = (1, 0)  # Basic indexed sprites
SPR_VERSION_1_1 = (1, 1)  # Added RLE compression
SPR_VERSION_2_0 = (2, 0)  # Added RGBA support
SPR_VERSION_2_1 = (2, 1)  # Current version

# Default palette (grayscale)
# Used when no palette is embedded in the file
# Creates 256 RGBA colors where each color is (i, i, i, 255) for grayscale
# 256 colors * 4 bytes (RGBA) = 1024 bytes total
DEFAULT_PALETTE = bytes([val for i in range(256) for val in (i, i, i, 255)])


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class SPRFrame:
    """
    Represents a single frame/image in an SPR file.
    
    Each frame can be either:
    - Indexed: 8-bit pixels referencing a 256-color palette
    - RGBA: 32-bit true color pixels (red, green, blue, alpha)
    
    Attributes:
        width (int):       Width of the frame in pixels
        height (int):      Height of the frame in pixels
        frame_type (str):  Either "indexed" or "rgba"
        data (bytes):      Raw pixel data
                          - For indexed: 1 byte per pixel (palette index)
                          - For RGBA: 4 bytes per pixel (R, G, B, A)
    """
    width: int = 0
    height: int = 0
    frame_type: str = "indexed"  # "indexed" or "rgba"
    data: bytes = b""
    
    def get_size(self) -> Tuple[int, int]:
        """
        Get frame dimensions.
        
        Returns:
            Tuple of (width, height)
        """
        return (self.width, self.height)
    
    def is_indexed(self) -> bool:
        """Check if this frame uses indexed color."""
        return self.frame_type == "indexed"
    
    def is_rgba(self) -> bool:
        """Check if this frame uses RGBA color."""
        return self.frame_type == "rgba"


@dataclass
class SPRSprite:
    """
    Represents a complete SPR sprite file.
    
    An SPR file contains multiple frames that can be used in animations.
    Character sprites typically have frames for different directions and
    actions (standing, walking, attacking, etc.).
    
    Attributes:
        version (tuple):       SPR format version as (major, minor)
        indexed_frames (list): List of indexed color frames
        rgba_frames (list):    List of RGBA color frames
        palette (bytes):       256-color palette (1024 bytes: 256 * RGBA)
        filepath (str):        Original file path (for reference)
    
    Frame Indexing:
        - Indexed frames come first, numbered 0 to (indexed_count - 1)
        - RGBA frames come after, numbered indexed_count to (total - 1)
        - Use get_frame() with the global index to get any frame
    """
    version: Tuple[int, int] = (2, 1)
    indexed_frames: List[SPRFrame] = field(default_factory=list)
    rgba_frames: List[SPRFrame] = field(default_factory=list)
    palette: bytes = b""
    filepath: str = ""
    
    def get_total_frames(self) -> int:
        """
        Get total number of frames (indexed + RGBA).
        
        Returns:
            Total frame count
        """
        return len(self.indexed_frames) + len(self.rgba_frames)
    
    def get_indexed_count(self) -> int:
        """Get number of indexed color frames."""
        return len(self.indexed_frames)
    
    def get_rgba_count(self) -> int:
        """Get number of RGBA color frames."""
        return len(self.rgba_frames)
    
    def get_frame(self, index: int) -> Optional[SPRFrame]:
        """
        Get a frame by global index.
        
        The global index spans both indexed and RGBA frames:
        - Index 0 to (indexed_count - 1): Indexed frames
        - Index indexed_count to (total - 1): RGBA frames
        
        Args:
            index: Global frame index
            
        Returns:
            SPRFrame if valid index, None otherwise
        """
        indexed_count = len(self.indexed_frames)
        
        if index < 0:
            return None
        elif index < indexed_count:
            return self.indexed_frames[index]
        elif index < indexed_count + len(self.rgba_frames):
            return self.rgba_frames[index - indexed_count]
        else:
            return None
    
    def set_palette(self, palette_data: bytes):
        """
        Set a custom palette for indexed frames.
        
        This allows recoloring sprites (e.g., hair dyes, class palettes).
        The palette should be 1024 bytes (256 colors * 4 bytes RGBA each).
        
        Args:
            palette_data: Raw palette bytes (1024 bytes expected)
        """
        if len(palette_data) >= 1024:
            self.palette = palette_data[:1024]
        else:
            # Pad with zeros if too short
            self.palette = palette_data + b'\x00' * (1024 - len(palette_data))
    
    def get_frame_image(self, index: int) -> Optional['Image.Image']:
        """
        Convert a frame to a PIL Image.
        
        This applies the palette to indexed frames and handles transparency.
        Index 0 in the palette is treated as transparent (RO convention).
        
        Args:
            index: Global frame index
            
        Returns:
            PIL Image in RGBA mode, or None if PIL unavailable or invalid index
        """
        if not PIL_AVAILABLE:
            print("[ERROR] Pillow required for image conversion")
            return None
        
        frame = self.get_frame(index)
        if frame is None:
            return None
        
        if frame.width == 0 or frame.height == 0:
            # Empty frame, return 1x1 transparent image
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        
        if frame.is_rgba():
            # RGBA frame - direct conversion
            # Note: RO stores RGBA as ABGR in some versions
            try:
                img = Image.frombytes("RGBA", (frame.width, frame.height), frame.data)
                # Convert ABGR to RGBA if needed
                r, g, b, a = img.split()
                img = Image.merge("RGBA", (r, g, b, a))
                return img
            except Exception as e:
                print(f"[ERROR] Failed to convert RGBA frame: {e}")
                return None
        
        else:
            # Indexed frame - apply palette
            try:
                # Create RGBA image
                img = Image.new("RGBA", (frame.width, frame.height))
                pixels = img.load()
                
                # Apply palette to each pixel
                palette = self.palette if self.palette else DEFAULT_PALETTE
                
                for y in range(frame.height):
                    for x in range(frame.width):
                        pixel_idx = y * frame.width + x
                        if pixel_idx < len(frame.data):
                            color_idx = frame.data[pixel_idx]
                            
                            # Get color from palette (4 bytes per color: RGBA)
                            pal_offset = color_idx * 4
                            if pal_offset + 4 <= len(palette):
                                r = palette[pal_offset]
                                g = palette[pal_offset + 1]
                                b = palette[pal_offset + 2]
                                a = palette[pal_offset + 3]
                                
                                # Index 0 is transparent in RO sprites
                                if color_idx == 0:
                                    a = 0
                                
                                pixels[x, y] = (r, g, b, a)
                            else:
                                pixels[x, y] = (0, 0, 0, 0)
                        else:
                            pixels[x, y] = (0, 0, 0, 0)
                
                return img
                
            except Exception as e:
                print(f"[ERROR] Failed to convert indexed frame: {e}")
                return None


# ==============================================================================
# SPR PARSER CLASS
# ==============================================================================

class SPRParser:
    """
    Parser for Ragnarok Online SPR sprite files.
    
    This class handles reading and decoding SPR files, including:
    - Version detection and handling
    - RLE decompression for indexed frames
    - Palette extraction
    - Both indexed and RGBA frame types
    
    Usage:
        parser = SPRParser()
        
        # Load from file path
        sprite = parser.load("path/to/sprite.spr")
        
        # Or load from bytes
        sprite = parser.load_from_bytes(spr_data)
        
        # Access frames
        frame = sprite.get_frame(0)
        image = sprite.get_frame_image(0)
    """
    
    def __init__(self):
        """Initialize the SPR parser."""
        pass
    
    def load(self, filepath: str) -> Optional[SPRSprite]:
        """
        Load an SPR file from disk.
        
        Args:
            filepath: Path to the .spr file
            
        Returns:
            SPRSprite object if successful, None on error
        """
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            
            sprite = self.load_from_bytes(data)
            if sprite:
                sprite.filepath = filepath
            return sprite
            
        except FileNotFoundError:
            print(f"[ERROR] SPR file not found: {filepath}")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to load SPR {filepath}: {e}")
            return None
    
    def load_from_bytes(self, data: bytes) -> Optional[SPRSprite]:
        """
        Load an SPR sprite from raw bytes.
        
        This is useful when reading sprites directly from GRF archives
        without extracting them to disk first.
        
        Args:
            data: Raw SPR file bytes
            
        Returns:
            SPRSprite object if successful, None on error
        """
        try:
            # Check minimum size
            if len(data) < 6:
                print("[ERROR] SPR data too small")
                return None
            
            # Check signature
            if data[0:2] != SPR_SIGNATURE:
                print(f"[ERROR] Invalid SPR signature: {data[0:2]}")
                return None
            
            # Read version (minor byte, major byte)
            version_minor = data[2]
            version_major = data[3]
            version = (version_major, version_minor)
            
            # Create sprite object
            sprite = SPRSprite(version=version)
            
            # Read frame counts
            # Offset 4-5: indexed frame count (uint16)
            # Offset 6-7: rgba frame count (uint16) - only in version >= 2.0
            indexed_count = struct.unpack('<H', data[4:6])[0]
            
            rgba_count = 0
            offset = 6
            
            if version >= SPR_VERSION_2_0:
                rgba_count = struct.unpack('<H', data[6:8])[0]
                offset = 8
            
            # Read indexed frames
            for i in range(indexed_count):
                frame, offset = self._read_indexed_frame(data, offset, version)
                sprite.indexed_frames.append(frame)
            
            # Read RGBA frames
            for i in range(rgba_count):
                frame, offset = self._read_rgba_frame(data, offset)
                sprite.rgba_frames.append(frame)
            
            # Read palette (at the end of file, 1024 bytes)
            # Palette is present in all versions
            if offset + 1024 <= len(data):
                sprite.palette = data[offset:offset + 1024]
            else:
                # Use default grayscale palette
                sprite.palette = DEFAULT_PALETTE
            
            return sprite
            
        except Exception as e:
            print(f"[ERROR] Failed to parse SPR data: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _read_indexed_frame(self, data: bytes, offset: int, 
                           version: Tuple[int, int]) -> Tuple[SPRFrame, int]:
        """
        Read an indexed color frame from SPR data.
        
        Indexed frames can be either raw or RLE compressed depending on version.
        
        Args:
            data: Full SPR file data
            offset: Current read position
            version: SPR file version
            
        Returns:
            Tuple of (SPRFrame, new_offset)
        """
        # Read width and height (uint16 each)
        width = struct.unpack('<H', data[offset:offset + 2])[0]
        height = struct.unpack('<H', data[offset + 2:offset + 4])[0]
        offset += 4
        
        frame = SPRFrame(
            width=width,
            height=height,
            frame_type="indexed"
        )
        
        if width == 0 or height == 0:
            # Empty frame
            frame.data = b""
            return frame, offset
        
        # Version 1.1+ uses RLE compression for indexed frames
        if version >= SPR_VERSION_1_1:
            # Read compressed size (uint16)
            compressed_size = struct.unpack('<H', data[offset:offset + 2])[0]
            offset += 2
            
            # Read compressed data
            compressed_data = data[offset:offset + compressed_size]
            offset += compressed_size
            
            # Decompress RLE
            frame.data = self._decompress_rle(compressed_data, width * height)
        else:
            # Raw pixel data
            pixel_count = width * height
            frame.data = data[offset:offset + pixel_count]
            offset += pixel_count
        
        return frame, offset
    
    def _read_rgba_frame(self, data: bytes, offset: int) -> Tuple[SPRFrame, int]:
        """
        Read an RGBA color frame from SPR data.
        
        RGBA frames are stored uncompressed as raw pixel data.
        Each pixel is 4 bytes (Red, Green, Blue, Alpha).
        
        Args:
            data: Full SPR file data
            offset: Current read position
            
        Returns:
            Tuple of (SPRFrame, new_offset)
        """
        # Read width and height (uint16 each)
        width = struct.unpack('<H', data[offset:offset + 2])[0]
        height = struct.unpack('<H', data[offset + 2:offset + 4])[0]
        offset += 4
        
        frame = SPRFrame(
            width=width,
            height=height,
            frame_type="rgba"
        )
        
        if width == 0 or height == 0:
            frame.data = b""
            return frame, offset
        
        # RGBA data: 4 bytes per pixel
        pixel_count = width * height * 4
        frame.data = data[offset:offset + pixel_count]
        offset += pixel_count
        
        return frame, offset
    
    def _decompress_rle(self, compressed: bytes, expected_size: int) -> bytes:
        """
        Decompress RLE-encoded indexed frame data.
        
        RO uses a simple RLE scheme:
        - If a byte is 0x00, the next byte is a run length of zeros
        - Otherwise, the byte is a literal pixel value
        
        Args:
            compressed: RLE-compressed data
            expected_size: Expected decompressed size (width * height)
            
        Returns:
            Decompressed pixel data
        """
        result = bytearray()
        i = 0
        
        while i < len(compressed) and len(result) < expected_size:
            byte = compressed[i]
            i += 1
            
            if byte == 0:
                # Run of zeros
                if i < len(compressed):
                    run_length = compressed[i]
                    i += 1
                    result.extend([0] * run_length)
            else:
                # Literal byte
                result.append(byte)
        
        # Pad or truncate to expected size
        if len(result) < expected_size:
            result.extend([0] * (expected_size - len(result)))
        elif len(result) > expected_size:
            result = result[:expected_size]
        
        return bytes(result)


# ==============================================================================
# PALETTE UTILITIES
# ==============================================================================

def load_palette(filepath: str) -> Optional[bytes]:
    """
    Load a palette file (.pal).
    
    RO palette files are simple 1024-byte files containing 256 RGBA colors.
    These are used for recoloring sprites (hair dyes, class variations, etc.).
    
    Args:
        filepath: Path to .pal file
        
    Returns:
        Palette data (1024 bytes) or None on error
    """
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        
        if len(data) >= 1024:
            return data[:1024]
        else:
            print(f"[WARN] Palette file too small: {filepath}")
            return data + b'\x00' * (1024 - len(data))
            
    except Exception as e:
        print(f"[ERROR] Failed to load palette {filepath}: {e}")
        return None


def create_palette_from_colors(colors: List[Tuple[int, int, int, int]]) -> bytes:
    """
    Create a palette from a list of RGBA color tuples.
    
    Args:
        colors: List of up to 256 (R, G, B, A) tuples
        
    Returns:
        Palette data (1024 bytes)
    """
    palette = bytearray()
    
    for i in range(256):
        if i < len(colors):
            r, g, b, a = colors[i]
            palette.extend([r, g, b, a])
        else:
            palette.extend([0, 0, 0, 0])
    
    return bytes(palette)


# ==============================================================================
# STANDALONE TEST
# ==============================================================================

if __name__ == "__main__":
    # Quick test if run directly
    import sys
    
    if len(sys.argv) > 1:
        parser = SPRParser()
        sprite = parser.load(sys.argv[1])
        
        if sprite:
            print(f"SPR Version: {sprite.version}")
            print(f"Indexed Frames: {sprite.get_indexed_count()}")
            print(f"RGBA Frames: {sprite.get_rgba_count()}")
            print(f"Total Frames: {sprite.get_total_frames()}")
            
            if PIL_AVAILABLE and sprite.get_total_frames() > 0:
                img = sprite.get_frame_image(0)
                if img:
                    img.save("test_frame.png")
                    print("Saved first frame to test_frame.png")
    else:
        print("Usage: python spr_parser.py <sprite.spr>")
