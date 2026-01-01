# ==============================================================================
# ASSET CATALOGER MODULE
# ==============================================================================
# Organizes and catalogs extracted assets by game, type, and source.
# Provides methods for categorizing assets based on file extension, path,
# and other heuristics.
#
# Asset categories:
#   - Textures:  .bmp, .tga, .dds, .png, .jpg
#   - Models:    .rsm, .zms, .smd, .obj
#   - Sprites:   .spr, .act
#   - Audio:     .wav, .mp3, .ogg
#   - Maps:      .rsw, .gnd, .gat, .him
#   - Data:      .txt, .xml, .lua, .yml
#   - Effects:   .str, .edf, .eff
#   - UI:        Interface elements
#   - Other:     Uncategorized
#
# Usage:
#   cataloger = AssetCataloger(database)
#   category = cataloger.categorize_file("sprite/monster.spr")
#   cataloger.organize_assets(results, output_path)
# ==============================================================================

import os
import shutil
from typing import List, Dict, Optional
from dataclasses import dataclass
from .database import Database, AssetType


# ==============================================================================
# CATEGORY MAPPING
# ==============================================================================
# Default mapping of file extensions to categories
# This can be customized per game if needed

DEFAULT_CATEGORIES = {
    # Textures and images
    'Textures': ['.bmp', '.tga', '.dds', '.png', '.jpg', '.jpeg', '.gif', '.tif', '.tiff'],
    
    # 3D models
    'Models': ['.rsm', '.zms', '.zmd', '.smd', '.obj', '.fbx', '.3ds', '.max', '.blend'],
    
    # 2D sprites and animations
    'Sprites': ['.spr', '.act', '.pal', '.imf'],
    
    # Audio files
    'Audio': ['.wav', '.mp3', '.ogg', '.bgm', '.mid', '.midi', '.flac', '.wma'],
    
    # Map and terrain data
    'Maps': ['.rsw', '.gnd', '.gat', '.him', '.zon', '.ifo', '.til', '.zsc'],
    
    # Configuration and data files
    'Data': ['.txt', '.xml', '.lua', '.yml', '.yaml', '.json', '.ini', '.conf', '.cfg', '.stb', '.stl', '.aip', '.qsd'],
    
    # Visual effects
    'Effects': ['.str', '.edf', '.eff', '.ptl', '.ddf'],
    
    # User interface
    'UI': ['.grf', '.lub'],  # Often UI-related in many games
    
    # Executables and libraries (usually not modified)
    'Binaries': ['.exe', '.dll', '.so', '.dylib'],
}


# ==============================================================================
# CATEGORIZED ASSET DATA CLASS
# ==============================================================================
@dataclass
class CategorizedAsset:
    """
    An asset with its assigned category.
    
    Attributes:
        path (str):      Original relative path of the asset
        full_path (str): Full filesystem path
        category (str):  Assigned category name
        extension (str): File extension
        size (int):      File size in bytes
        hash_md5 (str):  MD5 hash of the file
        status (str):    Comparison status (new/modified/identical)
    """
    path: str
    full_path: str
    category: str
    extension: str
    size: int
    hash_md5: Optional[str] = None
    status: str = 'unknown'


# ==============================================================================
# ASSET CATALOGER CLASS
# ==============================================================================
class AssetCataloger:
    """
    Organizes and catalogs extracted assets.
    
    This class provides methods for:
    - Categorizing assets by file type
    - Organizing assets into structured folders
    - Generating catalogs and reports
    - Finding duplicate assets across servers
    
    Attributes:
        db (Database):           Database instance
        categories (dict):       Mapping of category names to extensions
        extension_map (dict):    Reverse mapping of extension to category
    """
    
    def __init__(self, db: Database = None, custom_categories: Dict[str, List[str]] = None):
        """
        Initialize the cataloger.
        
        Args:
            db: Optional database instance for storing catalog data
            custom_categories: Optional custom category mappings to override defaults
        """
        self.db = db
        
        # Use custom categories if provided, otherwise use defaults
        self.categories = custom_categories if custom_categories else DEFAULT_CATEGORIES.copy()
        
        # Build reverse mapping: extension -> category
        self.extension_map = {}
        for category, extensions in self.categories.items():
            for ext in extensions:
                self.extension_map[ext.lower()] = category
    
    # ==========================================================================
    # CATEGORIZATION
    # ==========================================================================
    
    def get_category(self, file_path: str) -> str:
        """
        Get the category for a file based on its extension.
        
        Args:
            file_path: Path to the file (only extension is used)
            
        Returns:
            Category name, or 'Other' if no match found
            
        Example:
            >>> cataloger = AssetCataloger()
            >>> cataloger.get_category("sprite/monster.spr")
            'Sprites'
        """
        # Get the file extension (lowercase)
        ext = os.path.splitext(file_path)[1].lower()
        
        # Look up in extension map
        return self.extension_map.get(ext, 'Other')
    
    def categorize_file(self, file_path: str, full_path: str = None,
                        status: str = 'unknown', hash_md5: str = None) -> CategorizedAsset:
        """
        Create a categorized asset from a file.
        
        Args:
            file_path: Relative path of the file
            full_path: Full filesystem path (defaults to file_path)
            status: Comparison status
            hash_md5: MD5 hash if already computed
            
        Returns:
            CategorizedAsset object
        """
        full = full_path or file_path
        ext = os.path.splitext(file_path)[1].lower()
        category = self.get_category(file_path)
        
        # Get file size if file exists
        size = os.path.getsize(full) if os.path.isfile(full) else 0
        
        return CategorizedAsset(
            path=file_path,
            full_path=full,
            category=category,
            extension=ext,
            size=size,
            hash_md5=hash_md5,
            status=status
        )
    
    def categorize_files(self, files: List[Dict]) -> Dict[str, List[CategorizedAsset]]:
        """
        Categorize multiple files and group by category.
        
        Args:
            files: List of dicts with 'path', 'full_path', 'status', 'hash_md5' keys
            
        Returns:
            Dictionary mapping category names to lists of CategorizedAsset objects
        """
        # Initialize result dict with all categories
        result = {category: [] for category in self.categories.keys()}
        result['Other'] = []  # Add Other category
        
        # Categorize each file
        for file_info in files:
            asset = self.categorize_file(
                file_path=file_info.get('path', file_info.get('rel_path', '')),
                full_path=file_info.get('full_path', file_info.get('path', '')),
                status=file_info.get('status', 'unknown'),
                hash_md5=file_info.get('hash_md5', file_info.get('hash', None))
            )
            result[asset.category].append(asset)
        
        # Remove empty categories
        return {k: v for k, v in result.items() if v}
    
    # ==========================================================================
    # ORGANIZATION
    # ==========================================================================
    
    def organize_assets(self, assets: List[CategorizedAsset], output_path: str,
                        structure: str = 'by_category',
                        copy_files: bool = True,
                        progress_callback = None) -> Dict[str, int]:
        """
        Organize assets into a structured folder hierarchy.
        
        Args:
            assets: List of CategorizedAsset objects to organize
            output_path: Base output directory
            structure: Organization structure:
                      - 'by_category': output/Textures/, output/Models/, etc.
                      - 'by_status': output/new/, output/modified/, etc.
                      - 'by_extension': output/.bmp/, output/.spr/, etc.
                      - 'preserve': Keep original folder structure
            copy_files: If True, copy files to output. If False, just create catalog.
            progress_callback: Optional callback(current, total, filename)
            
        Returns:
            Dictionary with counts per category/status
        """
        # Ensure output directory exists
        os.makedirs(output_path, exist_ok=True)
        
        counts = {}
        total = len(assets)
        
        for idx, asset in enumerate(assets):
            # Report progress
            if progress_callback:
                progress_callback(idx + 1, total, asset.path)
            
            # Determine destination based on structure
            if structure == 'by_category':
                dest_dir = os.path.join(output_path, asset.category)
                key = asset.category
            elif structure == 'by_status':
                dest_dir = os.path.join(output_path, asset.status)
                key = asset.status
            elif structure == 'by_extension':
                ext_name = asset.extension.lstrip('.') or 'no_extension'
                dest_dir = os.path.join(output_path, ext_name)
                key = ext_name
            else:  # preserve
                # Keep original folder structure
                rel_dir = os.path.dirname(asset.path)
                dest_dir = os.path.join(output_path, rel_dir)
                key = 'preserved'
            
            # Update counts
            counts[key] = counts.get(key, 0) + 1
            
            # Copy file if requested
            if copy_files and os.path.isfile(asset.full_path):
                os.makedirs(dest_dir, exist_ok=True)
                dest_file = os.path.join(dest_dir, os.path.basename(asset.path))
                
                try:
                    shutil.copy2(asset.full_path, dest_file)
                except Exception as e:
                    print(f"[WARN] Failed to copy {asset.path}: {e}")
        
        return counts
    
    def organize_comparison_results(self, results: Dict, output_path: str,
                                    only_custom: bool = True,
                                    structure: str = 'by_category') -> Dict[str, int]:
        """
        Organize comparison results into folders.
        
        This is a convenience method that works directly with the output
        from AssetComparator.compare_directory().
        
        Args:
            results: Dictionary from compare_directory() with 'new', 'modified', etc.
            output_path: Base output directory
            only_custom: If True, only process 'new' and 'modified' assets
            structure: Organization structure
            
        Returns:
            Dictionary with counts per category
        """
        # Collect assets to organize
        assets_to_organize = []
        
        # Process each status
        for status in ['new', 'modified', 'identical', 'unknown']:
            # Skip non-custom if only_custom is True
            if only_custom and status not in ['new', 'modified']:
                continue
            
            for result in results.get(status, []):
                assets_to_organize.append({
                    'path': result.path,
                    'full_path': getattr(result, 'full_path', result.path),
                    'status': status,
                    'hash_md5': result.hash_md5
                })
        
        # Categorize files
        categorized = self.categorize_files(assets_to_organize)
        
        # Flatten to single list
        all_assets = []
        for category_assets in categorized.values():
            all_assets.extend(category_assets)
        
        # Organize
        return self.organize_assets(all_assets, output_path, structure)
    
    # ==========================================================================
    # REPORTING
    # ==========================================================================
    
    def generate_report(self, assets: List[CategorizedAsset]) -> str:
        """
        Generate a text report of categorized assets.
        
        Args:
            assets: List of CategorizedAsset objects
            
        Returns:
            Formatted report string
        """
        # Group by category
        by_category = {}
        for asset in assets:
            if asset.category not in by_category:
                by_category[asset.category] = []
            by_category[asset.category].append(asset)
        
        # Build report
        lines = ["=" * 60, "ASSET CATALOG REPORT", "=" * 60, ""]
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total assets: {len(assets)}")
        
        total_size = sum(a.size for a in assets)
        lines.append(f"Total size: {total_size / (1024*1024):.2f} MB")
        lines.append("")
        
        # By category
        lines.append("BY CATEGORY")
        lines.append("-" * 40)
        for category in sorted(by_category.keys()):
            cat_assets = by_category[category]
            cat_size = sum(a.size for a in cat_assets)
            lines.append(f"  {category}: {len(cat_assets)} files ({cat_size / (1024*1024):.2f} MB)")
        lines.append("")
        
        # By status
        by_status = {}
        for asset in assets:
            if asset.status not in by_status:
                by_status[asset.status] = 0
            by_status[asset.status] += 1
        
        lines.append("BY STATUS")
        lines.append("-" * 40)
        for status in ['new', 'modified', 'identical', 'unknown']:
            if status in by_status:
                lines.append(f"  {status}: {by_status[status]}")
        
        return "\n".join(lines)
    
    def save_catalog(self, assets: List[CategorizedAsset], output_file: str,
                     format: str = 'txt'):
        """
        Save asset catalog to a file.
        
        Args:
            assets: List of CategorizedAsset objects
            output_file: Output file path
            format: Output format ('txt', 'json', 'csv')
        """
        if format == 'txt':
            report = self.generate_report(assets)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
                
        elif format == 'json':
            import json
            data = [{
                'path': a.path,
                'category': a.category,
                'extension': a.extension,
                'size': a.size,
                'hash_md5': a.hash_md5,
                'status': a.status
            } for a in assets]
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
                
        elif format == 'csv':
            import csv
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['path', 'category', 'extension', 'size', 'hash_md5', 'status'])
                for a in assets:
                    writer.writerow([a.path, a.category, a.extension, a.size, a.hash_md5, a.status])
        
        print(f"[INFO] Saved catalog to {output_file}")
    
    # ==========================================================================
    # STATISTICS
    # ==========================================================================
    
    def get_statistics(self, assets: List[CategorizedAsset]) -> dict:
        """
        Get detailed statistics about a set of assets.
        
        Args:
            assets: List of CategorizedAsset objects
            
        Returns:
            Dictionary with statistics
        """
        by_category = {}
        by_status = {}
        by_extension = {}
        
        total_size = 0
        
        for asset in assets:
            # By category
            if asset.category not in by_category:
                by_category[asset.category] = {'count': 0, 'size': 0}
            by_category[asset.category]['count'] += 1
            by_category[asset.category]['size'] += asset.size
            
            # By status
            if asset.status not in by_status:
                by_status[asset.status] = 0
            by_status[asset.status] += 1
            
            # By extension
            if asset.extension not in by_extension:
                by_extension[asset.extension] = 0
            by_extension[asset.extension] += 1
            
            total_size += asset.size
        
        return {
            'total_count': len(assets),
            'total_size': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'by_category': by_category,
            'by_status': by_status,
            'by_extension': by_extension
        }
