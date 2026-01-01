# ==============================================================================
# ASSET HARVESTER - PATH UTILITIES
# ==============================================================================
# Centralized path handling that works for both development and frozen exe.
#
# When running as a script:
#   - Paths are relative to the project directory
#
# When running as frozen exe (PyInstaller):
#   - Application files are in the exe's directory
#   - User data (database, config) goes in AppData
#
# Usage:
#   from src.core.paths import Paths
#   db_path = Paths.get_database_path()
#   config_path = Paths.get_config_path()
# ==============================================================================

import os
import sys
from typing import Optional


class Paths:
    """
    Centralized path management for Asset Harvester.
    
    Handles the difference between running as a Python script
    and running as a frozen PyInstaller executable.
    
    User data (database, config, logs) is stored in:
    - Windows: %APPDATA%/AssetHarvester/
    - Linux: ~/.config/AssetHarvester/
    - macOS: ~/Library/Application Support/AssetHarvester/
    
    Application files (tools, default scripts) are stored with the exe.
    """
    
    # Application name for folder creation
    APP_NAME = "AssetHarvester"
    
    # Cache for computed paths
    _app_dir: Optional[str] = None
    _user_data_dir: Optional[str] = None
    
    @classmethod
    def is_frozen(cls) -> bool:
        """
        Check if running as a frozen executable.
        
        Returns:
            True if running as PyInstaller exe, False if running as script
        """
        return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
    
    @classmethod
    def get_app_dir(cls) -> str:
        """
        Get the application directory.
        
        For script: The project root directory
        For exe: The directory containing the executable
        
        Returns:
            Absolute path to application directory
        """
        if cls._app_dir is None:
            if cls.is_frozen():
                # Running as exe - use exe's directory
                cls._app_dir = os.path.dirname(sys.executable)
            else:
                # Running as script - use project root
                # This file is in src/core/, so go up 3 levels
                cls._app_dir = os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.abspath(__file__))
                    )
                )
        return cls._app_dir
    
    @classmethod
    def get_user_data_dir(cls) -> str:
        """
        Get the user data directory.
        
        This is where we store user-specific files like:
        - Database (harvester.db)
        - Configuration (config.json)
        - Logs
        
        Returns:
            Absolute path to user data directory
        """
        if cls._user_data_dir is None:
            if sys.platform == 'win32':
                # Windows: %APPDATA%/AssetHarvester/
                base = os.environ.get('APPDATA', os.path.expanduser('~'))
                cls._user_data_dir = os.path.join(base, cls.APP_NAME)
            elif sys.platform == 'darwin':
                # macOS: ~/Library/Application Support/AssetHarvester/
                cls._user_data_dir = os.path.join(
                    os.path.expanduser('~'),
                    'Library', 'Application Support', cls.APP_NAME
                )
            else:
                # Linux: ~/.config/AssetHarvester/
                base = os.environ.get('XDG_CONFIG_HOME', 
                                      os.path.join(os.path.expanduser('~'), '.config'))
                cls._user_data_dir = os.path.join(base, cls.APP_NAME)
            
            # Create directory if it doesn't exist
            os.makedirs(cls._user_data_dir, exist_ok=True)
        
        return cls._user_data_dir
    
    @classmethod
    def get_database_path(cls) -> str:
        """
        Get the path to the SQLite database.
        
        Returns:
            Absolute path to harvester.db
        """
        return os.path.join(cls.get_user_data_dir(), 'harvester.db')
    
    @classmethod
    def get_config_path(cls) -> str:
        """
        Get the path to the configuration file.
        
        Returns:
            Absolute path to config.json
        """
        return os.path.join(cls.get_user_data_dir(), 'config.json')
    
    @classmethod
    def get_logs_dir(cls) -> str:
        """
        Get the path to the logs directory.
        
        Returns:
            Absolute path to logs directory
        """
        logs_dir = os.path.join(cls.get_user_data_dir(), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        return logs_dir
    
    @classmethod
    def get_tools_dir(cls) -> str:
        """
        Get the path to the tools directory.
        
        This is where QuickBMS and scripts are stored.
        
        Returns:
            Absolute path to tools directory
        """
        return os.path.join(cls.get_app_dir(), 'tools')
    
    @classmethod
    def get_quickbms_path(cls) -> str:
        """
        Get the expected path to QuickBMS executable.
        
        Returns:
            Absolute path to quickbms.exe
        """
        return os.path.join(cls.get_tools_dir(), 'quickbms.exe')
    
    @classmethod
    def get_scripts_dir(cls) -> str:
        """
        Get the path to BMS scripts directory.
        
        Returns:
            Absolute path to scripts directory
        """
        scripts_dir = os.path.join(cls.get_tools_dir(), 'scripts')
        os.makedirs(scripts_dir, exist_ok=True)
        return scripts_dir
    
    @classmethod
    def get_resource_path(cls, relative_path: str) -> str:
        """
        Get absolute path to a resource file.
        
        Works for both development and frozen exe.
        For PyInstaller, looks in _MEIPASS for bundled resources.
        
        Args:
            relative_path: Path relative to app directory
            
        Returns:
            Absolute path to the resource
        """
        if cls.is_frozen():
            # PyInstaller stores bundled files in _MEIPASS
            base = sys._MEIPASS
        else:
            base = cls.get_app_dir()
        
        return os.path.join(base, relative_path)
    
    @classmethod
    def ensure_directories(cls):
        """
        Ensure all required directories exist.
        
        Call this at application startup.
        """
        # User data directories
        os.makedirs(cls.get_user_data_dir(), exist_ok=True)
        os.makedirs(cls.get_logs_dir(), exist_ok=True)
        
        # App directories (only if not frozen - exe includes these)
        if not cls.is_frozen():
            os.makedirs(cls.get_tools_dir(), exist_ok=True)
            os.makedirs(cls.get_scripts_dir(), exist_ok=True)
    
    @classmethod
    def get_default_output_dir(cls) -> str:
        """
        Get a sensible default output directory.
        
        Returns:
            Path to Documents/AssetHarvester or similar
        """
        if sys.platform == 'win32':
            # Windows: Documents/AssetHarvester
            docs = os.path.join(os.path.expanduser('~'), 'Documents')
        else:
            # Linux/Mac: ~/AssetHarvester
            docs = os.path.expanduser('~')
        
        output_dir = os.path.join(docs, cls.APP_NAME)
        return output_dir
