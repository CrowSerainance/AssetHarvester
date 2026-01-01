# ==============================================================================
# ASSET HARVESTER - BUILD SCRIPT
# ==============================================================================
# Automated build script for creating the Windows executable.
#
# Usage:
#   python build.py           # Build with console
#   python build.py --noconsole  # Build GUI-only (no console window)
#   python build.py --onefile    # Build single exe (larger, slower startup)
#   python build.py --clean      # Clean build directories first
#
# Requirements:
#   pip install pyinstaller
#
# Output:
#   dist/AssetHarvester/AssetHarvester.exe  (directory mode)
#   dist/AssetHarvester.exe                  (onefile mode)
# ==============================================================================

import os
import sys
import shutil
import subprocess
import argparse
from datetime import datetime


# ==============================================================================
# CONFIGURATION
# ==============================================================================

APP_NAME = "AssetHarvester"
VERSION = "1.0.0"
AUTHOR = "Crow"
DESCRIPTION = "Universal Private Server Asset Extraction & Cataloging System"

# Directories to clean before build
CLEAN_DIRS = ['build', 'dist', '__pycache__']

# Files to include in distribution
EXTRA_FILES = [
    ('README.md', '.'),
    ('requirements.txt', '.'),
    ('docs', 'docs'),
    ('tools/README.md', 'tools'),
    ('tools/scripts/README.md', 'tools/scripts'),
]


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_success(text: str):
    """Print a success message."""
    print(f"[OK] {text}")


def print_error(text: str):
    """Print an error message."""
    print(f"[ERROR] {text}")


def print_info(text: str):
    """Print an info message."""
    print(f"[INFO] {text}")


def clean_build():
    """Remove build artifacts."""
    print_header("Cleaning Build Directories")
    
    for dir_name in CLEAN_DIRS:
        if os.path.exists(dir_name):
            print_info(f"Removing {dir_name}/")
            shutil.rmtree(dir_name, ignore_errors=True)
    
    # Also clean __pycache__ in subdirectories
    for root, dirs, files in os.walk('.'):
        for d in dirs:
            if d == '__pycache__':
                path = os.path.join(root, d)
                print_info(f"Removing {path}")
                shutil.rmtree(path, ignore_errors=True)
    
    print_success("Clean complete")


def check_dependencies():
    """Check if required tools are installed."""
    print_header("Checking Dependencies")
    
    # Check PyInstaller
    try:
        import PyInstaller
        print_success(f"PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print_error("PyInstaller not found!")
        print_info("Install with: pip install pyinstaller")
        return False
    
    # Check SQLAlchemy
    try:
        import sqlalchemy
        print_success(f"SQLAlchemy {sqlalchemy.__version__} found")
    except ImportError:
        print_error("SQLAlchemy not found!")
        print_info("Install with: pip install sqlalchemy")
        return False
    
    # Check PyQt6 (optional but recommended)
    try:
        from PyQt6.QtCore import PYQT_VERSION_STR
        print_success(f"PyQt6 {PYQT_VERSION_STR} found")
    except ImportError:
        print_info("PyQt6 not found - GUI will not be available")
    
    return True


def create_version_info():
    """Create Windows version info file."""
    print_info("Creating version info...")
    
    # Parse version
    major, minor, patch = VERSION.split('.')
    
    version_info = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', '{AUTHOR}'),
            StringStruct('FileDescription', '{DESCRIPTION}'),
            StringStruct('FileVersion', '{VERSION}'),
            StringStruct('InternalName', '{APP_NAME}'),
            StringStruct('OriginalFilename', '{APP_NAME}.exe'),
            StringStruct('ProductName', '{APP_NAME}'),
            StringStruct('ProductVersion', '{VERSION}'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
'''
    
    with open('version_info.txt', 'w') as f:
        f.write(version_info)
    
    print_success("Version info created")


def run_pyinstaller(onefile: bool = False, noconsole: bool = False):
    """Run PyInstaller to create the executable."""
    print_header("Building Executable")
    
    # Base command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name', APP_NAME,
        '--clean',
        '--noconfirm',
    ]
    
    # One file or directory mode
    if onefile:
        cmd.append('--onefile')
        print_info("Building single executable (--onefile)")
    else:
        cmd.append('--onedir')
        print_info("Building directory distribution (--onedir)")
    
    # Console or windowed
    if noconsole:
        cmd.append('--noconsole')
        print_info("GUI mode - no console window")
    else:
        cmd.append('--console')
        print_info("Console mode - window will show")
    
    # Hidden imports
    hidden_imports = [
        'sqlalchemy.dialects.sqlite',
        'src.core.database',
        'src.core.hasher',
        'src.core.comparator',
        'src.core.cataloger',
        'src.core.config',
        'src.core.paths',
        'src.extractors.grf_extractor',
        'src.extractors.vfs_extractor',
        'src.extractors.generic_extractor',
    ]
    
    for imp in hidden_imports:
        cmd.extend(['--hidden-import', imp])
    
    # Data files
    for src, dst in EXTRA_FILES:
        if os.path.exists(src):
            cmd.extend(['--add-data', f'{src};{dst}'])
    
    # Icon (if exists)
    if os.path.exists('assets/icon.ico'):
        cmd.extend(['--icon', 'assets/icon.ico'])
    
    # Version info (Windows)
    if os.path.exists('version_info.txt') and sys.platform == 'win32':
        cmd.extend(['--version-file', 'version_info.txt'])
    
    # Excludes to reduce size
    excludes = ['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'IPython']
    for exc in excludes:
        cmd.extend(['--exclude-module', exc])
    
    # Main script
    cmd.append('main.py')
    
    print_info(f"Running: {' '.join(cmd[:10])}...")
    
    # Run PyInstaller
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print_error("PyInstaller failed!")
        return False
    
    print_success("Build complete!")
    return True


def post_build(onefile: bool = False):
    """Post-build tasks - copy additional files."""
    print_header("Post-Build Tasks")
    
    if onefile:
        dist_dir = 'dist'
        exe_path = os.path.join(dist_dir, f'{APP_NAME}.exe')
    else:
        dist_dir = os.path.join('dist', APP_NAME)
        exe_path = os.path.join(dist_dir, f'{APP_NAME}.exe')
    
    if not os.path.exists(exe_path):
        print_error(f"Executable not found: {exe_path}")
        return False
    
    # Create tools directory in dist
    tools_dir = os.path.join(dist_dir, 'tools')
    scripts_dir = os.path.join(tools_dir, 'scripts')
    os.makedirs(scripts_dir, exist_ok=True)
    
    # Copy placeholder files
    print_info("Creating directory structure...")
    
    # Write a note about QuickBMS
    quickbms_note = """# QuickBMS Required
    
Download QuickBMS from: https://aluigi.altervista.org/quickbms.htm
Place quickbms.exe in this directory.
"""
    with open(os.path.join(tools_dir, 'PLACE_QUICKBMS_HERE.txt'), 'w') as f:
        f.write(quickbms_note)
    
    print_success(f"Distribution created in: {dist_dir}")
    
    # Print size info
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print_info(f"Executable size: {size_mb:.1f} MB")
    
    return True


def create_zip_package():
    """Create a ZIP package for distribution."""
    print_header("Creating Distribution Package")
    
    dist_dir = os.path.join('dist', APP_NAME)
    if not os.path.exists(dist_dir):
        print_error("Distribution directory not found. Run build first.")
        return False
    
    # Create zip filename with date
    date_str = datetime.now().strftime('%Y%m%d')
    zip_name = f'{APP_NAME}-{VERSION}-{date_str}'
    
    print_info(f"Creating {zip_name}.zip...")
    
    shutil.make_archive(
        os.path.join('dist', zip_name),
        'zip',
        'dist',
        APP_NAME
    )
    
    zip_path = os.path.join('dist', f'{zip_name}.zip')
    if os.path.exists(zip_path):
        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        print_success(f"Package created: {zip_path} ({size_mb:.1f} MB)")
        return True
    
    return False


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    """Main build function."""
    parser = argparse.ArgumentParser(description=f"Build {APP_NAME} executable")
    parser.add_argument('--onefile', action='store_true', 
                        help='Create single executable (slower startup)')
    parser.add_argument('--noconsole', action='store_true',
                        help='Hide console window (GUI only)')
    parser.add_argument('--clean', action='store_true',
                        help='Clean build directories first')
    parser.add_argument('--zip', action='store_true',
                        help='Create ZIP package after build')
    parser.add_argument('--skip-build', action='store_true',
                        help='Skip build, only run post-build tasks')
    
    args = parser.parse_args()
    
    print_header(f"Building {APP_NAME} v{VERSION}")
    
    # Clean if requested
    if args.clean:
        clean_build()
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Create version info
    create_version_info()
    
    # Run build
    if not args.skip_build:
        if not run_pyinstaller(args.onefile, args.noconsole):
            return 1
    
    # Post-build
    if not post_build(args.onefile):
        return 1
    
    # Create ZIP package
    if args.zip and not args.onefile:
        create_zip_package()
    
    print_header("Build Complete!")
    
    if args.onefile:
        print(f"Executable: dist/{APP_NAME}.exe")
    else:
        print(f"Distribution: dist/{APP_NAME}/")
        print(f"Run: dist/{APP_NAME}/{APP_NAME}.exe")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
