# ==============================================================================
# ASSET HARVESTER - MAIN ENTRY POINT
# ==============================================================================
# This is the main entry point for the Asset Harvester application.
# It can be run in either GUI mode (default) or CLI mode.
#
# Usage:
#   python main.py              # Launch GUI
#   python main.py --cli        # Launch CLI
#   python main.py --help       # Show help
#
# When built as exe:
#   AssetHarvester.exe          # Launch GUI
#   AssetHarvester.exe --cli    # Launch CLI
# ==============================================================================

import os
import sys
import traceback

# ==============================================================================
# FROZEN EXE DETECTION
# ==============================================================================
IS_FROZEN = getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

if IS_FROZEN:
    # Running as compiled exe - PyInstaller puts files in _MEIPASS
    BASE_PATH = sys._MEIPASS
    APP_PATH = os.path.dirname(sys.executable)
else:
    # Running as script
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    APP_PATH = BASE_PATH

# ==============================================================================
# BANNER
# ==============================================================================

def print_banner():
    """Print the application banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║     █████╗ ███████╗███████╗███████╗████████╗                  ║
    ║    ██╔══██╗██╔════╝██╔════╝██╔════╝╚══██╔══╝                  ║
    ║    ███████║███████╗███████╗█████╗     ██║                     ║
    ║    ██╔══██║╚════██║╚════██║██╔══╝     ██║                     ║
    ║    ██║  ██║███████║███████║███████╗   ██║                     ║
    ║    ╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝   ╚═╝                     ║
    ║                                                               ║
    ║    ██╗  ██╗ █████╗ ██████╗ ██╗   ██╗███████╗███████╗████████╗ ║
    ║    ██║  ██║██╔══██╗██╔══██╗██║   ██║██╔════╝██╔════╝╚══██╔══╝ ║
    ║    ███████║███████║██████╔╝██║   ██║█████╗  ███████╗   ██║    ║
    ║    ██╔══██║██╔══██║██╔══██╗╚██╗ ██╔╝██╔══╝  ╚════██║   ██║    ║
    ║    ██║  ██║██║  ██║██║  ██║ ╚████╔╝ ███████╗███████║   ██║    ║
    ║    ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚══════╝   ╚═╝    ║
    ║                                                               ║
    ║    Universal Private Server Asset Extraction & Cataloging     ║
    ║                        Version 1.0.0                          ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)


# ==============================================================================
# DEPENDENCY CHECKS
# ==============================================================================

def check_dependencies():
    """
    Check if required dependencies are installed.
    
    Returns:
        Tuple of (all_ok, missing_packages)
    """
    missing = []
    
    # Core dependencies (always required)
    core_deps = ['sqlalchemy']
    
    for dep in core_deps:
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)
    
    return (len(missing) == 0, missing)


# ==============================================================================
# PATH UTILITIES (Simplified for frozen exe compatibility)
# ==============================================================================

def get_user_data_dir():
    """Get the user data directory for storing database and config."""
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        data_dir = os.path.join(base, 'AssetHarvester')
    else:
        base = os.environ.get('XDG_CONFIG_HOME', 
                              os.path.join(os.path.expanduser('~'), '.config'))
        data_dir = os.path.join(base, 'AssetHarvester')
    
    # Create if doesn't exist
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_database_path():
    """Get the path to the SQLite database."""
    return os.path.join(get_user_data_dir(), 'harvester.db')


def get_tools_dir():
    """Get the path to the tools directory."""
    return os.path.join(APP_PATH, 'tools')


# ==============================================================================
# INITIALIZATION
# ==============================================================================

def initialize_app():
    """
    Initialize the application.
    
    Creates necessary directories and sets up paths.
    """
    try:
        data_dir = get_user_data_dir()
        db_path = get_database_path()
        
        print(f"[INFO] Frozen: {IS_FROZEN}")
        print(f"[INFO] Base path: {BASE_PATH}")
        print(f"[INFO] App path: {APP_PATH}")
        print(f"[INFO] User data: {data_dir}")
        print(f"[INFO] Database: {db_path}")
        
        # Create tools directory if running as exe
        tools_dir = get_tools_dir()
        os.makedirs(tools_dir, exist_ok=True)
        os.makedirs(os.path.join(tools_dir, 'scripts'), exist_ok=True)
        
    except Exception as e:
        print(f"[WARNING] Initialization error: {e}")
        traceback.print_exc()


# ==============================================================================
# MODE LAUNCHERS
# ==============================================================================

def run_gui():
    """
    Launch the graphical user interface.
    
    Returns:
        Exit code (0 for success)
    """
    try:
        print("[INFO] Loading PyQt6...")
        from PyQt6.QtWidgets import QApplication
        
        print("[INFO] Loading GUI modules...")
        from src.gui.main_window import MainWindow
        
        print("[INFO] Creating application...")
        app = QApplication(sys.argv)
        app.setApplicationName("Asset Harvester")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("AssetHarvester")
        
        print("[INFO] Creating main window...")
        window = MainWindow()
        window.show()
        
        print("[INFO] Starting event loop...")
        return app.exec()
        
    except ImportError as e:
        print(f"\n[ERROR] Import failed: {e}")
        print(f"\nPyQt6 is required for GUI mode.")
        print(f"Install with: pip install PyQt6")
        print(f"\nOr use CLI mode: AssetHarvester.exe --cli")
        traceback.print_exc()
        input("\nPress Enter to exit...")
        return 1
    except Exception as e:
        print(f"\n[ERROR] GUI failed: {e}")
        traceback.print_exc()
        input("\nPress Enter to exit...")
        return 1


def run_cli():
    """
    Launch the command-line interface.
    
    Returns:
        Exit code (0 for success)
    """
    try:
        from src.cli import main as cli_main
        
        # Remove --cli from sys.argv so CLI parser doesn't see it
        if '--cli' in sys.argv:
            sys.argv.remove('--cli')
        
        cli_main()
        return 0
        
    except Exception as e:
        print(f"[ERROR] CLI failed: {e}")
        traceback.print_exc()
        return 1


# ==============================================================================
# ARGUMENT PARSING
# ==============================================================================

def parse_args():
    """Parse command line arguments manually (avoid argparse issues when frozen)."""
    args = {
        'cli': '--cli' in sys.argv,
        'help': '--help' in sys.argv or '-h' in sys.argv,
        'version': '--version' in sys.argv or '-v' in sys.argv,
        'check': '--check' in sys.argv,
        'paths': '--paths' in sys.argv,
    }
    return args


# ==============================================================================
# MAIN FUNCTION
# ==============================================================================

def main():
    """
    Main entry point for Asset Harvester.
    
    Parses command-line arguments and launches either GUI or CLI mode.
    """
    try:
        args = parse_args()
        
        # Handle --version
        if args['version']:
            print("Asset Harvester v1.0.0")
            print("Universal Private Server Asset Extraction & Cataloging System")
            return 0
        
        # Handle --paths
        if args['paths']:
            print("Asset Harvester Paths:")
            print(f"  Frozen:         {IS_FROZEN}")
            print(f"  Base Path:      {BASE_PATH}")
            print(f"  App Path:       {APP_PATH}")
            print(f"  User Data:      {get_user_data_dir()}")
            print(f"  Database:       {get_database_path()}")
            print(f"  Tools:          {get_tools_dir()}")
            return 0
        
        # Handle --check
        if args['check']:
            print("Checking dependencies...")
            print(f"  Frozen: {IS_FROZEN}")
            print(f"  Python: {sys.version}")
            
            all_ok, missing = check_dependencies()
            
            if all_ok:
                print("[OK] All core dependencies installed")
            else:
                print(f"[MISSING] {', '.join(missing)}")
            
            # Check optional deps
            print("\nOptional dependencies:")
            try:
                from PyQt6.QtCore import PYQT_VERSION_STR
                print(f"  [OK] PyQt6 {PYQT_VERSION_STR}")
            except ImportError:
                print(f"  [--] PyQt6 (not available)")
            
            try:
                import PIL
                print(f"  [OK] Pillow")
            except ImportError:
                print(f"  [--] Pillow (not available)")
            
            return 0 if all_ok else 1
        
        # Handle --help
        if args['help']:
            print_banner()
            print("\nUsage: AssetHarvester.exe [options]")
            print("\nOptions:")
            print("  --cli        Run in command-line mode instead of GUI")
            print("  --help, -h   Show this help message")
            print("  --version    Show version information")
            print("  --check      Check dependencies and exit")
            print("  --paths      Show data paths and exit")
            print("\nCLI Commands (use with --cli):")
            print("  games        Manage supported games")
            print("  servers      Manage registered servers")
            print("  baseline     Build and manage vanilla baselines")
            print("  extract      Extract files from archives")
            print("  compare      Compare client to vanilla baseline")
            print("  catalog      Generate asset catalogs")
            print("  stats        Show overall statistics")
            return 0
        
        # Check core dependencies
        all_ok, missing = check_dependencies()
        if not all_ok:
            print(f"[ERROR] Missing required packages: {', '.join(missing)}")
            input("\nPress Enter to exit...")
            return 1
        
        # Initialize application
        initialize_app()
        
        # Run in appropriate mode
        if args['cli']:
            return run_cli()
        else:
            print_banner()
            print("Starting GUI...")
            return run_gui()
            
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        traceback.print_exc()
        input("\nPress Enter to exit...")
        return 1


# ==============================================================================
# SCRIPT ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
