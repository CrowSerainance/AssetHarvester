# ==============================================================================
# ASSET HARVESTER - CONFIGURATION MODULE
# ==============================================================================
# Centralized configuration management for the application.
#
# This module handles:
#   - Loading/saving configuration from JSON file
#   - Default values for all settings
#   - Path validation and normalization
#   - Environment-specific overrides
#
# Configuration is stored in: data/config.json
#
# Usage:
#   from src.core.config import Config
#   config = Config()
#   config.load()
#   print(config.asset_library_path)
#   config.quickbms_path = "C:/tools/quickbms.exe"
#   config.save()
# ==============================================================================

import os
import json
from typing import Optional, Dict, Any


# ==============================================================================
# DEFAULT CONFIGURATION VALUES
# ==============================================================================
# These are used when no config file exists or when values are missing.

DEFAULT_CONFIG = {
    # -------------------------------------------------------------------------
    # PATHS
    # -------------------------------------------------------------------------
    # Where to store extracted assets by default
    "asset_library_path": "",
    
    # Path to QuickBMS executable
    "quickbms_path": "tools/quickbms.exe",
    
    # Path to BMS scripts folder
    "bms_scripts_path": "tools/scripts",
    
    # Default output folder for extractions
    "default_output_path": "",
    
    # -------------------------------------------------------------------------
    # DATABASE
    # -------------------------------------------------------------------------
    # Path to SQLite database
    "database_path": "data/harvester.db",
    
    # -------------------------------------------------------------------------
    # EXTRACTION SETTINGS
    # -------------------------------------------------------------------------
    # Hash algorithm for comparison (md5, sha256, both)
    "hash_algorithm": "md5",
    
    # Skip files larger than this (in MB, 0 = no limit)
    "max_file_size_mb": 0,
    
    # Number of parallel extraction threads
    "extraction_threads": 4,
    
    # Overwrite existing files during extraction
    "overwrite_existing": False,
    
    # -------------------------------------------------------------------------
    # CATALOGING SETTINGS
    # -------------------------------------------------------------------------
    # Generate thumbnails for images
    "generate_thumbnails": True,
    
    # Thumbnail size (pixels)
    "thumbnail_size": 128,
    
    # Default catalog export format (txt, json, csv)
    "catalog_format": "json",
    
    # -------------------------------------------------------------------------
    # GUI SETTINGS
    # -------------------------------------------------------------------------
    # Remember window size/position
    "remember_window_state": True,
    
    # Window width
    "window_width": 1400,
    
    # Window height
    "window_height": 900,
    
    # Theme (dark, light)
    "theme": "dark",
    
    # -------------------------------------------------------------------------
    # ADVANCED
    # -------------------------------------------------------------------------
    # Enable debug logging
    "debug_mode": False,
    
    # Show hidden/system files in browser
    "show_hidden_files": False,
}


# ==============================================================================
# CONFIGURATION CLASS
# ==============================================================================
class Config:
    """
    Configuration manager for Asset Harvester.
    
    Handles loading, saving, and accessing application settings.
    Settings are stored in a JSON file and can be accessed as
    properties on this object.
    
    Attributes:
        config_path: Path to the configuration file
        data: Dictionary containing all settings
    
    Example:
        >>> config = Config()
        >>> config.load()
        >>> print(config.asset_library_path)
        >>> config.quickbms_path = "/path/to/quickbms"
        >>> config.save()
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to config file. If None, uses default location.
        """
        # Determine config file path
        if config_path:
            self.config_path = config_path
        else:
            # Default: data/config.json relative to project root
            project_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            self.config_path = os.path.join(project_root, 'data', 'config.json')
        
        # Initialize with defaults
        self.data: Dict[str, Any] = DEFAULT_CONFIG.copy()
        
        # Track if config has been modified
        self._modified = False
    
    # -------------------------------------------------------------------------
    # LOADING AND SAVING
    # -------------------------------------------------------------------------
    
    def load(self) -> bool:
        """
        Load configuration from file.
        
        If the file doesn't exist, defaults are used.
        Missing keys are filled with defaults.
        
        Returns:
            True if file was loaded, False if using defaults
        """
        if not os.path.isfile(self.config_path):
            print(f"[INFO] Config file not found, using defaults")
            return False
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
            
            # Merge with defaults (so new settings get default values)
            for key, value in loaded.items():
                if key in self.data:
                    self.data[key] = value
            
            print(f"[INFO] Loaded config from {self.config_path}")
            self._modified = False
            return True
            
        except json.JSONDecodeError as e:
            print(f"[ERROR] Invalid config file: {e}")
            return False
        except Exception as e:
            print(f"[ERROR] Failed to load config: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save configuration to file.
        
        Creates the directory if it doesn't exist.
        
        Returns:
            True if saved successfully
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            # Write config with pretty formatting
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, sort_keys=True)
            
            print(f"[INFO] Saved config to {self.config_path}")
            self._modified = False
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to save config: {e}")
            return False
    
    def reset_to_defaults(self):
        """Reset all settings to their default values."""
        self.data = DEFAULT_CONFIG.copy()
        self._modified = True
    
    # -------------------------------------------------------------------------
    # PROPERTY ACCESS
    # -------------------------------------------------------------------------
    # These properties provide type-safe access to common settings
    
    @property
    def asset_library_path(self) -> str:
        """Get the asset library path."""
        return self.data.get('asset_library_path', '')
    
    @asset_library_path.setter
    def asset_library_path(self, value: str):
        """Set the asset library path."""
        self.data['asset_library_path'] = value
        self._modified = True
    
    @property
    def quickbms_path(self) -> str:
        """Get the QuickBMS executable path."""
        return self.data.get('quickbms_path', 'tools/quickbms.exe')
    
    @quickbms_path.setter
    def quickbms_path(self, value: str):
        """Set the QuickBMS executable path."""
        self.data['quickbms_path'] = value
        self._modified = True
    
    @property
    def database_path(self) -> str:
        """Get the database path."""
        return self.data.get('database_path', 'data/harvester.db')
    
    @database_path.setter
    def database_path(self, value: str):
        """Set the database path."""
        self.data['database_path'] = value
        self._modified = True
    
    @property
    def hash_algorithm(self) -> str:
        """Get the hash algorithm (md5, sha256, both)."""
        return self.data.get('hash_algorithm', 'md5')
    
    @hash_algorithm.setter
    def hash_algorithm(self, value: str):
        """Set the hash algorithm."""
        if value not in ('md5', 'sha256', 'both'):
            raise ValueError("hash_algorithm must be 'md5', 'sha256', or 'both'")
        self.data['hash_algorithm'] = value
        self._modified = True
    
    @property
    def debug_mode(self) -> bool:
        """Check if debug mode is enabled."""
        return self.data.get('debug_mode', False)
    
    @debug_mode.setter
    def debug_mode(self, value: bool):
        """Set debug mode."""
        self.data['debug_mode'] = bool(value)
        self._modified = True
    
    @property
    def extraction_threads(self) -> int:
        """Get the number of extraction threads."""
        return self.data.get('extraction_threads', 4)
    
    @extraction_threads.setter
    def extraction_threads(self, value: int):
        """Set the number of extraction threads."""
        self.data['extraction_threads'] = max(1, min(16, int(value)))
        self._modified = True
    
    @property
    def generate_thumbnails(self) -> bool:
        """Check if thumbnail generation is enabled."""
        return self.data.get('generate_thumbnails', True)
    
    @generate_thumbnails.setter
    def generate_thumbnails(self, value: bool):
        """Set thumbnail generation."""
        self.data['generate_thumbnails'] = bool(value)
        self._modified = True
    
    @property
    def thumbnail_size(self) -> int:
        """Get thumbnail size in pixels."""
        return self.data.get('thumbnail_size', 128)
    
    @thumbnail_size.setter
    def thumbnail_size(self, value: int):
        """Set thumbnail size."""
        self.data['thumbnail_size'] = max(32, min(512, int(value)))
        self._modified = True
    
    # -------------------------------------------------------------------------
    # GENERIC ACCESS
    # -------------------------------------------------------------------------
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            The configuration value
        """
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any):
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Value to set
        """
        self.data[key] = value
        self._modified = True
    
    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access: config['key']"""
        return self.data[key]
    
    def __setitem__(self, key: str, value: Any):
        """Allow dictionary-style setting: config['key'] = value"""
        self.data[key] = value
        self._modified = True
    
    # -------------------------------------------------------------------------
    # PATH RESOLUTION
    # -------------------------------------------------------------------------
    
    def resolve_path(self, path: str) -> str:
        """
        Resolve a path relative to the project root.
        
        If the path is absolute, returns it as-is.
        If relative, resolves it relative to the project root.
        
        Args:
            path: Path to resolve
            
        Returns:
            Absolute path
        """
        if os.path.isabs(path):
            return path
        
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        return os.path.join(project_root, path)
    
    def get_quickbms_executable(self) -> Optional[str]:
        """
        Get the full path to QuickBMS executable.
        
        Checks common locations if configured path doesn't exist.
        
        Returns:
            Path to QuickBMS if found, None otherwise
        """
        # Check configured path
        configured = self.resolve_path(self.quickbms_path)
        if os.path.isfile(configured):
            return configured
        
        # Check common locations
        common_paths = [
            'tools/quickbms.exe',
            'tools/quickbms/quickbms.exe',
            'C:/quickbms/quickbms.exe',
            'C:/Program Files/quickbms/quickbms.exe',
        ]
        
        for path in common_paths:
            full_path = self.resolve_path(path)
            if os.path.isfile(full_path):
                return full_path
        
        return None


# ==============================================================================
# GLOBAL CONFIG INSTANCE
# ==============================================================================
# This provides a singleton-like access to configuration

_global_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global configuration instance.
    
    Creates and loads config on first call.
    
    Returns:
        The global Config instance
    """
    global _global_config
    
    if _global_config is None:
        _global_config = Config()
        _global_config.load()
    
    return _global_config
