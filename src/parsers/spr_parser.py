# ==============================================================================
# SPR PARSER MODULE - FIXED VERSION (Matches GRFEditor Reference)
# ==============================================================================
# Parser for Ragnarok Online SPR (Sprite) files.
# SPR files contain STATIC FRAMES. For animations, use ACT files.
#
# CRITICAL FIXES based on GRFEditor reference implementation:
#   1. BGRA32 images: Vertical flip required (stored bottom-to-top)
#   2. Channel order: File stores ARGB → convert to RGBA (not ABGR)
#   3. Palette: Always read from last 1024 bytes of file
#   4. Palette alpha: All colors = 255, index 0 = 0 (transparent)
#   5. RLE: Only for version >= 2.1 indexed images
# ==============================================================================

import struct
from typing import List, Optional, Tuple
from dataclasses import dataclass, field

# ==============================================================================
# Import dependencies
# ==============================================================================
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================

SPR_SIGNATURE = b"SP"

# Default grayscale palette (RGBA format, 256 colors × 4 bytes = 1024 bytes)
# All colors have alpha=255 except index 0 which has alpha=0 (transparent)
DEFAULT_PALETTE = bytes([
    (i if idx > 0 else 0) if channel < 3 else (255 if idx > 0 else 0)
    for idx in range(256)
    for channel, i in enumerate([idx, idx, idx, 255])
])


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class SPRFrame:
    """
    Represents a single frame/image in an SPR file.
    
    Attributes:
        width: Frame width in pixels
        height: Frame height in pixels
        frame_type: Either "indexed" (palette-based) or "rgba" (32-bit color)
        data: Raw pixel data (indexed = 1 byte/pixel, rgba = 4 bytes/pixel)
    """
    width: int = 0
    height: int = 0
    frame_type: str = "indexed"
    data: bytes = b""
    
    def is_indexed(self) -> bool:
        """Check if this is a palette-indexed frame."""
        return self.frame_type == "indexed"
    
    def is_rgba(self) -> bool:
        """Check if this is a 32-bit RGBA frame."""
        return self.frame_type == "rgba"


@dataclass  
class SPRSprite:
    """
    Represents a complete SPR sprite file.
    
    SPR files contain:
      - Header with version and frame counts
      - Indexed (palette-based) frames
      - RGBA (32-bit) frames  
      - A 256-color palette (1024 bytes)
    
    Attributes:
        version: SPR format version as (major, minor) tuple
        indexed_frames: List of palette-indexed frames
        rgba_frames: List of 32-bit RGBA frames
        palette: 1024-byte palette (256 colors × 4 bytes RGBA)
        filepath: Original file path (if loaded from file)
    """
    version: Tuple[int, int] = (2, 1)
    indexed_frames: List[SPRFrame] = field(default_factory=list)
    rgba_frames: List[SPRFrame] = field(default_factory=list)
    palette: bytes = b""
    filepath: str = ""
    
    def get_total_frames(self) -> int:
        """Get total number of frames (indexed + RGBA)."""
        return len(self.indexed_frames) + len(self.rgba_frames)
    
    def get_indexed_count(self) -> int:
        """Get number of palette-indexed frames."""
        return len(self.indexed_frames)
    
    def get_rgba_count(self) -> int:
        """Get number of 32-bit RGBA frames."""
        return len(self.rgba_frames)
    
    def get_frame(self, index: int) -> Optional[SPRFrame]:
        """
        Get frame by absolute index.
        
        Indexed frames come first (0 to indexed_count-1),
        then RGBA frames (indexed_count to total-1).
        
        Args:
            index: Absolute frame index
            
        Returns:
            SPRFrame or None if index out of range
        """
        ic = len(self.indexed_frames)
        if index < 0:
            return None
        elif index < ic:
            return self.indexed_frames[index]
        elif index < ic + len(self.rgba_frames):
            return self.rgba_frames[index - ic]
        return None
    
    def set_palette(self, palette_data: bytes):
        """
        Set the sprite palette.
        
        Palette must be 1024 bytes (256 colors × 4 bytes RGBA).
        Will be padded or truncated to correct size.
        
        Args:
            palette_data: Raw palette bytes
        """
        if len(palette_data) >= 1024:
            self.palette = palette_data[:1024]
        else:
            self.palette = palette_data + b'\x00' * (1024 - len(palette_data))
    
    def get_frame_image(self, index: int) -> Optional['Image.Image']:
        """
        Convert a frame to a PIL Image.
        
        Handles both indexed (palette-based) and RGBA frames.
        Applies all necessary transformations (vertical flip, channel swap).
        
        Args:
            index: Absolute frame index
            
        Returns:
            PIL Image in RGBA mode, or None on error
        """
        if not PIL_AVAILABLE:
            return None
        
        frame = self.get_frame(index)
        if not frame or frame.width <= 0 or frame.height <= 0:
            return None
        
        # Safety limit: prevent memory issues with huge frames
        if frame.width > 2048 or frame.height > 2048:
            print(f"[WARN] Frame too large: {frame.width}x{frame.height}, limiting to placeholder")
            return Image.new("RGBA", (100, 100), (80, 80, 80, 255))
        
        try:
            if frame.is_rgba():
                return self._render_rgba(frame, self.version)
            else:
                return self._render_indexed(frame)
        except Exception as e:
            print(f"[ERROR] Frame render failed: {e}")
            return None

    def _render_rgba(self, frame: SPRFrame, version: Optional[Tuple[int, int]] = None) -> Optional['Image.Image']:
        """
        Render RGBA frame to PIL Image.
        
        SPR versions and channel orders:
        - Version 1.x: ABGR format (rare, very old files)
        - Version 2.x: ARGB format (standard)
        
        Both are stored bottom-to-top (vertical flip needed).
        
        GRFEditor code (SprLoader.cs _loadBgra32Image):
            for (int y = 0; y < height; y++) {
                for (int x = 0; x < width; x++) {
                    int index = 4 * ((height - y - 1) * width + x);  // VERTICAL FLIP
                    int index2 = 4 * (width * y + x);
                    realData[index2 + 0] = data[index + 1];  // R from position 1
                    realData[index2 + 1] = data[index + 2];  // G from position 2  
                    realData[index2 + 2] = data[index + 3];  // B from position 3
                    realData[index2 + 3] = data[index + 0];  // A from position 0
                }
            }
        """
        width = frame.width
        height = frame.height
        size = width * height * 4
        
        # Ensure we have enough data, pad with zeros if needed
        data = frame.data
        if len(data) < size:
            data = data + b'\x00' * (size - len(data))
        else:
            data = data[:size]
        
        # Detect channel order by version (legacy 1.x uses ABGR)
        use_abgr = False
        if version and version < (2, 0):
            use_abgr = True  # Legacy format
        
        if NUMPY_AVAILABLE:
            try:
                # Create array from raw data
                arr = np.frombuffer(data, dtype=np.uint8).copy()
                arr = arr.reshape((height, width, 4))
                
                # Vertical flip (image stored bottom-to-top)
                arr = np.flipud(arr)
                
                if use_abgr:
                    # ABGR → RGBA: [A][B][G][R] → [R][G][B][A]
                    rgba = arr[:, :, [3, 2, 1, 0]]
                else:
                    # ARGB → RGBA: [A][R][G][B] → [R][G][B][A]
                    rgba = arr[:, :, [1, 2, 3, 0]]
                
                return Image.fromarray(rgba, 'RGBA')
            except Exception as e:
                print(f"[WARN] NumPy RGBA conversion failed: {e}, using Python fallback")
        
        # Pure Python fallback with vertical flip and channel reorder
        pixels = bytearray(size)
        for y in range(height):
            for x in range(width):
                # Source: bottom-to-top storage, so flip Y
                src_y = height - 1 - y
                src_idx = (src_y * width + x) * 4
                dst_idx = (y * width + x) * 4
                
                if use_abgr:
                    # ABGR → RGBA
                    pixels[dst_idx + 0] = data[src_idx + 3]  # R
                    pixels[dst_idx + 1] = data[src_idx + 2]  # G
                    pixels[dst_idx + 2] = data[src_idx + 1]  # B
                    pixels[dst_idx + 3] = data[src_idx + 0]  # A
                else:
                    # ARGB -> RGBA
                    pixels[dst_idx + 0] = data[src_idx + 1]  # R
                    pixels[dst_idx + 1] = data[src_idx + 2]  # G
                    pixels[dst_idx + 2] = data[src_idx + 3]  # B
                    pixels[dst_idx + 3] = data[src_idx + 0]  # A
        
        return Image.frombytes("RGBA", (width, height), bytes(pixels))

    def _render_indexed(self, frame: SPRFrame) -> Optional['Image.Image']:
        """
        Render indexed (palette-based) frame to PIL Image.
        
        Each pixel is a single byte indexing into the 256-color palette.
        
        CRITICAL palette rules from GRFEditor:
          - Palette is RGBA format (4 bytes per color)
          - All colors default alpha = 255
          - Index 0 alpha = 0 (transparent)
        
        GRFEditor code (Spr.cs _toBgraPalette + rendering):
            // Palette swap from RGBA to BGRA for WPF
            pal[i + 0] = palette[i + 2];  // B <- R
            pal[i + 1] = palette[i + 1];  // G <- G
            pal[i + 2] = palette[i + 0];  // R <- B
            pal[i + 3] = palette[i + 3];  // A <- A
        
        For PIL output, we need RGBA format.
        """
        width = frame.width
        height = frame.height
        size = width * height
        
        # Get palette (RGBA format, 256 colors × 4 bytes)
        pal = self.palette if len(self.palette) >= 1024 else DEFAULT_PALETTE
        
        # Ensure we have enough pixel data
        data = frame.data
        if len(data) < size:
            data = data + b'\x00' * (size - len(data))
        else:
            data = data[:size]
        
        if NUMPY_AVAILABLE:
            try:
                # Build RGBA palette array (256 colors × 4 channels)
                pal_arr = np.frombuffer(pal[:1024], dtype=np.uint8).copy().reshape(256, 4)
                
                # Only force index 0 to be transparent, preserve other alpha values
                # BUT if all alpha values are 0 (buggy palette), set them to 255
                if np.all(pal_arr[:, 3] == 0):
                    # Buggy palette - all alpha is 0, fix it
                    pal_arr[:, 3] = 255
                
                # Always ensure index 0 is transparent
                pal_arr[0, 3] = 0
                
                # Create pixel index array
                idx = np.frombuffer(data, dtype=np.uint8).copy()
                
                # Lookup colors from palette
                rgba = pal_arr[idx]
                
                # Reshape to image dimensions
                rgba = rgba.reshape((height, width, 4))
                
                return Image.fromarray(rgba, 'RGBA')
            except Exception as e:
                print(f"[WARN] NumPy palette lookup failed: {e}, using Python fallback")
        
        # Pure Python fallback
        # Build lookup table: 256 entries of (R, G, B, A)
        lut = []
        for i in range(256):
            o = i * 4
            r = pal[o] if o < len(pal) else 0
            g = pal[o + 1] if o + 1 < len(pal) else 0
            b = pal[o + 2] if o + 2 < len(pal) else 0
            # Alpha: 0 for index 0 (transparent), 255 for all others
            a = 0 if i == 0 else 255
            lut.append((r, g, b, a))
        
        # Convert pixels using lookup table
        pixels = bytearray(size * 4)
        for i, idx in enumerate(data):
            offset = i * 4
            r, g, b, a = lut[idx]
            pixels[offset] = r
            pixels[offset + 1] = g
            pixels[offset + 2] = b
            pixels[offset + 3] = a
        
        return Image.frombytes("RGBA", (width, height), bytes(pixels))


# ==============================================================================
# SPR PARSER
# ==============================================================================

class SPRParser:
    """
    Parser for Ragnarok Online SPR (Sprite) files.
    
    SPR File Format:
        Header:
            - Signature: "SP" (2 bytes)
            - Minor version (1 byte)
            - Major version (1 byte)
            - Indexed frame count (2 bytes, uint16)
            - RGBA frame count (2 bytes, uint16) [version >= 2.0 only]
        
        Frame Data:
            - Indexed frames first, then RGBA frames
            - Each frame has: width (2), height (2), data (varies)
            - Indexed frames: RLE compressed if version >= 2.1
            - RGBA frames: raw pixel data (4 bytes/pixel)
        
        Palette:
            - Last 1024 bytes of file (256 colors × 4 bytes RGBA)
    
    Usage:
        parser = SPRParser()
        sprite = parser.load("sprite.spr")
        # or
        sprite = parser.load_from_bytes(data)
    """
    
    def load(self, filepath: str) -> Optional[SPRSprite]:
        """
        Load SPR file from disk.
        
        Args:
            filepath: Path to SPR file
            
        Returns:
            SPRSprite object or None on error
        """
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            sprite = self.load_from_bytes(data)
            if sprite:
                sprite.filepath = filepath
            return sprite
        except Exception as e:
            print(f"[ERROR] Failed to load SPR file {filepath}: {e}")
            return None
    
    def load_from_bytes(self, data: bytes) -> Optional[SPRSprite]:
        """
        Load SPR from raw bytes.
        
        Args:
            data: Raw SPR file bytes
            
        Returns:
            SPRSprite object or None on error
        """
        if not data or len(data) < 8:
            return None
        
        result = self._parse(data)
        if result:
            return result
        
        # Fallback parser if primary fails
        try:
            from src.parsers.spr_parser_fallback import parse_spr_fallback
            return parse_spr_fallback(data)
        except:
            return None
    
    def _parse(self, data: bytes) -> Optional[SPRSprite]:
        """
        Parse SPR file data.
        
        Based on GRFEditor's SprLoader.cs implementation.
        """
        # Store version for use in rendering
        sprite_version = None
        try:
            # ===============================================================
            # HEADER PARSING
            # ===============================================================
            
            # Validate signature
            if data[0:2] != SPR_SIGNATURE:
                print(f"[ERROR] Invalid SPR signature: {data[0:2]}")
                return None
            
            # Read version (byte 2 = minor, byte 3 = major)
            minor = data[2]
            major = data[3]
            version = (major, minor)
            sprite_version = version  # Store for rendering
            
            # Validate version (support 1.x, 2.x)
            if major < 1 or major > 3:
                print(f"[ERROR] Unsupported SPR version: {version}")
                return None
            
            sprite = SPRSprite(version=version)
            
            # Read frame counts
            indexed_count = struct.unpack('<H', data[4:6])[0]
            
            # Sanity check
            if indexed_count > 5000:
                print(f"[WARN] Unusually high indexed frame count: {indexed_count}")
                return None
            
            rgba_count = 0
            offset = 6
            
            # Version 2.0+ has RGBA frame count
            if version >= (2, 0):
                if len(data) < 8:
                    return None
                rgba_count = struct.unpack('<H', data[6:8])[0]
                if rgba_count > 5000:
                    print(f"[WARN] Unusually high RGBA frame count: {rgba_count}")
                    return None
                offset = 8
            
            # ===============================================================
            # PALETTE LOADING (from end of file - GRFEditor method)
            # ===============================================================
            # GRFEditor reads palette from last 1024 bytes
            # BUT only if there are indexed images
            if indexed_count > 0 and len(data) >= 1024:
                pal_offset = len(data) - 1024
                palette = bytearray(data[pal_offset:pal_offset + 1024])
                
                # Fix alpha channel per GRFEditor:
                # All colors = alpha 255, index 0 = alpha 0
                for i in range(256):
                    palette[i * 4 + 3] = 255
                palette[3] = 0  # Index 0 transparent
                
                sprite.palette = bytes(palette)
            else:
                sprite.palette = DEFAULT_PALETTE
            
            # Calculate where frame data ends (before palette)
            frame_data_end = len(data) - 1024 if indexed_count > 0 else len(data)
            
            # ===============================================================
            # INDEXED FRAMES
            # ===============================================================
            for i in range(indexed_count):
                if offset + 4 > frame_data_end:
                    print(f"[WARN] Ran out of data reading indexed frame {i}")
                    break
                
                frame, offset = self._read_indexed_frame(data, offset, version, frame_data_end)
                if frame:
                    sprite.indexed_frames.append(frame)
            
            # ===============================================================
            # RGBA FRAMES  
            # ===============================================================
            for i in range(rgba_count):
                if offset + 4 > frame_data_end:
                    print(f"[WARN] Ran out of data reading RGBA frame {i}")
                    break
                
                frame, offset = self._read_rgba_frame(data, offset, frame_data_end)
                if frame:
                    sprite.rgba_frames.append(frame)
            
            # Validation
            if sprite.get_total_frames() == 0:
                print("[WARN] SPR parsed but contains 0 frames")
                return None
            
            return sprite
            
        except Exception as e:
            print(f"[ERROR] SPR parse exception: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _read_indexed_frame(self, data: bytes, offset: int, version: Tuple[int, int], max_offset: int):
        """
        Read a single indexed (palette-based) frame.
        
        GRFEditor logic:
          - Version >= 2.1: RLE compressed
          - Version < 2.1: Raw pixel data
        
        Args:
            data: Full SPR file data
            offset: Current read position
            version: SPR version tuple
            max_offset: Maximum valid offset (before palette)
            
        Returns:
            Tuple of (SPRFrame, new_offset)
        """
        # Read dimensions
        width = struct.unpack('<H', data[offset:offset+2])[0]
        height = struct.unpack('<H', data[offset+2:offset+4])[0]
        offset += 4
        
        frame = SPRFrame(width=width, height=height, frame_type="indexed")
        
        # Empty frame check
        if width == 0 or height == 0:
            return frame, offset
        
        # Version 2.1+: RLE compressed
        if version >= (2, 1):
            if offset + 2 > max_offset:
                return frame, offset
            
            # Read compressed size
            compressed_size = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2
            
            # Read compressed data
            if offset + compressed_size > max_offset:
                compressed_size = max_offset - offset
            
            compressed_data = data[offset:offset + compressed_size]
            offset += compressed_size
            
            # Decompress RLE
            frame.data = self._decompress_rle(compressed_data, width * height)
        else:
            # Raw pixel data (1 byte per pixel)
            pixel_count = width * height
            if offset + pixel_count > max_offset:
                pixel_count = max_offset - offset
            
            frame.data = data[offset:offset + pixel_count]
            offset += pixel_count
        
        return frame, offset
    
    def _read_rgba_frame(self, data: bytes, offset: int, max_offset: int):
        """
        Read a single RGBA (32-bit) frame.
        
        RGBA frames are NOT RLE compressed - just raw pixel data.
        Each pixel is 4 bytes in ARGB order (per GRFEditor).
        
        Args:
            data: Full SPR file data  
            offset: Current read position
            max_offset: Maximum valid offset
            
        Returns:
            Tuple of (SPRFrame, new_offset)
        """
        # Read dimensions
        width = struct.unpack('<H', data[offset:offset+2])[0]
        height = struct.unpack('<H', data[offset+2:offset+4])[0]
        offset += 4
        
        frame = SPRFrame(width=width, height=height, frame_type="rgba")
        
        # Empty frame check
        if width == 0 or height == 0:
            return frame, offset
        
        # Raw RGBA data (4 bytes per pixel)
        pixel_count = width * height * 4
        if offset + pixel_count > max_offset:
            pixel_count = max_offset - offset
        
        frame.data = data[offset:offset + pixel_count]
        offset += pixel_count
        
        return frame, offset
    
    def _decompress_rle(self, compressed: bytes, expected_size: int) -> bytes:
        """
        Decompress RLE-encoded indexed pixel data.
        
        GRFEditor RLE format (Rle.cs):
          - If byte == 0: next byte is run length of zeros
          - Otherwise: byte is a pixel value
        
        This matches standard Ragnarok Online RLE for SPR files.
        
        Args:
            compressed: RLE compressed data
            expected_size: Expected decompressed size (width × height)
            
        Returns:
            Decompressed pixel data
        """
        result = bytearray()
        i = 0
        
        while i < len(compressed) and len(result) < expected_size:
            byte = compressed[i]
            i += 1
            
            if byte == 0:
                # Zero run: next byte is count
                if i < len(compressed):
                    run_length = compressed[i]
                    i += 1
                    result.extend([0] * run_length)
                else:
                    # Malformed: zero at end without count
                    result.append(0)
            else:
                # Non-zero pixel value
                result.append(byte)
        
        # Pad to expected size if needed
        if len(result) < expected_size:
            result.extend([0] * (expected_size - len(result)))
        
        return bytes(result[:expected_size])


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def load_palette(filepath: str) -> Optional[bytes]:
    """
    Load a standalone palette file (.pal).
    
    Ragnarok palette files are 1024 bytes (256 colors × 4 bytes RGBA).
    
    Args:
        filepath: Path to .pal file
        
    Returns:
        1024-byte palette data or None on error
    """
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        
        # Ensure 1024 bytes
        if len(data) >= 1024:
            palette = bytearray(data[:1024])
        else:
            palette = bytearray(data + b'\x00' * (1024 - len(data)))
        
        # Fix alpha per GRFEditor convention
        for i in range(256):
            palette[i * 4 + 3] = 255
        palette[3] = 0  # Index 0 transparent
        
        return bytes(palette)
    except Exception as e:
        print(f"[ERROR] Failed to load palette {filepath}: {e}")
        return None
