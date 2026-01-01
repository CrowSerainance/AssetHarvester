# ==============================================================================
# BATCH EXPORT MODULE
# ==============================================================================
# Batch export functionality for RO sprites.
#
# This module provides tools to export large numbers of sprites at once:
#   - Export all headgear as individual PNGs
#   - Export all jobs as sprite sheets
#   - Export animation sequences as GIFs
#   - Generate comparison sheets (vanilla vs custom)
#
# Usage:
#   exporter = BatchExporter(compositor, output_path)
#   exporter.export_all_headgear(progress_callback)
#   exporter.export_job_spritesheet("Knight", progress_callback)
# ==============================================================================

import os
import math
from typing import Optional, List, Callable, Dict, Tuple
from dataclasses import dataclass

# ==============================================================================
# PIL IMPORT
# ==============================================================================
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("[WARN] Pillow not installed. Batch export disabled.")


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class ExportResult:
    """
    Result of an export operation.
    
    Attributes:
        success (bool):     Whether export succeeded
        output_path (str):  Path to exported file(s)
        count (int):        Number of items exported
        errors (list):      List of error messages
        skipped (list):     List of skipped items
    """
    success: bool = False
    output_path: str = ""
    count: int = 0
    errors: List[str] = None
    skipped: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.skipped is None:
            self.skipped = []


@dataclass
class SpritesheetConfig:
    """
    Configuration for sprite sheet generation.
    
    Attributes:
        columns (int):          Number of columns in sheet
        cell_width (int):       Width of each cell in pixels
        cell_height (int):      Height of each cell in pixels
        padding (int):          Padding between cells
        background_color (tuple): RGBA background color
        include_labels (bool):  Add text labels under sprites
        label_font_size (int):  Font size for labels
    """
    columns: int = 8
    cell_width: int = 100
    cell_height: int = 120
    padding: int = 5
    background_color: Tuple[int, int, int, int] = (32, 32, 48, 255)
    include_labels: bool = True
    label_font_size: int = 10


# ==============================================================================
# BATCH EXPORTER CLASS
# ==============================================================================

class BatchExporter:
    """
    Batch export manager for RO sprites.
    
    Handles large-scale export operations like exporting all headgear
    or generating job sprite sheets.
    
    Attributes:
        compositor: SpriteCompositor instance for rendering
        output_path: Base directory for exports
        item_db: ItemDatabase for looking up names
    """
    
    def __init__(self, compositor, output_path: str, item_db=None):
        """
        Initialize batch exporter.
        
        Args:
            compositor: SpriteCompositor for rendering sprites
            output_path: Base directory for exports
            item_db: Optional ItemDatabase for item names
        """
        self.compositor = compositor
        self.output_path = output_path
        self.item_db = item_db
        
        # Ensure output directory exists
        os.makedirs(output_path, exist_ok=True)
    
    def export_all_headgear(self, headgear_ids: List[int], 
                           gender: str = "male",
                           progress_callback: Callable = None) -> ExportResult:
        """
        Export all headgear as individual PNG files.
        
        Args:
            headgear_ids: List of headgear IDs to export
            gender: Gender for sprite rendering
            progress_callback: Optional callback(current, total, message)
            
        Returns:
            ExportResult with details
        """
        if not PIL_AVAILABLE:
            return ExportResult(success=False, errors=["Pillow not installed"])
        
        result = ExportResult()
        
        # Create headgear output folder
        hg_folder = os.path.join(self.output_path, "headgear")
        os.makedirs(hg_folder, exist_ok=True)
        
        total = len(headgear_ids)
        exported = 0
        
        # Store original compositor state
        original_hg = self.compositor.headgear_top
        original_gender = self.compositor.gender
        
        try:
            self.compositor.gender = gender
            
            for i, hg_id in enumerate(headgear_ids):
                if progress_callback:
                    progress_callback(i, total, f"Exporting headgear {hg_id}...")
                
                # Set headgear
                self.compositor.headgear_top = hg_id
                self.compositor.headgear_mid = 0
                self.compositor.headgear_low = 0
                
                # Render
                img = self.compositor.render_frame(0, 0, 0)  # Stand, frame 0, south
                
                if img:
                    # Get name from database if available
                    name = f"headgear_{hg_id}"
                    if self.item_db:
                        db_name = self.item_db.get_headgear_name(hg_id)
                        if db_name and not db_name.startswith("Headgear "):
                            # Sanitize filename
                            name = f"{hg_id}_{self._sanitize_filename(db_name)}"
                    
                    # Save
                    out_path = os.path.join(hg_folder, f"{name}.png")
                    img.save(out_path, "PNG")
                    exported += 1
                else:
                    result.skipped.append(f"Headgear {hg_id}: No sprite found")
            
            result.success = True
            result.output_path = hg_folder
            result.count = exported
            
        except Exception as e:
            result.errors.append(str(e))
        
        finally:
            # Restore original state
            self.compositor.headgear_top = original_hg
            self.compositor.gender = original_gender
        
        if progress_callback:
            progress_callback(total, total, f"Exported {exported} headgear")
        
        return result
    
    def export_headgear_spritesheet(self, headgear_ids: List[int],
                                    gender: str = "male",
                                    config: SpritesheetConfig = None,
                                    progress_callback: Callable = None) -> ExportResult:
        """
        Export headgear as a single sprite sheet image.
        
        Args:
            headgear_ids: List of headgear IDs to include
            gender: Gender for sprite rendering
            config: Sprite sheet configuration
            progress_callback: Optional progress callback
            
        Returns:
            ExportResult with sprite sheet path
        """
        if not PIL_AVAILABLE:
            return ExportResult(success=False, errors=["Pillow not installed"])
        
        if config is None:
            config = SpritesheetConfig()
        
        result = ExportResult()
        
        total = len(headgear_ids)
        rows = math.ceil(total / config.columns)
        
        # Calculate sheet dimensions
        sheet_width = config.columns * (config.cell_width + config.padding) + config.padding
        sheet_height = rows * (config.cell_height + config.padding) + config.padding
        
        # Create sheet image
        sheet = Image.new("RGBA", (sheet_width, sheet_height), config.background_color)
        draw = ImageDraw.Draw(sheet)
        
        # Try to load font for labels
        font = None
        if config.include_labels:
            try:
                font = ImageFont.truetype("arial.ttf", config.label_font_size)
            except:
                try:
                    font = ImageFont.load_default()
                except:
                    font = None
        
        # Store original state
        original_hg = self.compositor.headgear_top
        original_gender = self.compositor.gender
        
        try:
            self.compositor.gender = gender
            exported = 0
            
            for i, hg_id in enumerate(headgear_ids):
                if progress_callback:
                    progress_callback(i, total, f"Rendering headgear {hg_id}...")
                
                # Calculate cell position
                col = i % config.columns
                row = i // config.columns
                
                x = config.padding + col * (config.cell_width + config.padding)
                y = config.padding + row * (config.cell_height + config.padding)
                
                # Set headgear and render
                self.compositor.headgear_top = hg_id
                img = self.compositor.render_frame(0, 0, 0)
                
                if img:
                    # Scale to fit cell (preserve aspect ratio)
                    img.thumbnail((config.cell_width, config.cell_height - 20), 
                                 Image.Resampling.NEAREST)
                    
                    # Center in cell
                    paste_x = x + (config.cell_width - img.width) // 2
                    paste_y = y + (config.cell_height - 20 - img.height) // 2
                    
                    sheet.paste(img, (paste_x, paste_y), img)
                    exported += 1
                
                # Draw label
                if config.include_labels:
                    label = str(hg_id)
                    if self.item_db:
                        name = self.item_db.get_headgear_name(hg_id)
                        if len(name) > 12:
                            name = name[:10] + "..."
                        label = f"{hg_id}\n{name}"
                    
                    label_y = y + config.cell_height - 18
                    draw.text((x + config.cell_width // 2, label_y), 
                             str(hg_id), fill=(200, 200, 200, 255), 
                             anchor="mt", font=font)
            
            # Save sheet
            out_path = os.path.join(self.output_path, f"headgear_sheet_{gender}.png")
            sheet.save(out_path, "PNG")
            
            result.success = True
            result.output_path = out_path
            result.count = exported
            
        except Exception as e:
            result.errors.append(str(e))
        
        finally:
            self.compositor.headgear_top = original_hg
            self.compositor.gender = original_gender
        
        return result
    
    def export_job_spritesheet(self, job_name: str, 
                              gender: str = "male",
                              actions: List[int] = None,
                              config: SpritesheetConfig = None,
                              progress_callback: Callable = None) -> ExportResult:
        """
        Export a job's animations as a sprite sheet.
        
        Creates a grid showing all actions and frames for a job class.
        
        Args:
            job_name: Job name (e.g., "Knight")
            gender: Gender for sprites
            actions: List of action indices to include (default: common actions)
            config: Sprite sheet configuration
            progress_callback: Optional progress callback
            
        Returns:
            ExportResult with sprite sheet path
        """
        if not PIL_AVAILABLE:
            return ExportResult(success=False, errors=["Pillow not installed"])
        
        if config is None:
            config = SpritesheetConfig(columns=8, cell_width=80, cell_height=100)
        
        if actions is None:
            # Default to common actions (one direction each)
            actions = [0, 8, 16, 32, 40, 48, 64, 72]  # Stand, Walk, Sit, Ready, Atk, Hurt, Dead, Cast
        
        result = ExportResult()
        
        # Store original state
        original_job = self.compositor.job
        original_gender = self.compositor.gender
        
        try:
            self.compositor.job = job_name
            self.compositor.gender = gender
            
            # First pass: render all frames to get dimensions
            frames = []
            action_names = {
                0: "Stand", 8: "Walk", 16: "Sit", 32: "Ready",
                40: "Attack", 48: "Hurt", 64: "Dead", 72: "Cast"
            }
            
            for action_idx in actions:
                action_frames = []
                for frame_idx in range(8):  # Max 8 frames per action
                    if progress_callback:
                        progress_callback(len(frames), len(actions) * 8, 
                                        f"Rendering {job_name} action {action_idx}...")
                    
                    img = self.compositor.render_frame(action_idx, frame_idx, 0)
                    if img:
                        action_frames.append(img)
                
                if action_frames:
                    frames.append((action_idx, action_names.get(action_idx, f"Act{action_idx}"), 
                                  action_frames))
            
            if not frames:
                result.errors.append("No frames rendered")
                return result
            
            # Calculate sheet dimensions
            max_frames = max(len(f[2]) for f in frames)
            rows = len(frames)
            
            label_width = 60  # Space for action labels
            sheet_width = label_width + max_frames * (config.cell_width + config.padding) + config.padding
            sheet_height = rows * (config.cell_height + config.padding) + config.padding
            
            # Create sheet
            sheet = Image.new("RGBA", (sheet_width, sheet_height), config.background_color)
            draw = ImageDraw.Draw(sheet)
            
            # Try to load font
            font = None
            try:
                font = ImageFont.truetype("arial.ttf", 10)
            except:
                pass
            
            # Draw frames
            for row, (action_idx, action_name, action_frames) in enumerate(frames):
                y = config.padding + row * (config.cell_height + config.padding)
                
                # Draw action label
                draw.text((5, y + config.cell_height // 2), action_name, 
                         fill=(200, 200, 200, 255), anchor="lm", font=font)
                
                # Draw frames
                for col, frame_img in enumerate(action_frames):
                    x = label_width + config.padding + col * (config.cell_width + config.padding)
                    
                    # Scale to fit cell
                    frame_img.thumbnail((config.cell_width, config.cell_height), 
                                       Image.Resampling.NEAREST)
                    
                    # Center in cell
                    paste_x = x + (config.cell_width - frame_img.width) // 2
                    paste_y = y + (config.cell_height - frame_img.height) // 2
                    
                    sheet.paste(frame_img, (paste_x, paste_y), frame_img)
            
            # Save
            out_path = os.path.join(self.output_path, 
                                   f"{self._sanitize_filename(job_name)}_{gender}_sheet.png")
            sheet.save(out_path, "PNG")
            
            result.success = True
            result.output_path = out_path
            result.count = sum(len(f[2]) for f in frames)
            
        except Exception as e:
            result.errors.append(str(e))
        
        finally:
            self.compositor.job = original_job
            self.compositor.gender = original_gender
        
        return result
    
    def export_all_jobs_preview(self, job_names: List[str],
                                gender: str = "male",
                                progress_callback: Callable = None) -> ExportResult:
        """
        Export preview images for all jobs.
        
        Creates a single image showing all job classes standing.
        
        Args:
            job_names: List of job names to include
            gender: Gender for sprites
            progress_callback: Optional progress callback
            
        Returns:
            ExportResult with output path
        """
        if not PIL_AVAILABLE:
            return ExportResult(success=False, errors=["Pillow not installed"])
        
        result = ExportResult()
        config = SpritesheetConfig(columns=6, cell_width=80, cell_height=100)
        
        total = len(job_names)
        rows = math.ceil(total / config.columns)
        
        sheet_width = config.columns * (config.cell_width + config.padding) + config.padding
        sheet_height = rows * (config.cell_height + config.padding) + config.padding
        
        sheet = Image.new("RGBA", (sheet_width, sheet_height), config.background_color)
        draw = ImageDraw.Draw(sheet)
        
        font = None
        try:
            font = ImageFont.truetype("arial.ttf", 9)
        except:
            pass
        
        original_job = self.compositor.job
        original_gender = self.compositor.gender
        
        try:
            self.compositor.gender = gender
            exported = 0
            
            for i, job_name in enumerate(job_names):
                if progress_callback:
                    progress_callback(i, total, f"Rendering {job_name}...")
                
                col = i % config.columns
                row = i // config.columns
                
                x = config.padding + col * (config.cell_width + config.padding)
                y = config.padding + row * (config.cell_height + config.padding)
                
                self.compositor.job = job_name
                img = self.compositor.render_frame(0, 0, 0)
                
                if img:
                    img.thumbnail((config.cell_width, config.cell_height - 15), 
                                 Image.Resampling.NEAREST)
                    
                    paste_x = x + (config.cell_width - img.width) // 2
                    paste_y = y + (config.cell_height - 15 - img.height) // 2
                    
                    sheet.paste(img, (paste_x, paste_y), img)
                    exported += 1
                
                # Label
                label = job_name[:10] if len(job_name) > 10 else job_name
                draw.text((x + config.cell_width // 2, y + config.cell_height - 5),
                         label, fill=(200, 200, 200, 255), anchor="mb", font=font)
            
            out_path = os.path.join(self.output_path, f"all_jobs_{gender}.png")
            sheet.save(out_path, "PNG")
            
            result.success = True
            result.output_path = out_path
            result.count = exported
            
        except Exception as e:
            result.errors.append(str(e))
        
        finally:
            self.compositor.job = original_job
            self.compositor.gender = original_gender
        
        return result
    
    def export_comparison_sheet(self, 
                                vanilla_compositor,
                                custom_compositor,
                                items: List[Tuple[str, int]],  # (type, id) pairs
                                progress_callback: Callable = None) -> ExportResult:
        """
        Export a side-by-side comparison sheet.
        
        Creates an image showing vanilla vs custom versions of sprites.
        
        Args:
            vanilla_compositor: Compositor with vanilla data
            custom_compositor: Compositor with custom data
            items: List of (item_type, item_id) tuples to compare
            progress_callback: Optional progress callback
            
        Returns:
            ExportResult with comparison sheet path
        """
        if not PIL_AVAILABLE:
            return ExportResult(success=False, errors=["Pillow not installed"])
        
        result = ExportResult()
        
        cell_width = 100
        cell_height = 120
        padding = 5
        
        # 3 columns: Label, Vanilla, Custom
        sheet_width = 3 * cell_width + 4 * padding
        sheet_height = len(items) * (cell_height + padding) + padding + 30  # +30 for header
        
        sheet = Image.new("RGBA", (sheet_width, sheet_height), (32, 32, 48, 255))
        draw = ImageDraw.Draw(sheet)
        
        font = None
        try:
            font = ImageFont.truetype("arial.ttf", 10)
        except:
            pass
        
        # Draw header
        draw.text((padding + cell_width // 2, 10), "Item", fill=(255, 255, 255, 255), 
                 anchor="mt", font=font)
        draw.text((padding + cell_width + padding + cell_width // 2, 10), "Vanilla", 
                 fill=(100, 255, 100, 255), anchor="mt", font=font)
        draw.text((padding + 2 * (cell_width + padding) + cell_width // 2, 10), "Custom", 
                 fill=(255, 200, 100, 255), anchor="mt", font=font)
        
        exported = 0
        
        for i, (item_type, item_id) in enumerate(items):
            if progress_callback:
                progress_callback(i, len(items), f"Comparing {item_type} {item_id}...")
            
            y = 30 + padding + i * (cell_height + padding)
            
            # Draw label
            label = f"{item_type}\n{item_id}"
            if self.item_db and item_type == "headgear":
                name = self.item_db.get_headgear_name(item_id)
                label = f"{item_id}\n{name[:12]}"
            
            draw.text((padding + cell_width // 2, y + cell_height // 2), label,
                     fill=(200, 200, 200, 255), anchor="mm", font=font)
            
            # Render vanilla
            if item_type == "headgear":
                vanilla_compositor.headgear_top = item_id
                custom_compositor.headgear_top = item_id
            
            vanilla_img = vanilla_compositor.render_frame(0, 0, 0)
            custom_img = custom_compositor.render_frame(0, 0, 0)
            
            # Draw vanilla
            if vanilla_img:
                vanilla_img.thumbnail((cell_width - 10, cell_height - 10), 
                                     Image.Resampling.NEAREST)
                x = padding + cell_width + padding
                paste_x = x + (cell_width - vanilla_img.width) // 2
                paste_y = y + (cell_height - vanilla_img.height) // 2
                sheet.paste(vanilla_img, (paste_x, paste_y), vanilla_img)
            else:
                draw.text((padding + cell_width + padding + cell_width // 2, y + cell_height // 2),
                         "N/A", fill=(100, 100, 100, 255), anchor="mm", font=font)
            
            # Draw custom
            if custom_img:
                custom_img.thumbnail((cell_width - 10, cell_height - 10), 
                                    Image.Resampling.NEAREST)
                x = padding + 2 * (cell_width + padding)
                paste_x = x + (cell_width - custom_img.width) // 2
                paste_y = y + (cell_height - custom_img.height) // 2
                sheet.paste(custom_img, (paste_x, paste_y), custom_img)
                exported += 1
            else:
                x = padding + 2 * (cell_width + padding)
                draw.text((x + cell_width // 2, y + cell_height // 2),
                         "N/A", fill=(100, 100, 100, 255), anchor="mm", font=font)
        
        out_path = os.path.join(self.output_path, "comparison_sheet.png")
        sheet.save(out_path, "PNG")
        
        result.success = True
        result.output_path = out_path
        result.count = exported
        
        return result
    
    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize a string for use as a filename.
        
        Args:
            name: Original string
            
        Returns:
            Safe filename string
        """
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        
        # Remove leading/trailing spaces and dots
        name = name.strip(' .')
        
        # Limit length
        if len(name) > 50:
            name = name[:50]
        
        return name


# ==============================================================================
# STANDALONE TEST
# ==============================================================================

if __name__ == "__main__":
    print("Batch Exporter module loaded")
    print("This module requires a SpriteCompositor instance to function.")
