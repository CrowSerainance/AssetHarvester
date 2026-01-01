# Asset Harvester

**Universal Private Server Asset Extraction & Cataloging System**

Asset Harvester is a desktop application designed to extract, compare, and catalog game assets from private MMORPG server clients. It provides a unified interface for handling multiple game formats and supports extensibility for adding new games through a plugin architecture.

## Features

- 📦 **Multi-Format Extraction**: Support for GRF (Ragnarok Online), VFS (ROSE Online), PAK (RF Online), and many more through QuickBMS integration
- 🔍 **Custom Content Detection**: Automatically identify modified and new content by comparing against vanilla baselines
- 📁 **Asset Cataloging**: Organize assets by game, type (textures, models, sprites, audio, maps), and source server
- 🖥️ **Dual Interface**: Both GUI (PyQt6) and CLI for different workflows
- 🔌 **Extensible Architecture**: Easy to add support for new game formats through the extractor plugin system

## Supported Games

| Game | Archive Format | Status |
|------|---------------|--------|
| Ragnarok Online | .grf, .gpf, .thor | ✅ Implemented |
| ROSE Online | .vfs, .idx | 🔄 Planned |
| RF Online | .pak, .dat, .edf | 🔄 Planned |
| MU Online | .bmd, .ozj | 🔄 Planned |
| Lineage 2 | .u, .utx | 🔄 Planned |
| Flyff | .res | 🔄 Planned |
| Silkroad Online | .pk2 | 🔄 Planned |
| Any Other | Various | Via QuickBMS |

## Installation

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Quick Start

```bash
# Clone or download the project
git clone https://github.com/CrowSerainance/AssetHarvester.git
cd AssetHarvester

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### GUI Mode (Default)

```bash
python main.py
```

### CLI Mode

```bash
python main.py --cli [command]
```

## CLI Usage

### List Supported Games

```bash
python main.py --cli games list
```

### Add a Server

```bash
python main.py --cli servers add --game "Ragnarok Online" --name "NovaRO" --website "https://novaragnarok.com"
```

### Build Vanilla Baseline

Before comparing clients, you need to create a baseline from a clean/vanilla game client:

```bash
   python main.py --cli baseline build --game "Ragnarok Online" --path "C:\Games\RO_Vanilla"
```

### Extract Archive

```bash
python main.py --cli extract --archive "C:\Games\Server\data.grf" --output "C:\Extracted"
```

### Compare Client to Vanilla

```bash
python main.py --cli compare --game "Ragnarok Online" --client "C:\Games\ServerClient" --output "C:\CustomAssets"
```

### Generate Asset Catalog

```bash
python main.py --cli catalog --path "C:\Extracted" --output "catalog.json" --format json
```

## Project Structure

```
AssetHarvester/
├── main.py                 # Main entry point
├── requirements.txt        # Python dependencies
├── README.md              # This file
│
├── src/                   # Source code
│   ├── __init__.py
│   ├── cli.py            # Command-line interface
│   │
│   ├── core/             # Core engine modules
│   │   ├── __init__.py
│   │   ├── database.py   # SQLite database & models
│   │   ├── hasher.py     # File hashing utilities
│   │   ├── comparator.py # Vanilla comparison engine
│   │   └── cataloger.py  # Asset organization
│   │
│   ├── extractors/       # Game-specific extractors
│   │   ├── __init__.py
│   │   ├── base_extractor.py  # Abstract base class
│   │   ├── grf_extractor.py   # Ragnarok Online GRF
│   │   └── generic_extractor.py # QuickBMS wrapper
│   │
│   └── gui/              # PyQt6 GUI
│       ├── __init__.py
│       └── main_window.py
│
├── data/                 # Database and configs
│   └── harvester.db      # SQLite database (auto-created)
│
├── docs/                 # Documentation
│   └── TechSpec.docx     # Technical specification
│
└── tools/                # External tools
    ├── quickbms.exe      # QuickBMS (download separately)
    └── scripts/          # BMS scripts for various games
```

## Adding New Game Support

To add support for a new game:

1. Create a new extractor class in `src/extractors/`:

```python
from .base_extractor import BaseExtractor, ExtractorRegistry, FileEntry

class MyGameExtractor(BaseExtractor):
    @property
    def game_name(self) -> str:
        return "My Game"
    
    @property
    def supported_extensions(self) -> list:
        return ['.pak', '.dat']
    
    @property
    def extractor_id(self) -> str:
        return "mygame"
    
    def detect(self, path: str) -> bool:
        # Check if this extractor can handle the file
        pass
    
    def open(self, archive_path: str) -> bool:
        # Parse archive header and file table
        pass
    
    def list_files(self) -> list:
        # Return list of FileEntry objects
        pass
    
    def extract_file(self, file_path: str, output_path: str) -> bool:
        # Extract a single file
        pass
    
    def get_file_data(self, file_path: str) -> bytes:
        # Return file contents as bytes
        pass

# Register the extractor
ExtractorRegistry.register(MyGameExtractor)
```

2. Import in `src/extractors/__init__.py`

3. Add game to database:
```bash
python main.py --cli games add --name "My Game" --format ".pak" --extractor "mygame_extractor"
```

## Using QuickBMS for Unsupported Formats

For games without native support, use the GenericExtractor with QuickBMS:

1. Download QuickBMS from: https://aluigi.altervista.org/quickbms.htm
2. Place `quickbms.exe` in the `tools/` directory
3. Find or write a BMS script for your game
4. Place the script in `tools/scripts/`

```python
from src.extractors import GenericExtractor

extractor = GenericExtractor()
extractor.set_quickbms_path("tools/quickbms.exe")
extractor.set_script("tools/scripts/mygame.bms")
extractor.open("archive.pak")
extractor.extract_all("output/")
```

## Workflow Example

### Harvesting Custom Assets from a Private Server

1. **Download vanilla client** from the official game source
2. **Build baseline** from vanilla client:
   ```bash
   python main.py --cli baseline build --game "Ragnarok Online" --path "C:\Games\RO_Official"
   ```
3. **Download private server client**
4. **Compare to find custom content**:
   ```bash
   python main.py --cli compare --game "Ragnarok Online" --client "C:\Games\PrivateServer" --output "C:\CustomAssets"
   ```
5. **Browse and organize** the custom assets in the output folder

## Database Schema

The application uses SQLite to store:

- **games**: Supported games and their extractors
- **servers**: Registered private servers
- **clients**: Downloaded client folders
- **vanilla_files**: Baseline file hashes for comparison
- **assets**: Extracted assets with comparison status
- **asset_types**: Categories for organizing assets

## Contributing

Contributions are welcome! Areas that need work:

- [ ] More game format extractors
- [ ] DES decryption for encrypted GRF files
- [ ] Thumbnail generation for various asset types
- [ ] Asset preview in GUI
- [ ] Download manager for client downloads

## License

This project is for educational and personal use. Please respect game publishers' terms of service when working with game assets.

## Acknowledgments

- [QuickBMS](https://aluigi.altervista.org/quickbms.htm) by Luigi Auriemma
- [pygrf](https://github.com/bmeinka/pygrf) for GRF format research
- [rose-tools](https://github.com/rminderhoud/rose-tools) for ROSE Online tools
- The private server modding community for format documentation
