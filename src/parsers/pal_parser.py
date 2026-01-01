# ==============================================================================
# PAL (PALETTE) FILE PARSER
# ==============================================================================
# This module reads Ragnarok Online .pal palette files.
#
# PAL FILE FORMAT:
# ----------------
# PAL files are simple 256-color palettes used by indexed sprites.
# Each color is 4 bytes (RGBA), so the file is always 1024 bytes.
#
# PALETTE USAGE:
#   - Default palette: Used when no .pal file is specified
#   - Character palettes: Different hair colors, outfit colors, etc.
#   - Index 0 is always transparent (alpha = 0)
#
# PALETTE NAMING CONVENTION:
# --------------------------
# Ragnarok Online uses a specific naming convention for alternate palettes:
#   - Base sprite: monster.spr (uses embedded or default palette)
#   - Palette 1: monster_1.pal (alternative color scheme)
#   - Palette 2: monster_2.pal (another color scheme)
#   - etc.
#
# For player sprites, the naming is different:
#   - Hair palettes: Ðý¹Ý_Ãʸ£°Ô´Ý_´²ÀÚ_1.pal (hair color 1)
#   - Body palettes: Numbers correspond to job class palettes
#
# USAGE EXAMPLE:
# --------------
#   pal_parser = PALParser()
#   
#   # Load a palette file
#   if pal_parser.load("monster_1.pal"):
#       # Get the palette as a list of RGBA tuples
#       palette = pal_parser.palette
#       
#       # Use with SPR parser
#       spr_parser.set_palette(palette)
#
#   # Or generate a palette programmatically
#   red_palette = PALParser.create_solid_palette((255, 0, 0, 255))
#
# REFERENCES:
# -----------
#   - https://ragnarokresearchlab.github.io/file-formats/pal/
# ==============================================================================

import struct
from dataclasses import dataclass
from typing import List, Tuple, Optional
from pathlib import Path


# ==============================================================================
# CONSTANTS
# ==============================================================================

# Palette file size (always 1024 bytes = 256 colors * 4 bytes each)
PALETTE_SIZE = 1024

# Number of colors in a palette
PALETTE_COLOR_COUNT = 256


# ==============================================================================
# PAL PARSER CLASS
# ==============================================================================

class PALParser:
    """
    Parser for Ragnarok Online .pal palette files.
    
    This class handles reading palette files and provides methods to
    manipulate and convert palettes.
    
    Attributes:
        palette (List[Tuple]): 256 RGBA color tuples
        filename (str):        Path to loaded file
    
    Usage:
        parser = PALParser()
        
        # Load from file
        if parser.load("sprite_1.pal"):
            colors = parser.palette
        
        # Load from bytes
        parser.load_from_bytes(palette_data)
        
        # Create programmatically
        parser = PALParser.from_gradient((0, 0, 0), (255, 255, 255))
    """
    
    def __init__(self):
        """Initialize with a default grayscale palette."""
        self.filename: str = ""
        self._is_loaded: bool = False
        
        # Default grayscale palette
        # Index 0 is transparent, 1-255 are grayscale
        self.palette: List[Tuple[int, int, int, int]] = [
            (i, i, i, 255 if i > 0 else 0) for i in range(256)
        ]
    
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    
    def load(self, file_path: str) -> bool:
        """
        Load a palette from a .pal file.
        
        Args:
            file_path: Path to the .pal file
        
        Returns:
            True if loaded successfully, False otherwise
        
        Example:
            parser = PALParser()
            if parser.load("hair_colors/red.pal"):
                print(f"Loaded palette with {len(parser.palette)} colors")
        """
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            
            self.filename = file_path
            return self.load_from_bytes(data)
        
        except FileNotFoundError:
            print(f"[ERROR] Palette file not found: {file_path}")
            return False
        except Exception as e:
            print(f"[ERROR] Failed to load palette {file_path}: {e}")
            return False
    
    def load_from_bytes(self, data: bytes) -> bool:
        """
        Load a palette from raw bytes.
        
        Args:
            data: Raw bytes of the palette (should be 1024 bytes)
        
        Returns:
            True if parsed successfully, False otherwise
        """
        if len(data) < PALETTE_SIZE:
            print(f"[ERROR] Palette data too small: {len(data)} bytes (expected {PALETTE_SIZE})")
            return False
        
        self.palette = []
        
        for i in range(PALETTE_COLOR_COUNT):
            offset = i * 4
            r = data[offset]
            g = data[offset + 1]
            b = data[offset + 2]
            a = data[offset + 3]
            
            # Index 0 is always transparent in RO
            if i == 0:
                self.palette.append((r, g, b, 0))
            else:
                # Fix common issue where alpha is 0 in file but should be 255
                if a == 0:
                    a = 255
                self.palette.append((r, g, b, a))
        
        self._is_loaded = True
        return True
    
    def save(self, file_path: str) -> bool:
        """
        Save the current palette to a .pal file.
        
        Args:
            file_path: Destination path
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            data = bytearray(PALETTE_SIZE)
            
            for i, (r, g, b, a) in enumerate(self.palette):
                offset = i * 4
                data[offset] = r
                data[offset + 1] = g
                data[offset + 2] = b
                data[offset + 3] = a
            
            with open(file_path, 'wb') as f:
                f.write(data)
            
            return True
        
        except Exception as e:
            print(f"[ERROR] Failed to save palette: {e}")
            return False
    
    def get_color(self, index: int) -> Tuple[int, int, int, int]:
        """
        Get a specific color from the palette.
        
        Args:
            index: Color index (0-255)
        
        Returns:
            RGBA tuple
        """
        if 0 <= index < len(self.palette):
            return self.palette[index]
        return (0, 0, 0, 0)
    
    def set_color(self, index: int, color: Tuple[int, int, int, int]):
        """
        Set a specific color in the palette.
        
        Args:
            index: Color index (0-255)
            color: RGBA tuple
        """
        if 0 <= index < len(self.palette):
            self.palette[index] = color
    
    @property
    def is_loaded(self) -> bool:
        """Whether a file has been successfully loaded."""
        return self._is_loaded
    
    # ==========================================================================
    # STATIC FACTORY METHODS
    # ==========================================================================
    
    @staticmethod
    def create_grayscale() -> 'PALParser':
        """
        Create a grayscale palette.
        
        Returns:
            PALParser with grayscale palette
        
        Example:
            gray_pal = PALParser.create_grayscale()
        """
        parser = PALParser()
        parser.palette = [
            (i, i, i, 255 if i > 0 else 0) for i in range(256)
        ]
        return parser
    
    @staticmethod
    def create_solid_palette(color: Tuple[int, int, int, int]) -> 'PALParser':
        """
        Create a palette with a single solid color (except index 0).
        
        Args:
            color: RGBA tuple for all non-zero indices
        
        Returns:
            PALParser with solid color palette
        
        Example:
            red_pal = PALParser.create_solid_palette((255, 0, 0, 255))
        """
        parser = PALParser()
        parser.palette = [(0, 0, 0, 0)] + [color] * 255
        return parser
    
    @staticmethod
    def create_gradient(start: Tuple[int, int, int], 
                        end: Tuple[int, int, int]) -> 'PALParser':
        """
        Create a gradient palette between two colors.
        
        Args:
            start: Starting RGB color
            end: Ending RGB color
        
        Returns:
            PALParser with gradient palette
        
        Example:
            sunset_pal = PALParser.create_gradient((255, 100, 0), (100, 0, 255))
        """
        parser = PALParser()
        parser.palette = [(0, 0, 0, 0)]  # Index 0 = transparent
        
        for i in range(1, 256):
            t = i / 255.0
            r = int(start[0] + (end[0] - start[0]) * t)
            g = int(start[1] + (end[1] - start[1]) * t)
            b = int(start[2] + (end[2] - start[2]) * t)
            parser.palette.append((r, g, b, 255))
        
        return parser
    
    @staticmethod
    def create_hue_shifted(base_palette: List[Tuple[int, int, int, int]], 
                           hue_shift: float) -> 'PALParser':
        """
        Create a hue-shifted version of an existing palette.
        
        This is commonly used for creating color variants of sprites
        (e.g., different team colors, seasonal variations).
        
        Args:
            base_palette: Original palette (256 RGBA tuples)
            hue_shift: Amount to shift hue (0.0 to 1.0, where 1.0 = full cycle)
        
        Returns:
            PALParser with hue-shifted palette
        
        Example:
            # Shift hue by 180 degrees (opposite colors)
            shifted = PALParser.create_hue_shifted(original.palette, 0.5)
        """
        import colorsys
        
        parser = PALParser()
        parser.palette = []
        
        for r, g, b, a in base_palette:
            if a == 0 or (r == 0 and g == 0 and b == 0):
                # Keep transparent/black as-is
                parser.palette.append((r, g, b, a))
            else:
                # Convert to HSV, shift hue, convert back
                h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
                h = (h + hue_shift) % 1.0
                new_r, new_g, new_b = colorsys.hsv_to_rgb(h, s, v)
                parser.palette.append((
                    int(new_r * 255),
                    int(new_g * 255),
                    int(new_b * 255),
                    a
                ))
        
        return parser
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def to_image(self, cell_size: int = 16) -> Optional['Image.Image']:
        """
        Create a visual representation of the palette.
        
        Creates a 16x16 grid showing all 256 colors.
        
        Args:
            cell_size: Size of each color cell in pixels
        
        Returns:
            PIL.Image showing the palette, or None if PIL unavailable
        """
        try:
            from PIL import Image
        except ImportError:
            print("[WARN] PIL required for palette visualization")
            return None
        
        # Create 16x16 grid
        width = height = 16 * cell_size
        img = Image.new('RGBA', (width, height), (128, 128, 128, 255))
        
        for i, (r, g, b, a) in enumerate(self.palette):
            row = i // 16
            col = i % 16
            
            x1 = col * cell_size
            y1 = row * cell_size
            x2 = x1 + cell_size
            y2 = y1 + cell_size
            
            # Draw cell
            for y in range(y1, y2):
                for x in range(x1, x2):
                    # Checkerboard for transparent pixels
                    if a < 128:
                        checker = ((x // 4) + (y // 4)) % 2
                        c = 192 if checker else 128
                        img.putpixel((x, y), (c, c, c, 255))
                    else:
                        img.putpixel((x, y), (r, g, b, 255))
        
        return img


# ==============================================================================
# STANDALONE USAGE
# ==============================================================================
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pal_parser.py <file.pal> [output.png]")
        print("\nExamples:")
        print("  python pal_parser.py monster.pal")
        print("  python pal_parser.py hair_colors.pal preview.png")
        sys.exit(1)
    
    parser = PALParser()
    if parser.load(sys.argv[1]):
        print(f"Loaded palette: {sys.argv[1]}")
        print(f"Colors: {len(parser.palette)}")
        
        # Show first few colors
        print("\nFirst 10 colors:")
        for i in range(10):
            r, g, b, a = parser.palette[i]
            print(f"  {i:3d}: R={r:3d} G={g:3d} B={b:3d} A={a:3d}")
        
        # Save visualization if output specified
        if len(sys.argv) > 2:
            img = parser.to_image()
            if img:
                img.save(sys.argv[2])
                print(f"\nSaved palette preview to: {sys.argv[2]}")
    else:
        print("Failed to load palette file")
        sys.exit(1)
