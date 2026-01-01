# ==============================================================================
# ASSET HARVESTER - COMMAND LINE INTERFACE
# ==============================================================================
# CLI prototype for testing extraction and comparison logic before GUI.
#
# This provides a command-line interface with the following commands:
#   - games: List supported games
#   - servers: Manage servers
#   - baseline: Build vanilla baseline
#   - extract: Extract files from archives
#   - compare: Compare client against vanilla
#   - catalog: Generate asset catalogs
#
# Usage:
#   python cli.py games list
#   python cli.py baseline build --game "Ragnarok Online" --path "E:\RO_Vanilla"
#   python cli.py extract --archive "data.grf" --output "extracted/"
#   python cli.py compare --client "E:\Server_Client" --output "custom/"
#
# ==============================================================================

import os
import sys
import argparse
from typing import Optional

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==============================================================================
# COLOR HELPERS FOR TERMINAL OUTPUT
# ==============================================================================
class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
    @classmethod
    def disable(cls):
        """Disable colors (for non-supporting terminals)."""
        cls.HEADER = ''
        cls.BLUE = ''
        cls.CYAN = ''
        cls.GREEN = ''
        cls.YELLOW = ''
        cls.RED = ''
        cls.BOLD = ''
        cls.UNDERLINE = ''
        cls.END = ''


def print_header(text: str):
    """Print a header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.END}\n")


def print_success(text: str):
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text: str):
    """Print an error message."""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_info(text: str):
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def progress_callback(current: int, total: int, filename: str):
    """Progress callback for long operations."""
    percent = (current / total) * 100 if total > 0 else 0
    bar_length = 30
    filled = int(bar_length * current / total) if total > 0 else 0
    bar = '█' * filled + '░' * (bar_length - filled)
    
    # Truncate filename if too long
    max_name_len = 40
    if len(filename) > max_name_len:
        filename = '...' + filename[-(max_name_len-3):]
    
    print(f"\r[{bar}] {percent:5.1f}% | {current}/{total} | {filename}", end='', flush=True)
    
    if current >= total:
        print()  # New line when complete


# ==============================================================================
# DATABASE INITIALIZATION
# ==============================================================================
def get_database():
    """Get or create the database instance."""
    from src.core.database import Database
    
    # Get database path - works for both frozen and script
    if getattr(sys, 'frozen', False):
        # Running as exe
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        data_dir = os.path.join(base, 'AssetHarvester')
    else:
        # Running as script
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data'
        )
    
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, 'harvester.db')
    
    return Database(db_path)


# ==============================================================================
# GAMES COMMANDS
# ==============================================================================
def cmd_games_list(args):
    """List all supported games."""
    print_header("Supported Games")
    
    db = get_database()
    games = db.get_all_games()
    
    if not games:
        print_warning("No games registered")
        return
    
    print(f"{'ID':<4} {'Game Name':<25} {'Format':<10} {'Extractor':<20}")
    print("-" * 65)
    
    for game in games:
        print(f"{game.id:<4} {game.name:<25} {game.archive_format:<10} {game.extractor_module:<20}")
    
    print(f"\nTotal: {len(games)} games")


def cmd_games_add(args):
    """Add a new game."""
    db = get_database()
    
    game = db.add_game(
        name=args.name,
        archive_format=args.format,
        extractor_module=args.extractor,
        description=args.description
    )
    
    print_success(f"Added game: {game.name} (ID: {game.id})")


# ==============================================================================
# SERVERS COMMANDS
# ==============================================================================
def cmd_servers_list(args):
    """List all registered servers."""
    print_header("Registered Servers")
    
    db = get_database()
    
    if args.game:
        game = db.get_game_by_name(args.game)
        if not game:
            print_error(f"Game not found: {args.game}")
            return
        servers = db.get_servers_by_game(game.id)
    else:
        servers = db.get_all_servers()
    
    if not servers:
        print_warning("No servers registered")
        return
    
    print(f"{'ID':<4} {'Server Name':<25} {'Game ID':<8} {'Status':<10} {'Custom':<8}")
    print("-" * 60)
    
    for server in servers:
        custom = "Yes" if server.has_custom else "No"
        print(f"{server.id:<4} {server.name:<25} {server.game_id:<8} {server.status:<10} {custom:<8}")
    
    print(f"\nTotal: {len(servers)} servers")


def cmd_servers_add(args):
    """Add a new server."""
    db = get_database()
    
    # Find game
    game = db.get_game_by_name(args.game)
    if not game:
        print_error(f"Game not found: {args.game}")
        return
    
    server = db.add_server(
        game_id=game.id,
        name=args.name,
        website=args.website,
        download_url=args.download,
        notes=args.notes
    )
    
    print_success(f"Added server: {server.name} (ID: {server.id})")


# ==============================================================================
# BASELINE COMMANDS
# ==============================================================================
def cmd_baseline_build(args):
    """Build vanilla baseline from a clean client."""
    print_header("Building Vanilla Baseline")
    
    db = get_database()
    
    # Find game
    game = db.get_game_by_name(args.game)
    if not game:
        print_error(f"Game not found: {args.game}")
        return
    
    # Check path exists
    if not os.path.isdir(args.path):
        print_error(f"Path does not exist: {args.path}")
        return
    
    print_info(f"Game: {game.name}")
    print_info(f"Path: {args.path}")
    print()
    
    # Create comparator and build baseline
    from src.core.comparator import AssetComparator
    
    comparator = AssetComparator(db, game.id)
    
    # Clear existing baseline if requested
    if args.clear:
        print_warning("Clearing existing baseline...")
        comparator.clear_baseline()
    
    # Build baseline
    count = comparator.build_baseline(
        args.path,
        progress_callback=progress_callback
    )
    
    print()
    print_success(f"Added {count} files to vanilla baseline")
    
    # Show stats
    stats = comparator.get_baseline_stats()
    print(f"\nBaseline Statistics:")
    print(f"  Total files: {stats['total_files']}")
    print(f"  Total size:  {stats['total_size_mb']} MB")


def cmd_baseline_stats(args):
    """Show baseline statistics."""
    print_header("Baseline Statistics")
    
    db = get_database()
    
    # Find game
    game = db.get_game_by_name(args.game)
    if not game:
        print_error(f"Game not found: {args.game}")
        return
    
    from src.core.comparator import AssetComparator
    
    comparator = AssetComparator(db, game.id)
    stats = comparator.get_baseline_stats()
    
    print(f"Game: {game.name}")
    print(f"Total files: {stats['total_files']}")
    print(f"Total size:  {stats['total_size_mb']} MB")


# ==============================================================================
# EXTRACT COMMANDS
# ==============================================================================
def cmd_extract(args):
    """Extract files from an archive."""
    print_header("Extracting Archive")
    
    archive_path = args.archive
    output_path = args.output
    
    # Check archive exists
    if not os.path.isfile(archive_path):
        print_error(f"Archive not found: {archive_path}")
        return
    
    print_info(f"Archive: {archive_path}")
    print_info(f"Output:  {output_path}")
    print()
    
    # Find appropriate extractor
    from src.extractors import ExtractorRegistry
    
    extractor = ExtractorRegistry.get_extractor_for_file(archive_path)
    
    if not extractor:
        print_error("No extractor found for this file type")
        print_info("Supported formats: " + ", ".join(ExtractorRegistry.list_supported_extensions()))
        return
    
    print_info(f"Using extractor: {extractor.game_name}")
    print()
    
    # Extract
    try:
        count = extractor.extract_all(output_path, progress_callback=progress_callback)
        print()
        print_success(f"Extracted {count} files")
    except Exception as e:
        print_error(f"Extraction failed: {e}")
    finally:
        extractor.close()


def cmd_extract_list(args):
    """List files in an archive."""
    print_header("Archive Contents")
    
    archive_path = args.archive
    
    # Check archive exists
    if not os.path.isfile(archive_path):
        print_error(f"Archive not found: {archive_path}")
        return
    
    # Find appropriate extractor
    from src.extractors import ExtractorRegistry
    
    extractor = ExtractorRegistry.get_extractor_for_file(archive_path)
    
    if not extractor:
        print_error("No extractor found for this file type")
        return
    
    # List files
    files = extractor.list_files()
    
    print(f"Archive: {archive_path}")
    print(f"Format:  {extractor.game_name}")
    print(f"Files:   {len(files)}")
    print()
    
    if args.verbose:
        print(f"{'Path':<60} {'Size':<12} {'Compressed':<12}")
        print("-" * 85)
        
        for entry in files[:args.limit]:
            path = entry.path
            if len(path) > 57:
                path = '...' + path[-57:]
            print(f"{path:<60} {entry.size:<12} {entry.compressed_size:<12}")
        
        if len(files) > args.limit:
            print(f"\n... and {len(files) - args.limit} more files")
    
    # Statistics
    total_size = sum(f.size for f in files)
    total_compressed = sum(f.compressed_size for f in files)
    
    print(f"\nTotal size: {total_size / (1024*1024):.2f} MB")
    print(f"Compressed: {total_compressed / (1024*1024):.2f} MB")
    
    extractor.close()


# ==============================================================================
# COMPARE COMMANDS
# ==============================================================================
def cmd_compare(args):
    """Compare a client against vanilla baseline."""
    print_header("Comparing Client to Vanilla")
    
    db = get_database()
    
    # Find game
    game = db.get_game_by_name(args.game)
    if not game:
        print_error(f"Game not found: {args.game}")
        return
    
    # Check path exists
    if not os.path.isdir(args.client):
        print_error(f"Client path does not exist: {args.client}")
        return
    
    print_info(f"Game:   {game.name}")
    print_info(f"Client: {args.client}")
    print()
    
    # Create comparator
    from src.core.comparator import AssetComparator
    
    comparator = AssetComparator(db, game.id)
    
    # Check baseline exists
    stats = comparator.get_baseline_stats()
    if stats['total_files'] == 0:
        print_error("No vanilla baseline found for this game")
        print_info("Run 'baseline build' first to create a baseline")
        return
    
    print_info(f"Baseline: {stats['total_files']} files ({stats['total_size_mb']} MB)")
    print()
    
    # Compare
    results = comparator.compare_directory(
        args.client,
        progress_callback=progress_callback
    )
    
    print()
    
    # Summary
    print(f"\n{Colors.BOLD}Results:{Colors.END}")
    print(f"  {Colors.GREEN}Identical:{Colors.END} {len(results['identical'])}")
    print(f"  {Colors.YELLOW}Modified:{Colors.END}  {len(results['modified'])}")
    print(f"  {Colors.CYAN}New:{Colors.END}       {len(results['new'])} (CUSTOM CONTENT)")
    print(f"  {Colors.RED}Unknown:{Colors.END}   {len(results['unknown'])}")
    
    # Export custom content if requested
    if args.output and (results['new'] or results['modified']):
        print()
        print_info(f"Exporting custom content to: {args.output}")
        
        from src.core.cataloger import AssetCataloger
        
        cataloger = AssetCataloger()
        counts = cataloger.organize_comparison_results(
            results,
            args.output,
            only_custom=True,
            structure='by_category'
        )
        
        print_success(f"Exported {sum(counts.values())} custom files")
        print(f"\nBy category:")
        for category, count in sorted(counts.items()):
            print(f"  {category}: {count}")


# ==============================================================================
# CATALOG COMMANDS
# ==============================================================================
def cmd_catalog(args):
    """Generate asset catalog from a directory."""
    print_header("Generating Asset Catalog")
    
    if not os.path.isdir(args.path):
        print_error(f"Path does not exist: {args.path}")
        return
    
    print_info(f"Path: {args.path}")
    print()
    
    from src.core.cataloger import AssetCataloger, CategorizedAsset
    
    cataloger = AssetCataloger()
    
    # Collect files
    files = []
    for root, dirs, filenames in os.walk(args.path):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, args.path)
            files.append({'path': rel_path, 'full_path': full_path, 'status': 'unknown'})
    
    print_info(f"Found {len(files)} files")
    
    # Categorize
    categorized = cataloger.categorize_files(files)
    
    # Show summary
    print(f"\n{Colors.BOLD}By Category:{Colors.END}")
    for category, assets in sorted(categorized.items()):
        total_size = sum(a.size for a in assets)
        print(f"  {category}: {len(assets)} files ({total_size / (1024*1024):.2f} MB)")
    
    # Save catalog if requested
    if args.output:
        all_assets = []
        for assets in categorized.values():
            all_assets.extend(assets)
        
        cataloger.save_catalog(all_assets, args.output, format=args.format)
        print_success(f"Saved catalog to {args.output}")


# ==============================================================================
# STATS COMMAND
# ==============================================================================
def cmd_stats(args):
    """Show overall statistics."""
    print_header("Asset Harvester Statistics")
    
    db = get_database()
    stats = db.get_stats()
    
    print(f"Games registered:     {stats['games']}")
    print(f"Servers registered:   {stats['servers']}")
    print(f"Clients tracked:      {stats['clients']}")
    print(f"Vanilla baseline:     {stats['vanilla_files']} files")
    print(f"Total assets:         {stats['total_assets']}")
    print(f"Custom assets found:  {stats['custom_assets']}")


# ==============================================================================
# MAIN ARGUMENT PARSER
# ==============================================================================
def main():
    """Main entry point for CLI."""
    # Check if colors are supported
    if sys.platform == 'win32':
        # Enable ANSI colors on Windows
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except:
            Colors.disable()
    
    # Create main parser
    parser = argparse.ArgumentParser(
        description="Asset Harvester - Universal Private Server Asset Extraction Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s games list                    List all supported games
  %(prog)s servers add --game "RO"       Add a new server
  %(prog)s baseline build --game "RO"    Build vanilla baseline
  %(prog)s extract --archive data.grf    Extract archive contents
  %(prog)s compare --game "RO"           Compare client to vanilla
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # -------------------------------------------------------------------------
    # GAMES commands
    # -------------------------------------------------------------------------
    games_parser = subparsers.add_parser('games', help='Manage supported games')
    games_sub = games_parser.add_subparsers(dest='subcommand')
    
    # games list
    games_list = games_sub.add_parser('list', help='List supported games')
    games_list.set_defaults(func=cmd_games_list)
    
    # games add
    games_add = games_sub.add_parser('add', help='Add a new game')
    games_add.add_argument('--name', required=True, help='Game name')
    games_add.add_argument('--format', required=True, help='Archive format (e.g., .grf)')
    games_add.add_argument('--extractor', required=True, help='Extractor module name')
    games_add.add_argument('--description', help='Game description')
    games_add.set_defaults(func=cmd_games_add)
    
    # -------------------------------------------------------------------------
    # SERVERS commands
    # -------------------------------------------------------------------------
    servers_parser = subparsers.add_parser('servers', help='Manage servers')
    servers_sub = servers_parser.add_subparsers(dest='subcommand')
    
    # servers list
    servers_list = servers_sub.add_parser('list', help='List registered servers')
    servers_list.add_argument('--game', help='Filter by game name')
    servers_list.set_defaults(func=cmd_servers_list)
    
    # servers add
    servers_add = servers_sub.add_parser('add', help='Add a new server')
    servers_add.add_argument('--game', required=True, help='Game name')
    servers_add.add_argument('--name', required=True, help='Server name')
    servers_add.add_argument('--website', help='Server website')
    servers_add.add_argument('--download', help='Client download URL')
    servers_add.add_argument('--notes', help='Additional notes')
    servers_add.set_defaults(func=cmd_servers_add)
    
    # -------------------------------------------------------------------------
    # BASELINE commands
    # -------------------------------------------------------------------------
    baseline_parser = subparsers.add_parser('baseline', help='Manage vanilla baselines')
    baseline_sub = baseline_parser.add_subparsers(dest='subcommand')
    
    # baseline build
    baseline_build = baseline_sub.add_parser('build', help='Build vanilla baseline')
    baseline_build.add_argument('--game', required=True, help='Game name')
    baseline_build.add_argument('--path', required=True, help='Path to vanilla client')
    baseline_build.add_argument('--clear', action='store_true', help='Clear existing baseline first')
    baseline_build.set_defaults(func=cmd_baseline_build)
    
    # baseline stats
    baseline_stats = baseline_sub.add_parser('stats', help='Show baseline statistics')
    baseline_stats.add_argument('--game', required=True, help='Game name')
    baseline_stats.set_defaults(func=cmd_baseline_stats)
    
    # -------------------------------------------------------------------------
    # EXTRACT commands
    # -------------------------------------------------------------------------
    extract_parser = subparsers.add_parser('extract', help='Extract archives')
    extract_parser.add_argument('--archive', required=True, help='Archive file to extract')
    extract_parser.add_argument('--output', required=True, help='Output directory')
    extract_parser.set_defaults(func=cmd_extract)
    
    # extract list
    extract_list = subparsers.add_parser('list', help='List archive contents')
    extract_list.add_argument('--archive', required=True, help='Archive file to list')
    extract_list.add_argument('--verbose', '-v', action='store_true', help='Show detailed list')
    extract_list.add_argument('--limit', type=int, default=100, help='Max files to show')
    extract_list.set_defaults(func=cmd_extract_list)
    
    # -------------------------------------------------------------------------
    # COMPARE commands
    # -------------------------------------------------------------------------
    compare_parser = subparsers.add_parser('compare', help='Compare client to vanilla')
    compare_parser.add_argument('--game', required=True, help='Game name')
    compare_parser.add_argument('--client', required=True, help='Path to client to compare')
    compare_parser.add_argument('--output', help='Output directory for custom content')
    compare_parser.set_defaults(func=cmd_compare)
    
    # -------------------------------------------------------------------------
    # CATALOG commands
    # -------------------------------------------------------------------------
    catalog_parser = subparsers.add_parser('catalog', help='Generate asset catalog')
    catalog_parser.add_argument('--path', required=True, help='Path to assets')
    catalog_parser.add_argument('--output', help='Output file for catalog')
    catalog_parser.add_argument('--format', choices=['txt', 'json', 'csv'], default='txt')
    catalog_parser.set_defaults(func=cmd_catalog)
    
    # -------------------------------------------------------------------------
    # STATS command
    # -------------------------------------------------------------------------
    stats_parser = subparsers.add_parser('stats', help='Show overall statistics')
    stats_parser.set_defaults(func=cmd_stats)
    
    # -------------------------------------------------------------------------
    # Parse and execute
    # -------------------------------------------------------------------------
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Handle subcommands
    if hasattr(args, 'func'):
        args.func(args)
    else:
        # Print help for the subcommand
        if args.command == 'games':
            games_parser.print_help()
        elif args.command == 'servers':
            servers_parser.print_help()
        elif args.command == 'baseline':
            baseline_parser.print_help()


if __name__ == "__main__":
    main()
