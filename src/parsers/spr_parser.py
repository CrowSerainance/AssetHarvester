# ==============================================================================
# SPR PARSER MODULE - OPTIMIZED VERSION
# ==============================================================================
# Parser for Ragnarok Online SPR (Sprite) files.
# SPR files contain STATIC FRAMES. For animations, use ACT files.
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
SPR_VERSION_1_1 = (1, 1)
SPR_VERSION_2_0 = (2, 0)

# Default grayscale palette
DEFAULT_PALETTE = bytes([val for i in range(256) for val in (i, i, i, 255)])


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class SPRFrame:
    width: int = 0
    height: int = 0
    frame_type: str = "indexed"
    data: bytes = b""
    
    def is_indexed(self) -> bool:
        return self.frame_type == "indexed"
    
    def is_rgba(self) -> bool:
        return self.frame_type == "rgba"


@dataclass  
class SPRSprite:
    version: Tuple[int, int] = (2, 1)
    indexed_frames: List[SPRFrame] = field(default_factory=list)
    rgba_frames: List[SPRFrame] = field(default_factory=list)
    palette: bytes = b""
    filepath: str = ""
    
    def get_total_frames(self) -> int:
        return len(self.indexed_frames) + len(self.rgba_frames)
    
    def get_indexed_count(self) -> int:
        return len(self.indexed_frames)
    
    def get_rgba_count(self) -> int:
        return len(self.rgba_frames)
    
    def get_frame(self, index: int) -> Optional[SPRFrame]:
        ic = len(self.indexed_frames)
        if index < 0:
            return None
        elif index < ic:
            return self.indexed_frames[index]
        elif index < ic + len(self.rgba_frames):
            return self.rgba_frames[index - ic]
        return None
    
    def set_palette(self, palette_data: bytes):
        self.palette = (palette_data[:1024] if len(palette_data) >= 1024 
                       else palette_data + b'\x00' * (1024 - len(palette_data)))
    
    def get_frame_image(self, index: int) -> Optional['Image.Image']:
        """Convert frame to PIL Image."""
        if not PIL_AVAILABLE:
            return None
        
        frame = self.get_frame(index)
        if not frame or frame.width <= 0 or frame.height <= 0:
            return None
        
        # Size limit: max 1000x1000
        if frame.width > 1000 or frame.height > 1000:
            return Image.new("RGBA", (100, 100), (80, 80, 80, 255))
        
        try:
            if frame.is_rgba():
                return self._render_rgba(frame)
            else:
                return self._render_indexed(frame)
        except Exception as e:
            print(f"[ERROR] Render failed: {e}")
            return None

    def _render_rgba(self, frame: SPRFrame) -> Optional['Image.Image']:
        """Render RGBA frame (stored as ABGR in RO)."""
        size = frame.width * frame.height * 4
        data = frame.data[:size] if len(frame.data) >= size else frame.data + b'\x00' * (size - len(frame.data))
        
        if NUMPY_AVAILABLE:
            try:
                # Fast: frombuffer + copy gives writable array
                arr = np.frombuffer(data, dtype=np.uint8).copy()
                arr = arr.reshape((frame.height, frame.width, 4))
                # ABGR -> RGBA: just rearrange columns
                rgba = arr[:, :, [3, 2, 1, 0]]  # R=3, G=2, B=1, A=0
                return Image.fromarray(rgba, 'RGBA')
            except:
                pass  # Fall through to pure Python
        
        # Pure Python: use struct.unpack for speed
        pixels = bytearray(size)
        for i in range(0, size, 4):
            pixels[i] = data[i + 3]      # R
            pixels[i + 1] = data[i + 2]  # G
            pixels[i + 2] = data[i + 1]  # B
            pixels[i + 3] = data[i]      # A
        return Image.frombytes("RGBA", (frame.width, frame.height), bytes(pixels))

    def _render_indexed(self, frame: SPRFrame) -> Optional['Image.Image']:
        """Render indexed frame with palette."""
        size = frame.width * frame.height
        pal = self.palette if len(self.palette) >= 1024 else DEFAULT_PALETTE
        data = frame.data[:size] if len(frame.data) >= size else frame.data + b'\x00' * (size - len(frame.data))
        
        if NUMPY_AVAILABLE:
            try:
                # Create palette array (256 colors, RGBA)
                pal_arr = np.frombuffer(pal[:1024], dtype=np.uint8).copy().reshape(256, 4)
                
                # Create index array
                idx = np.frombuffer(data, dtype=np.uint8).copy()
                
                # Lookup
                rgba = pal_arr[idx]
                
                # Index 0 = transparent
                rgba[idx == 0, 3] = 0
                
                # Reshape and create image
                rgba = rgba.reshape((frame.height, frame.width, 4))
                return Image.fromarray(rgba, 'RGBA')
            except:
                pass  # Fall through to pure Python
        
        # Pure Python: pre-build lookup table
        lut = []
        for i in range(256):
            o = i * 4
            r, g, b, a = pal[o], pal[o+1], pal[o+2], (0 if i == 0 else pal[o+3])
            lut.append(bytes([r, g, b, a]))
        
        # Fast join
        pixels = b''.join(lut[b] for b in data)
        return Image.frombytes("RGBA", (frame.width, frame.height), pixels)


# ==============================================================================
# SPR PARSER
# ==============================================================================

class SPRParser:
    def load(self, filepath: str) -> Optional[SPRSprite]:
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            sprite = self.load_from_bytes(data)
            if sprite:
                sprite.filepath = filepath
            return sprite
        except:
            return None
    
    def load_from_bytes(self, data: bytes) -> Optional[SPRSprite]:
        if not data or len(data) < 8:
            return None
        
        result = self._parse(data)
        if result:
            return result
        
        # Fallback
        try:
            from src.parsers.spr_parser_fallback import parse_spr_fallback
            return parse_spr_fallback(data)
        except:
            return None
    
    def _parse(self, data: bytes) -> Optional[SPRSprite]:
        try:
            if data[0:2] != SPR_SIGNATURE:
                return None
            
            version = (data[3], data[2])
            if version[0] < 1 or version[0] > 3:
                return None
            
            sprite = SPRSprite(version=version)
            
            indexed_count = struct.unpack('<H', data[4:6])[0]
            if indexed_count > 1000:
                return None
            
            rgba_count = 0
            offset = 6
            
            if version >= SPR_VERSION_2_0:
                if len(data) < 8:
                    return None
                rgba_count = struct.unpack('<H', data[6:8])[0]
                if rgba_count > 1000:
                    return None
                offset = 8
            
            # Indexed frames
            for _ in range(indexed_count):
                if offset + 4 > len(data):
                    break
                f, offset = self._read_indexed(data, offset, version)
                if f:
                    sprite.indexed_frames.append(f)
            
            # RGBA frames
            for _ in range(rgba_count):
                if offset + 4 > len(data):
                    break
                f, offset = self._read_rgba(data, offset)
                if f:
                    sprite.rgba_frames.append(f)
            
            # Palette
            if offset + 1024 <= len(data):
                sprite.palette = data[offset:offset + 1024]
            else:
                sprite.palette = DEFAULT_PALETTE
            
            return sprite if sprite.get_total_frames() > 0 else None
        except:
            return None
    
    def _read_indexed(self, data: bytes, offset: int, version):
        w = struct.unpack('<H', data[offset:offset+2])[0]
        h = struct.unpack('<H', data[offset+2:offset+4])[0]
        offset += 4
        
        frame = SPRFrame(width=w, height=h, frame_type="indexed")
        
        if w == 0 or h == 0:
            return frame, offset
        
        if version >= SPR_VERSION_1_1:
            # RLE
            if offset + 2 > len(data):
                return frame, offset
            csize = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2
            cdata = data[offset:offset+csize]
            offset += csize
            frame.data = self._decompress_rle(cdata, w * h)
        else:
            pc = w * h
            frame.data = data[offset:offset+pc]
            offset += pc
        
        return frame, offset
    
    def _read_rgba(self, data: bytes, offset: int):
        w = struct.unpack('<H', data[offset:offset+2])[0]
        h = struct.unpack('<H', data[offset+2:offset+4])[0]
        offset += 4
        
        frame = SPRFrame(width=w, height=h, frame_type="rgba")
        
        if w == 0 or h == 0:
            return frame, offset
        
        pc = w * h * 4
        frame.data = data[offset:offset+pc]
        offset += pc
        
        return frame, offset
    
    def _decompress_rle(self, compressed: bytes, expected: int) -> bytes:
        result = bytearray()
        i = 0
        while i < len(compressed) and len(result) < expected:
            b = compressed[i]
            i += 1
            if b == 0 and i < len(compressed):
                run = compressed[i]
                i += 1
                result.extend([0] * run)
            else:
                result.append(b)
        
        if len(result) < expected:
            result.extend([0] * (expected - len(result)))
        return bytes(result[:expected])


# ==============================================================================
# UTILITIES
# ==============================================================================

def load_palette(filepath: str) -> Optional[bytes]:
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        return data[:1024] if len(data) >= 1024 else data + b'\x00' * (1024 - len(data))
    except:
        return None
