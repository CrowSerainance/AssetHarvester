# ==============================================================================
# SPRITE CATALOG MODULE
# ==============================================================================
# Utility for scanning and cataloging RO sprite assets.
#
# This module scans extracted RO data folders to find available sprites,
# headgear, weapons, and other customization options. It builds a catalog
# that the Character Designer uses to populate dropdown menus.
#
# The catalog includes:
#   - Available job sprites (which jobs exist in the data)
#   - Headgear sprites (accessory folder contents)
#   - Weapon sprites (weapon folder contents)
#   - Head sprites (different hairstyles)
#   - Palettes (available dyes and recolors)
#
# Usage:
#   catalog = SpriteCatalog("path/to/extracted/ro")
#   catalog.scan()
#   
#   # Get available jobs
#   jobs = catalog.get_jobs()
#   
#   # Get available headgear
#   headgear = catalog.get_headgear()
# ==============================================================================

import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class HeadgearInfo:
    """
    Information about a headgear sprite.
    
    Attributes:
        id (int):           Headgear ID (from filename)
        name (str):         Display name (from lua/database if available)
        path (str):         Relative path to sprite file
        slot (str):         Which slot: 'top', 'mid', 'low'
        has_male (bool):    Male version exists
        has_female (bool):  Female version exists
    """
    id: int = 0
    name: str = ""
    path: str = ""
    slot: str = "top"
    has_male: bool = False
    has_female: bool = False


@dataclass
class JobInfo:
    """
    Information about a job/class sprite.
    
    Attributes:
        id (int):           Job ID (RO standard)
        name (str):         Display name
        folder (str):       Folder name in sprite directory
        has_male (bool):    Male version exists
        has_female (bool):  Female version exists
        is_mount (bool):    This is a mounted version
        base_job (str):     Base job name (for transcendent)
    """
    id: int = 0
    name: str = ""
    folder: str = ""
    has_male: bool = False
    has_female: bool = False
    is_mount: bool = False
    base_job: str = ""


@dataclass
class PaletteInfo:
    """
    Information about a palette file.
    
    Attributes:
        id (int):           Palette index
        name (str):         Display name (e.g., "Hair Color 1")
        path (str):         Path to .pal file
        target (str):       What this palette is for: 'head', 'body'
        job (str):          Applicable job (if body palette)
    """
    id: int = 0
    name: str = ""
    path: str = ""
    target: str = "head"
    job: str = ""


# ==============================================================================
# SPRITE CATALOG CLASS
# ==============================================================================

class SpriteCatalog:
    """
    Catalog of available RO sprite assets.
    
    Scans an extracted RO data directory and catalogs all available
    sprites, headgear, palettes, etc. for use by the Character Designer.
    
    Attributes:
        resource_path (str):    Base path to extracted RO data
        jobs (dict):            Available job sprites
        headgear (dict):        Available headgear
        heads (dict):           Available head sprites (hairstyles)
        head_palettes (dict):   Available head palettes (hair colors)
        body_palettes (dict):   Available body palettes
        is_scanned (bool):      Whether scan has been performed
    """
    
    def __init__(self, resource_path: str = ""):
        """
        Initialize the catalog.
        
        Args:
            resource_path: Path to extracted RO data folder
        """
        self.resource_path = resource_path
        
        # Catalog storage
        self.jobs: Dict[int, JobInfo] = {}
        self.headgear: Dict[int, HeadgearInfo] = {}
        self.heads: Dict[int, str] = {}  # head_id -> path
        self.head_palettes: Dict[int, PaletteInfo] = {}
        self.body_palettes: Dict[str, Dict[int, PaletteInfo]] = {}  # job -> {id: palette}
        
        self.is_scanned = False
    
    def scan(self, progress_callback=None) -> bool:
        """
        Scan the resource directory for available sprites.
        
        This scans the standard RO directory structure to find:
        - Job sprites in data/sprite/인간족/몸통/
        - Head sprites in data/sprite/인간족/머리통/
        - Headgear in data/sprite/악세사리/
        - Palettes in data/palette/
        
        Args:
            progress_callback: Optional function(current, total, message)
            
        Returns:
            True if scan successful, False on error
        """
        if not self.resource_path:
            print("[ERROR] No resource path set")
            return False
        
        if not os.path.isdir(self.resource_path):
            print(f"[ERROR] Resource path not found: {self.resource_path}")
            return False
        
        # Clear previous data
        self.jobs.clear()
        self.headgear.clear()
        self.heads.clear()
        self.head_palettes.clear()
        self.body_palettes.clear()
        
        try:
            # Scan jobs
            if progress_callback:
                progress_callback(0, 4, "Scanning job sprites...")
            self._scan_jobs()
            
            # Scan heads
            if progress_callback:
                progress_callback(1, 4, "Scanning head sprites...")
            self._scan_heads()
            
            # Scan headgear
            if progress_callback:
                progress_callback(2, 4, "Scanning headgear...")
            self._scan_headgear()
            
            # Scan palettes
            if progress_callback:
                progress_callback(3, 4, "Scanning palettes...")
            self._scan_palettes()
            
            self.is_scanned = True
            
            if progress_callback:
                progress_callback(4, 4, "Scan complete!")
            
            print(f"[INFO] Catalog scan complete:")
            print(f"  Jobs: {len(self.jobs)}")
            print(f"  Heads: {len(self.heads)}")
            print(f"  Headgear: {len(self.headgear)}")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Scan failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _scan_jobs(self):
        """Scan for available job sprites."""
        # Check both Korean and English paths
        body_paths = [
            os.path.join(self.resource_path, "data", "sprite", "인간족", "몸통"),
            os.path.join(self.resource_path, "data", "sprite", "human", "body"),
        ]
        
        for body_path in body_paths:
            if not os.path.isdir(body_path):
                continue
            
            # Check male/female folders
            for gender_folder in os.listdir(body_path):
                gender_path = os.path.join(body_path, gender_folder)
                if not os.path.isdir(gender_path):
                    continue
                
                # Determine gender
                is_male = gender_folder in ["남", "male", "m"]
                is_female = gender_folder in ["여", "female", "f"]
                
                if not (is_male or is_female):
                    continue
                
                # Scan for .spr files
                for filename in os.listdir(gender_path):
                    if not filename.lower().endswith(".spr"):
                        continue
                    
                    # Extract job name from filename
                    # Format is usually "jobname_gender.spr"
                    job_name = filename[:-4]  # Remove .spr
                    
                    # Remove gender suffix if present
                    if job_name.endswith("_남") or job_name.endswith("_여"):
                        job_name = job_name[:-2]
                    if job_name.endswith("_male") or job_name.endswith("_female"):
                        job_name = job_name.rsplit("_", 1)[0]
                    
                    # Create or update job info
                    job_id = hash(job_name) % 10000  # Generate ID from name
                    
                    if job_id not in self.jobs:
                        self.jobs[job_id] = JobInfo(
                            id=job_id,
                            name=job_name,
                            folder=job_name
                        )
                    
                    if is_male:
                        self.jobs[job_id].has_male = True
                    if is_female:
                        self.jobs[job_id].has_female = True
    
    def _scan_heads(self):
        """Scan for available head sprites."""
        head_paths = [
            os.path.join(self.resource_path, "data", "sprite", "인간족", "머리통"),
            os.path.join(self.resource_path, "data", "sprite", "human", "head"),
        ]
        
        for head_path in head_paths:
            if not os.path.isdir(head_path):
                continue
            
            for gender_folder in os.listdir(head_path):
                gender_path = os.path.join(head_path, gender_folder)
                if not os.path.isdir(gender_path):
                    continue
                
                for filename in os.listdir(gender_path):
                    if not filename.lower().endswith(".spr"):
                        continue
                    
                    # Extract head ID from filename
                    # Format is usually "N_gender.spr" where N is the head number
                    match = re.match(r"(\d+)", filename)
                    if match:
                        head_id = int(match.group(1))
                        rel_path = os.path.join(gender_folder, filename[:-4])
                        self.heads[head_id] = rel_path
    
    def _scan_headgear(self):
        """Scan for available headgear sprites."""
        hg_paths = [
            os.path.join(self.resource_path, "data", "sprite", "악세사리"),
            os.path.join(self.resource_path, "data", "sprite", "accessory"),
        ]
        
        for hg_path in hg_paths:
            if not os.path.isdir(hg_path):
                continue
            
            for gender_folder in os.listdir(hg_path):
                gender_path = os.path.join(hg_path, gender_folder)
                if not os.path.isdir(gender_path):
                    continue
                
                is_male = gender_folder in ["남", "male", "m"]
                is_female = gender_folder in ["여", "female", "f"]
                
                for filename in os.listdir(gender_path):
                    if not filename.lower().endswith(".spr"):
                        continue
                    
                    # Extract headgear ID from filename
                    # Format varies, try to extract number
                    match = re.search(r"_?(\d+)", filename)
                    if match:
                        hg_id = int(match.group(1))
                        
                        if hg_id not in self.headgear:
                            self.headgear[hg_id] = HeadgearInfo(
                                id=hg_id,
                                name=f"Headgear {hg_id}",
                                path=os.path.join(gender_folder, filename[:-4])
                            )
                        
                        if is_male:
                            self.headgear[hg_id].has_male = True
                        if is_female:
                            self.headgear[hg_id].has_female = True
    
    def _scan_palettes(self):
        """Scan for available palette files."""
        pal_paths = [
            os.path.join(self.resource_path, "data", "palette"),
        ]
        
        for pal_path in pal_paths:
            if not os.path.isdir(pal_path):
                continue
            
            # Walk through palette directory
            for root, dirs, files in os.walk(pal_path):
                for filename in files:
                    if not filename.lower().endswith(".pal"):
                        continue
                    
                    # Determine if head or body palette
                    rel_path = os.path.relpath(root, pal_path)
                    
                    if "머리" in rel_path or "head" in rel_path.lower():
                        # Head palette
                        match = re.search(r"(\d+)", filename)
                        if match:
                            pal_id = int(match.group(1))
                            self.head_palettes[pal_id] = PaletteInfo(
                                id=pal_id,
                                name=f"Hair Color {pal_id}",
                                path=os.path.join(root, filename),
                                target="head"
                            )
                    
                    elif "몸" in rel_path or "body" in rel_path.lower():
                        # Body palette - try to determine job
                        job_name = os.path.basename(root)
                        match = re.search(r"(\d+)", filename)
                        if match:
                            pal_id = int(match.group(1))
                            
                            if job_name not in self.body_palettes:
                                self.body_palettes[job_name] = {}
                            
                            self.body_palettes[job_name][pal_id] = PaletteInfo(
                                id=pal_id,
                                name=f"Body Palette {pal_id}",
                                path=os.path.join(root, filename),
                                target="body",
                                job=job_name
                            )
    
    # ==========================================================================
    # GETTERS
    # ==========================================================================
    
    def get_jobs(self) -> List[JobInfo]:
        """Get list of available jobs."""
        return sorted(self.jobs.values(), key=lambda j: j.name)
    
    def get_job(self, job_id: int) -> Optional[JobInfo]:
        """Get job info by ID."""
        return self.jobs.get(job_id)
    
    def get_headgear(self) -> List[HeadgearInfo]:
        """Get list of available headgear."""
        return sorted(self.headgear.values(), key=lambda h: h.id)
    
    def get_headgear_by_id(self, hg_id: int) -> Optional[HeadgearInfo]:
        """Get headgear info by ID."""
        return self.headgear.get(hg_id)
    
    def get_head_ids(self) -> List[int]:
        """Get list of available head IDs."""
        return sorted(self.heads.keys())
    
    def get_head_path(self, head_id: int) -> Optional[str]:
        """Get path to head sprite by ID."""
        return self.heads.get(head_id)
    
    def get_head_palettes(self) -> List[PaletteInfo]:
        """Get list of available head palettes."""
        return sorted(self.head_palettes.values(), key=lambda p: p.id)
    
    def get_body_palettes(self, job_name: str) -> List[PaletteInfo]:
        """Get list of body palettes for a job."""
        if job_name in self.body_palettes:
            return sorted(self.body_palettes[job_name].values(), key=lambda p: p.id)
        return []


# ==============================================================================
# STANDALONE TEST
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        catalog = SpriteCatalog(sys.argv[1])
        
        def progress(cur, total, msg):
            print(f"[{cur}/{total}] {msg}")
        
        if catalog.scan(progress):
            print("\n--- Available Jobs ---")
            for job in catalog.get_jobs()[:10]:
                print(f"  {job.name} (M:{job.has_male}, F:{job.has_female})")
            
            print("\n--- Available Heads ---")
            heads = catalog.get_head_ids()[:10]
            print(f"  IDs: {heads}")
            
            print("\n--- Available Headgear ---")
            for hg in catalog.get_headgear()[:10]:
                print(f"  [{hg.id}] {hg.name}")
    else:
        print("Usage: python sprite_catalog.py <path_to_ro_data>")
