# Asset Harvester - User Guide

## Quick Start

### 1. Install Dependencies

```bash
cd E:\2026 PROJECT\AssetHarvester
pip install -r requirements.txt
```

### 2. Run the Application

**GUI Mode (Default)**
```bash
python main.py
```

**CLI Mode**
```bash
python main.py --cli [command]
```

## Core Concepts

### Games

Supported games are stored in the database. The default installation includes:
- Ragnarok Online (.grf)
- ROSE Online (.vfs)
- RF Online (.pak)

### Servers

Register private servers you want to track. Each server belongs to a game.

### Vanilla Baseline

A "vanilla baseline" is a hash fingerprint of all files in an official/clean game client. This is used to identify custom content in private server clients.

### Custom Content Detection

When you compare a private server client against the vanilla baseline:
- **Identical**: File hash matches vanilla (original content)
- **Modified**: Same path but different hash (edited content)
- **New**: Path doesn't exist in vanilla (completely custom)

## Workflow

### Step 1: Build Vanilla Baseline

```bash
python main.py --cli baseline build --game "Ragnarok Online" --path "E:\Official_RO_Client"
```

This scans all files in the official client and stores their hashes.

### Step 2: Register a Server

```bash
python main.py --cli servers add --game "Ragnarok Online" --name "MyPrivateServer" --website "https://server.com"
```

### Step 3: Compare Server Client

```bash
python main.py --cli compare --game "Ragnarok Online" --client "E:\MyServer_Client" --output "E:\CustomAssets"
```

This will:
1. Scan all files in the private server client
2. Compare each file against the vanilla baseline
3. Copy custom/modified files to the output directory
4. Generate a report

## CLI Commands Reference

### Games

```bash
# List all games
python main.py --cli games list

# Add a new game
python main.py --cli games add --name "My Game" --format ".pak" --extractor "generic"
```

### Servers

```bash
# List all servers
python main.py --cli servers list

# List servers for a specific game
python main.py --cli servers list --game "Ragnarok Online"

# Add a server
python main.py --cli servers add --game "Ragnarok Online" --name "NovaRO" --website "https://novaragnarok.com"
```

### Baseline

```bash
# Build baseline from vanilla client
python main.py --cli baseline build --game "Ragnarok Online" --path "E:\RO_Vanilla"

# Clear and rebuild
python main.py --cli baseline build --game "Ragnarok Online" --path "E:\RO_Vanilla" --clear

# Show baseline stats
python main.py --cli baseline stats --game "Ragnarok Online"
```

### Extract

```bash
# Extract an archive
python main.py --cli extract --archive "E:\server\data.grf" --output "E:\extracted"

# List archive contents
python main.py --cli list --archive "E:\server\data.grf" --verbose
```

### Compare

```bash
# Compare and export custom content
python main.py --cli compare --game "Ragnarok Online" --client "E:\ServerClient" --output "E:\Custom"
```

### Catalog

```bash
# Generate catalog from directory
python main.py --cli catalog --path "E:\extracted" --output "catalog.json" --format json
```

## Troubleshooting

### "No extractor found for this file type"

The file format isn't natively supported. Options:
1. Download QuickBMS and place in `tools/`
2. Find a BMS script for your game format
3. Use the GenericExtractor with a script

### "Database not found"

The database is created automatically on first run. If you see this error:
1. Check write permissions for `data/` directory
2. Ensure SQLAlchemy is installed: `pip install sqlalchemy`

### PyQt6 not installed

For GUI mode, install PyQt6:
```bash
pip install PyQt6
```

Or use CLI mode which doesn't require it.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## Character Designer (RO Only)

Asset Harvester includes a visual Character Designer for Ragnarok Online sprites. This allows you to:

- Preview character sprites with different job classes, genders, and hairstyles
- Test headgear, weapon, shield, and garment equipment
- Apply palette/dye variations
- Animate through all character actions
- Export rendered sprites as PNG

### Using the Character Designer

1. Extract RO data using the Extract tab
2. Go to the **🎨 Character Designer** tab
3. Browse to your extracted data folder
4. Select job, gender, and equipment
5. Use animation controls to preview

See `docs/CHARACTER_DESIGNER.md` for detailed documentation.

## File Formats

### Supported Natively

| Extension | Game | Extractor |
|-----------|------|-----------|
| .grf, .gpf | Ragnarok Online | GRFExtractor |
| .vfs, .idx | ROSE Online | VFSExtractor |

### Via QuickBMS

Any format with a BMS script can be extracted using GenericExtractor.

## Database Location

The SQLite database is stored at:
```
E:\2026 PROJECT\AssetHarvester\data\harvester.db
```

You can back this up to preserve your server registry and baseline data.
