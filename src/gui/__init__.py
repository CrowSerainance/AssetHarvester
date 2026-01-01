# ==============================================================================
# GUI MODULE INIT
# ==============================================================================
# PyQt6-based graphical user interface for Asset Harvester.
#
# Components:
#   - MainWindow: Primary application window with tabbed interface
#   - ServerPanel: Manage registered servers
#   - ExtractPanel: Extract and compare assets
#   - BrowsePanel: Browse extracted assets
#   - SettingsPanel: Application settings
# ==============================================================================

from .main_window import MainWindow

__all__ = ['MainWindow']
