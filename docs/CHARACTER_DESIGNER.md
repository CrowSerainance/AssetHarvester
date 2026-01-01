# Ragnarok Online Character Designer - Enhanced

A comprehensive visual character sprite designer for Ragnarok Online, integrated with Asset Harvester.

## New Features

### 1. Side-by-Side Comparison View
Compare vanilla sprites against custom/private server sprites:
- Set separate paths for vanilla and custom data
- View both versions simultaneously
- Automatic difference detection
- Visual indicators for modified/new content

### 2. Auto-Detect Custom Sprites
Integration with Asset Harvester's comparison database:
- Marks sprites as "Vanilla", "Modified", or "New (Custom)"
- Uses hash comparison against baseline
- Status indicator in preview area
- Works with existing comparison results

### 3. Batch Export
Mass export functionality for sprites:
- **All Headgear**: Export every headgear as individual PNG files
- **Headgear Sprite Sheet**: All headgear in one grid image
- **Job Animation Sheet**: Complete animation grid for a job class
- **All Jobs Preview**: Every job class in one preview image
- **Comparison Sheet**: Side-by-side vanilla vs custom export

### 4. Item Database Lookup
Built-in database of item names:
- 300+ headgear with names
- 200+ weapons with types
- Search by name or ID
- Double-click to equip from browser
- Automatic name display in equipment panel

---

## Installation

### Requirements
```bash
pip install PyQt6 Pillow
```

### Dependencies
- **Python 3.10+**
- **PyQt6** - GUI framework
- **Pillow** - Image processing
- **Asset Harvester** - Database integration (optional)

---

## Quick Start

### 1. Launch the Designer
The Character Designer is available as a tab in Asset Harvester, or standalone:

```python
from src.gui.character_designer import CharacterDesignerWidget
from PyQt6.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)
designer = CharacterDesignerWidget()
designer.show()
sys.exit(app.exec())
```

### 2. Set Resource Path
Point to your extracted RO data folder containing `data/sprite/`.

### 3. Use the Tabs

| Tab | Purpose |
|-----|---------|
| 🎨 Designer | Main character preview and configuration |
| ⚖️ Compare | Side-by-side vanilla vs custom comparison |
| 📦 Batch Export | Mass export sprites and sprite sheets |
| 🔍 Item Browser | Search and select headgear by name |

---

## Designer Tab

### Character Settings
| Setting | Description |
|---------|-------------|
| **Job** | Character class (Novice, Knight, etc.) |
| **Gender** | Male or Female |
| **Head** | Hairstyle number (1-30) |
| **Hair Color** | Palette index for hair dye |

### Equipment Panel
- **Headgear Top/Mid/Low**: Item ID with name lookup
- **Weapon**: Weapon sprite ID
- **Shield**: Shield sprite ID
- Names display automatically from database

### Animation Controls
- **Action**: Stand, Walk, Sit, Attack, etc.
- **Direction**: 8 directions (S, SW, W, NW, N, NE, E, SE)
- **Frame**: Current animation frame
- **Play/Stop**: Animation playback
- **Speed**: Playback speed multiplier

### Custom Status Indicator
Shows whether current sprites are:
- ✓ **Vanilla**: Matches original game files
- ⚠️ **Modified**: Same path but different content
- ⭐ **Custom/New**: Not in vanilla data

---

## Compare Tab

### Setup
1. Set **Vanilla Data** path to extracted official client
2. Set **Custom Data** path to extracted private server client
3. Click "Sync to Comparison" from Designer tab

### Features
- Side-by-side preview
- Automatic difference detection
- Size comparison
- Status indicators for each version

---

## Batch Export Tab

### Export Types

#### All Headgear (Individual PNGs)
Exports every known headgear as separate PNG files.
- Uses item database for filenames
- Organized by ID and name
- Transparent backgrounds

#### Headgear Sprite Sheet
Single image containing all headgear in a grid.
- Configurable columns
- Optional labels
- Good for preview/documentation

#### Job Animation Sheet
Complete animation reference for one job class.
- All actions in rows
- All frames in columns
- Action labels included

#### All Jobs Preview
One image showing every job class standing.
- Quick visual reference
- 6 columns default
- Labels for each job

#### Comparison Sheet
Side-by-side export of vanilla vs custom sprites.
- Three columns: Label, Vanilla, Custom
- Multiple items per sheet
- Difference indicators

### Progress Tracking
- Real-time progress bar
- Log output for each item
- Error reporting
- Skip list for missing sprites

---

## Item Browser Tab

### Features
- Search by name or ID
- Table view with ID, Name, Slot
- Double-click to equip
- "Use" button to apply to character

### Item Database
Built-in database includes:
- ~100 common headgear
- Standard weapons by type
- Shields
- Can load from itemInfo.lua

### Loading External Data
```python
from src.parsers.item_database import ItemDatabase

db = ItemDatabase()
db.load_defaults()  # Built-in data
db.load_from_lua("path/to/itemInfo.lua")  # From client
db.save_to_json("items.json")  # Export for later
```

---

## File Formats

### SPR (Sprite)
- Contains indexed and RGBA frames
- Palette-based recoloring support
- RLE compression
- Versions 1.0 - 2.1

### ACT (Action)
- Animation definitions
- Layers with transforms
- Anchor points for attachment
- Event triggers for sounds

### PAL (Palette)
- 256 colors × 4 bytes (RGBA)
- 1024 bytes total
- Used for hair dyes, class palettes

---

## Sprite Paths

### Body Sprites
```
data/sprite/인간족/몸통/{gender}/{job}_{gender}.spr
data/sprite/인간족/몸통/남/초보자_남.spr  # Male Novice
data/sprite/인간족/몸통/여/기사_여.spr   # Female Knight
```

### Head Sprites
```
data/sprite/인간족/머리통/{gender}/{head_id}_{gender}.spr
data/sprite/인간족/머리통/남/1_남.spr  # Male head #1
```

### Headgear Sprites
```
data/sprite/악세사리/{gender}/{gender}_{item_id}.spr
data/sprite/악세사리/남/남_2220.spr  # Male Hat
```

---

## Job Reference

### Basic Jobs (ID 0-6)
| ID | Name | Folder |
|----|------|--------|
| 0 | Novice | 초보자 |
| 1 | Swordman | 검사 |
| 2 | Mage | 마법사 |
| 3 | Archer | 궁수 |
| 4 | Acolyte | 성직자 |
| 5 | Merchant | 상인 |
| 6 | Thief | 도둑 |

### 2-1 Jobs (ID 7-12)
| ID | Name | Folder |
|----|------|--------|
| 7 | Knight | 기사 |
| 8 | Priest | 프리스트 |
| 9 | Wizard | 위저드 |
| 10 | Blacksmith | 제철공 |
| 11 | Hunter | 헌터 |
| 12 | Assassin | 어세신 |

### 2-2 Jobs (ID 14-20)
| ID | Name | Folder |
|----|------|--------|
| 14 | Crusader | 크루세이더 |
| 15 | Monk | 몽크 |
| 16 | Sage | 세이지 |
| 17 | Rogue | 로그 |
| 18 | Alchemist | 연금술사 |
| 19 | Bard | 바드 |
| 20 | Dancer | 무희 |

### Transcendent (ID 4008+)
| ID | Name | Folder |
|----|------|--------|
| 4008 | Lord Knight | 로드나이트 |
| 4009 | High Priest | 하이프리스트 |
| 4010 | High Wizard | 하이위저드 |
| 4011 | Whitesmith | 화이트스미스 |
| 4012 | Sniper | 스나이퍼 |
| 4013 | Assassin Cross | 어쌔신 크로스 |

---

## Headgear ID Reference

### Common Headgear (2201-2300)
| ID | Name |
|----|------|
| 2201 | Sunglasses |
| 2202 | Glasses |
| 2210 | Santa Hat |
| 2220 | Hat |
| 2221 | Cap |
| 2222 | Beret |
| 2230 | Archangel Wing |
| 2236 | Helm |
| 2257 | Majestic Goat |

### Middle Headgear (5000-5100)
| ID | Name |
|----|------|
| 5000 | Sunglasses [1] |
| 5001 | Glasses [1] |
| 5002 | Eye Patch |
| 5013 | Blush |
| 5014 | Robo Eye |

### Lower Headgear (5100-5200)
| ID | Name |
|----|------|
| 5100 | Grandpa Beard |
| 5105 | Gangster Mask |
| 5106 | Lollipop |

---

## Troubleshooting

### "No sprite found"
1. Verify resource path is correct
2. Check that data is extracted (not in GRF)
3. Ensure folder structure matches expected format
4. Try different job/gender combinations

### "Pillow not installed"
```bash
pip install Pillow
```

### "PyQt6 not installed"
```bash
pip install PyQt6
```

### Comparison shows "Unknown" status
- Set baseline in Custom Detector
- Load vanilla file hashes from database
- Run comparison in Asset Harvester first

### Batch export fails
- Check output path is writable
- Ensure resource path is set
- Check for specific error in log

### Item names not showing
- Load item database: `db.load_defaults()`
- Or load from itemInfo.lua
- Check item ID exists in database

---

## API Reference

### SpriteCompositor
```python
compositor = SpriteCompositor(resource_path)
compositor.job = "Knight"
compositor.gender = "male"
compositor.headgear_top = 2220
img = compositor.render_frame(action=0, frame=0, direction=0)
```

### ItemDatabase
```python
db = get_item_database()
name = db.get_headgear_name(2220)  # "Hat"
results = db.search_headgear("crown")
```

### BatchExporter
```python
exporter = BatchExporter(compositor, output_path, item_db)
result = exporter.export_all_headgear(headgear_ids, gender)
result = exporter.export_headgear_spritesheet(ids, gender, config)
```

### CustomSpriteDetector
```python
detector = CustomSpriteDetector(baseline=vanilla_hashes)
status = detector.check_sprite(sprite_path)  # 'vanilla', 'modified', 'new'
```

---

## Credits

- File format documentation: [Ragnarok Research Lab](https://ragnarokresearchlab.github.io/)
- Inspired by: [RateMyServer Character Simulator](https://ro-character-simulator.ratemyserver.net/)
- Rendering techniques from: [zrenderer](https://github.com/zhad3/zrenderer)

## License

Part of Asset Harvester - MIT License
