# ==============================================================================
# ITEM DATABASE MODULE
# ==============================================================================
# Database of Ragnarok Online item names and metadata.
#
# This module provides lookup tables for:
#   - Headgear item IDs → Display names
#   - Weapon item IDs → Display names and types
#   - Shield item IDs → Display names
#   - Card item IDs → Display names
#
# Data can be loaded from:
#   - Built-in defaults (common items)
#   - itemInfo.lua from client data
#   - Custom CSV/JSON files
#   - rAthena/Hercules item databases
#
# Usage:
#   db = ItemDatabase()
#   db.load_defaults()  # Load built-in data
#   
#   name = db.get_headgear_name(2220)  # "Hat"
#   weapon_type = db.get_weapon_type(1101)  # "Sword"
# ==============================================================================

import os
import re
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class ItemInfo:
    """
    Information about a game item.
    
    Attributes:
        id (int):           Item ID
        name (str):         Display name (English)
        name_korean (str):  Korean name (if available)
        slot (str):         Equipment slot (headtop, headmid, headlow, weapon, shield)
        sprite_id (int):    Sprite ID for rendering (may differ from item ID)
        description (str):  Item description
        class_num (int):    View class number for sprites
    """
    id: int = 0
    name: str = ""
    name_korean: str = ""
    slot: str = ""
    sprite_id: int = 0
    description: str = ""
    class_num: int = 0


@dataclass  
class WeaponInfo(ItemInfo):
    """
    Extended information for weapons.
    
    Attributes:
        weapon_type (str):  Type of weapon (sword, staff, bow, etc.)
        weapon_level (int): Weapon level (1-4)
        attack (int):       Base attack power
    """
    weapon_type: str = ""
    weapon_level: int = 1
    attack: int = 0


# ==============================================================================
# DEFAULT HEADGEAR DATA
# ==============================================================================
# This is a subset of common headgear items with their names.
# The full list would come from itemInfo.lua or a database.

DEFAULT_HEADGEAR = {
    # Top Headgear (Helmets, Hats)
    2201: "Sunglasses",
    2202: "Glasses",
    2203: "Diver Goggles",
    2206: "Flu Mask",
    2207: "Gas Mask",
    2208: "Elven Ears",
    2209: "Fin Helm",
    2210: "Santa Hat",
    2211: "Antenna",
    2212: "Angelic Hairpin",
    2213: "Mage Hat",
    2214: "Wizard Hat",
    2215: "Big Ribbon",
    2216: "Nurse Cap",
    2217: "Bunny Band",
    2218: "Cat Ear Hairband",
    2219: "Flower Hairband",
    2220: "Hat",
    2221: "Cap",
    2222: "Beret",
    2223: "Bonnet",
    2224: "Chinese Crown",
    2225: "Ghost Bandana",
    2226: "Straw Hat",
    2227: "Biretta",
    2228: "Binoculars",
    2229: "Flower",
    2230: "Archangel Wing",
    2231: "Cowboy Hat",
    2232: "Candle",
    2233: "Crown",
    2234: "Corsair",
    2235: "Tiara",
    2236: "Helm",
    2237: "Celebrant Mitre",
    2238: "Joker Jester",
    2239: "Parcher Hat",
    2240: "Ramen Hat",
    2241: "Viking Helm",
    2242: "Bowing Hat",
    2243: "Bucket Hat",
    2244: "Party Hat",
    2245: "Feather Beret",
    2246: "Decorative Mushroom",
    2247: "Army Cap",
    2248: "Poo Poo Hat",
    2249: "Funeral Hat",
    2250: "Funeral Dress Hat",
    2251: "Magician Hat",
    2252: "Round Hat",
    2253: "Sweet Gent",
    2254: "Golden Helm",
    2255: "Mine Helm",
    2256: "Headset",
    2257: "Magestic Goat",
    2258: "Romantic Flower",
    2259: "Purple Cowboy Hat",
    2260: "Romantic Leaf",
    2261: "Giant Band Aid",
    2262: "Sombrero",
    2263: "Ear Muffs",
    2264: "Antlers",
    2265: "Apple o' Archer",
    2266: "Bone Helm",
    2267: "Pirate Bandana",
    2268: "Assassin Mask",
    2269: "Munak Hat",
    2270: "Bongun Hat",
    2271: "Leopard Hood",
    2272: "Twisted Ribbon",
    2273: "Alice Doll",
    2274: "Magic Eyes",
    2275: "Angry Mouth",
    2276: "Bubble Gum",
    2277: "Opera Phantom Mask",
    2278: "Orc Hero Helm",
    2279: "Rideword Hat",
    2280: "Drooping Cat",
    2281: "Miner Hat",
    2282: "Crescent Helm",
    2283: "Kabuki Mask",
    2284: "Executioner Hood",
    2285: "Ph.D Hat",
    2286: "Arch Bishop Crown",
    
    # Mid Headgear (Glasses, Masks)
    5000: "Sunglasses [1]",
    5001: "Glasses [1]",
    5002: "Eye Patch",
    5003: "Pipe",
    5004: "Monocle",
    5005: "Opera Mask",
    5006: "Masquerade",
    5007: "Cigarette",
    5008: "Cyclops Eye",
    5009: "Blank Eyes",
    5010: "Evil Wing Ears",
    5011: "Angel Wing Ears",
    5012: "Geek Glasses",
    5013: "Blush",
    5014: "Robo Eye",
    
    # Low Headgear (Mouth items)
    5100: "Granpa Beard",
    5101: "Spiked Scarf",
    5102: "Doctor Band",
    5103: "Angel's Kiss",
    5104: "Romantic Gent",
    5105: "Gangster Mask",
    5106: "Lollipop",
    5107: "Candy Cane",
    
    # Popular Custom Headgear IDs (common on private servers)
    5170: "Drooping Bunny",
    5171: "Hermose Cap",
    5172: "Crescent Hairpin",
    5173: "Coppola",
    5174: "Drooping Kitty",
    5175: "Smokie Leaf",
    5176: "Panda Cap",
    5200: "Wanderer's Sakkat",
    5201: "Fish Head",
    5202: "Sheep Hat",
    5203: "Pumpkin Hat",
    5204: "Jack be Dandy",
    5205: "Striped Hairband",
    5206: "Kitty Hairband",
    5207: "Fairy Ears",
    5208: "Frog Hat",
    5209: "Bunny Ear Hat",
    5210: "Penguin Cap",
    
    # Cash Shop Items (common range)
    5300: "Valkyrie Helm",
    5301: "Rabbit Ears",
    5302: "Deviling Hat",
    5303: "Angel Spirit",
    5304: "Evil Spirit",
    5305: "Fallen Angel Wing",
    5306: "Lover in Mouth",
    5307: "Love Balloon",
    5308: "Rice Cake Hat",
    5309: "Event Hat",
    5310: "Lucky Clover",
}

# ==============================================================================
# DEFAULT WEAPON DATA
# ==============================================================================

DEFAULT_WEAPONS = {
    # Daggers
    1201: ("Knife", "Dagger"),
    1202: ("Cutter", "Dagger"),
    1203: ("Main Gauche", "Dagger"),
    1204: ("Dirk", "Dagger"),
    1205: ("Dagger", "Dagger"),
    1206: ("Stiletto", "Dagger"),
    1207: ("Gladius", "Dagger"),
    1208: ("Damascus", "Dagger"),
    1209: ("Fortune Sword", "Dagger"),
    1210: ("Sword Breaker", "Dagger"),
    1211: ("Mail Breaker", "Dagger"),
    1212: ("Assassin Dagger", "Dagger"),
    1213: ("Poison Knife", "Dagger"),
    1214: ("Princess Knife", "Dagger"),
    1215: ("Cursed Dagger", "Dagger"),
    1216: ("Counter Dagger", "Dagger"),
    1217: ("Grimtooth", "Dagger"),
    1218: ("Cinquedea", "Dagger"),
    1219: ("Kindling Dagger", "Dagger"),
    1220: ("Obsidian Dagger", "Dagger"),
    
    # One-Handed Swords
    1101: ("Sword", "Sword"),
    1102: ("Falchion", "Sword"),
    1103: ("Blade", "Sword"),
    1104: ("Lapier", "Sword"),
    1105: ("Scimitar", "Sword"),
    1106: ("Katana", "Sword"),
    1107: ("Tsurugi", "Sword"),
    1108: ("Ring Pommel Saber", "Sword"),
    1109: ("Haedonggum", "Sword"),
    1110: ("Fire Brand", "Sword"),
    1111: ("Ice Falchion", "Sword"),
    1112: ("Edge", "Sword"),
    1113: ("Cutlas", "Sword"),
    1114: ("Solar Sword", "Sword"),
    1115: ("Excalibur", "Sword"),
    1116: ("Mysteltainn", "Sword"),
    1117: ("Talefing", "Sword"),
    1118: ("Byeollungum", "Sword"),
    1119: ("Immaterial Sword", "Sword"),
    1120: ("Nagan", "Sword"),
    
    # Two-Handed Swords
    1151: ("Slayer", "Two-Hand Sword"),
    1152: ("Bastard Sword", "Two-Hand Sword"),
    1153: ("Two-Handed Sword", "Two-Hand Sword"),
    1154: ("Broad Sword", "Two-Hand Sword"),
    1155: ("Claymore", "Two-Hand Sword"),
    1156: ("Muramasa", "Two-Hand Sword"),
    1157: ("Masamune", "Two-Hand Sword"),
    1158: ("Dragon Slayer", "Two-Hand Sword"),
    1159: ("Executioner", "Two-Hand Sword"),
    1160: ("Katzbalger", "Two-Hand Sword"),
    
    # Spears
    1401: ("Javelin", "Spear"),
    1402: ("Spear", "Spear"),
    1403: ("Pike", "Spear"),
    1404: ("Guisarme", "Spear"),
    1405: ("Glaive", "Spear"),
    1406: ("Partizan", "Spear"),
    1407: ("Trident", "Spear"),
    1408: ("Halberd", "Spear"),
    1409: ("Crescent Scythe", "Spear"),
    1410: ("Bill Guisarme", "Spear"),
    
    # Staves
    1601: ("Rod", "Staff"),
    1602: ("Wand", "Staff"),
    1603: ("Staff", "Staff"),
    1604: ("Arc Wand", "Staff"),
    1605: ("Mighty Staff", "Staff"),
    1606: ("Blessed Wand", "Staff"),
    1607: ("Bone Wand", "Staff"),
    1608: ("Staff of Destruction", "Staff"),
    1609: ("Staff of Recovery", "Staff"),
    1610: ("Walking Stick", "Staff"),
    1611: ("Release of Wish", "Staff"),
    1612: ("Elder Staff", "Staff"),
    1613: ("Hypnotist's Staff", "Staff"),
    1614: ("Survivor's Staff", "Staff"),
    
    # Bows
    1701: ("Bow", "Bow"),
    1702: ("Composite Bow", "Bow"),
    1703: ("Great Bow", "Bow"),
    1704: ("Crossbow", "Bow"),
    1705: ("Arbalest", "Bow"),
    1706: ("Kakkung", "Bow"),
    1707: ("Hunter Bow", "Bow"),
    1708: ("Gakkung", "Bow"),
    1709: ("Ballista", "Bow"),
    1710: ("Rudra Bow", "Bow"),
    1711: ("Mystery Bow", "Bow"),
    1712: ("Orc Archer Bow", "Bow"),
    
    # Maces
    1501: ("Club", "Mace"),
    1502: ("Mace", "Mace"),
    1503: ("Smasher", "Mace"),
    1504: ("Flail", "Mace"),
    1505: ("Morning Star", "Mace"),
    1506: ("Sword Mace", "Mace"),
    1507: ("Chain", "Mace"),
    1508: ("Stunner", "Mace"),
    1509: ("Golden Mace", "Mace"),
    1510: ("Long Mace", "Mace"),
    1511: ("Slash", "Mace"),
    1512: ("Spike", "Mace"),
    1513: ("Mjolnir", "Mace"),
    
    # Axes
    1301: ("Axe", "Axe"),
    1302: ("Battle Axe", "Axe"),
    1303: ("Hammer", "Axe"),
    1304: ("Buster", "Axe"),
    1305: ("Two-Handed Axe", "Axe"),
    
    # Katars
    1251: ("Jur", "Katar"),
    1252: ("Katar", "Katar"),
    1253: ("Jamadhar", "Katar"),
    1254: ("Infiltrator", "Katar"),
    1255: ("Sharpened Legbone", "Katar"),
    1256: ("Bloody Roar", "Katar"),
    1257: ("Unholy Touch", "Katar"),
}

# ==============================================================================
# DEFAULT SHIELD DATA
# ==============================================================================

DEFAULT_SHIELDS = {
    2101: "Guard",
    2102: "Buckler",
    2103: "Shield",
    2104: "Mirror Shield",
    2105: "Memorize Book",
    2106: "Holy Guard",
    2107: "Herald of GOD",
    2108: "Platinum Shield",
    2109: "Orleans's Server",
    2110: "Thorny Buckler",
    2111: "Strong Shield",
    2112: "Geffenia Water",
    2113: "Bradium Shield",
    2114: "Immune Shield",
    2115: "Flame Thrower",
    2116: "Energy Fiber",
    2117: "Token of Siegfried",
}


# ==============================================================================
# ITEM DATABASE CLASS
# ==============================================================================

class ItemDatabase:
    """
    Database of Ragnarok Online item information.
    
    Provides lookup for item names, types, and sprite IDs.
    Can be populated from built-in defaults, Lua files, or custom sources.
    
    Attributes:
        headgear (dict):    Headgear ID -> ItemInfo
        weapons (dict):     Weapon ID -> WeaponInfo
        shields (dict):     Shield ID -> ItemInfo
        loaded_sources (list): List of loaded data sources
    """
    
    def __init__(self):
        """Initialize empty item database."""
        self.headgear: Dict[int, ItemInfo] = {}
        self.weapons: Dict[int, WeaponInfo] = {}
        self.shields: Dict[int, ItemInfo] = {}
        self.loaded_sources: List[str] = []
    
    def load_defaults(self):
        """
        Load built-in default item data.
        
        This provides a basic set of common items without requiring
        external data files.
        """
        # Load headgear
        for item_id, name in DEFAULT_HEADGEAR.items():
            slot = "headtop"
            if 5000 <= item_id < 5100:
                slot = "headmid"
            elif 5100 <= item_id < 5200:
                slot = "headlow"
            
            self.headgear[item_id] = ItemInfo(
                id=item_id,
                name=name,
                slot=slot,
                sprite_id=item_id
            )
        
        # Load weapons
        for item_id, (name, weapon_type) in DEFAULT_WEAPONS.items():
            self.weapons[item_id] = WeaponInfo(
                id=item_id,
                name=name,
                slot="weapon",
                weapon_type=weapon_type
            )
        
        # Load shields
        for item_id, name in DEFAULT_SHIELDS.items():
            self.shields[item_id] = ItemInfo(
                id=item_id,
                name=name,
                slot="shield"
            )
        
        self.loaded_sources.append("defaults")
        print(f"[INFO] Loaded default items: {len(self.headgear)} headgear, "
              f"{len(self.weapons)} weapons, {len(self.shields)} shields")
    
    def load_from_lua(self, lua_path: str) -> bool:
        """
        Load item data from itemInfo.lua file.
        
        This file is found in RO client data and contains item names,
        descriptions, and sprite IDs for all items.
        
        Args:
            lua_path: Path to itemInfo.lua file
            
        Returns:
            True if loaded successfully
        """
        if not os.path.exists(lua_path):
            print(f"[ERROR] Lua file not found: {lua_path}")
            return False
        
        try:
            with open(lua_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Parse Lua table format
            # Format: [ITEM_ID] = { ... identifiedDisplayName = "Name", ... }
            pattern = r'\[(\d+)\]\s*=\s*\{([^}]+)\}'
            matches = re.findall(pattern, content, re.DOTALL)
            
            for item_id_str, item_data in matches:
                item_id = int(item_id_str)
                
                # Extract display name
                name_match = re.search(r'identifiedDisplayName\s*=\s*"([^"]+)"', item_data)
                if not name_match:
                    continue
                
                name = name_match.group(1)
                
                # Extract slot info
                slot_match = re.search(r'slotCount\s*=\s*(\d+)', item_data)
                slot = slot_match.group(1) if slot_match else "0"
                
                # Determine item category by ID range
                if 2200 <= item_id < 3000 or 5000 <= item_id < 6000:
                    # Headgear
                    hg_slot = "headtop"
                    if 5000 <= item_id < 5100:
                        hg_slot = "headmid"
                    elif 5100 <= item_id < 5200:
                        hg_slot = "headlow"
                    
                    self.headgear[item_id] = ItemInfo(
                        id=item_id,
                        name=name,
                        slot=hg_slot,
                        sprite_id=item_id
                    )
                
                elif 1100 <= item_id < 1800:
                    # Weapons
                    weapon_type = self._guess_weapon_type(item_id)
                    self.weapons[item_id] = WeaponInfo(
                        id=item_id,
                        name=name,
                        slot="weapon",
                        weapon_type=weapon_type
                    )
                
                elif 2100 <= item_id < 2200:
                    # Shields
                    self.shields[item_id] = ItemInfo(
                        id=item_id,
                        name=name,
                        slot="shield"
                    )
            
            self.loaded_sources.append(f"lua:{lua_path}")
            print(f"[INFO] Loaded from Lua: {len(matches)} items parsed")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to parse Lua file: {e}")
            return False
    
    def load_from_json(self, json_path: str) -> bool:
        """
        Load item data from a JSON file.
        
        Expected format:
        {
            "headgear": {
                "2220": {"name": "Hat", "slot": "headtop"},
                ...
            },
            "weapons": {...},
            "shields": {...}
        }
        
        Args:
            json_path: Path to JSON file
            
        Returns:
            True if loaded successfully
        """
        if not os.path.exists(json_path):
            print(f"[ERROR] JSON file not found: {json_path}")
            return False
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load headgear
            if 'headgear' in data:
                for item_id_str, info in data['headgear'].items():
                    item_id = int(item_id_str)
                    self.headgear[item_id] = ItemInfo(
                        id=item_id,
                        name=info.get('name', f'Headgear {item_id}'),
                        slot=info.get('slot', 'headtop'),
                        sprite_id=info.get('sprite_id', item_id)
                    )
            
            # Load weapons
            if 'weapons' in data:
                for item_id_str, info in data['weapons'].items():
                    item_id = int(item_id_str)
                    self.weapons[item_id] = WeaponInfo(
                        id=item_id,
                        name=info.get('name', f'Weapon {item_id}'),
                        slot='weapon',
                        weapon_type=info.get('type', 'Unknown')
                    )
            
            # Load shields
            if 'shields' in data:
                for item_id_str, info in data['shields'].items():
                    item_id = int(item_id_str)
                    self.shields[item_id] = ItemInfo(
                        id=item_id,
                        name=info.get('name', f'Shield {item_id}'),
                        slot='shield'
                    )
            
            self.loaded_sources.append(f"json:{json_path}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to load JSON: {e}")
            return False
    
    def save_to_json(self, json_path: str) -> bool:
        """
        Save current database to JSON file.
        
        Args:
            json_path: Output file path
            
        Returns:
            True if saved successfully
        """
        try:
            data = {
                'headgear': {
                    str(k): {'name': v.name, 'slot': v.slot, 'sprite_id': v.sprite_id}
                    for k, v in self.headgear.items()
                },
                'weapons': {
                    str(k): {'name': v.name, 'type': v.weapon_type}
                    for k, v in self.weapons.items()
                },
                'shields': {
                    str(k): {'name': v.name}
                    for k, v in self.shields.items()
                }
            }
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to save JSON: {e}")
            return False
    
    def _guess_weapon_type(self, item_id: int) -> str:
        """Guess weapon type from ID range."""
        if 1100 <= item_id < 1150:
            return "Sword"
        elif 1150 <= item_id < 1200:
            return "Two-Hand Sword"
        elif 1200 <= item_id < 1250:
            return "Dagger"
        elif 1250 <= item_id < 1300:
            return "Katar"
        elif 1300 <= item_id < 1400:
            return "Axe"
        elif 1400 <= item_id < 1500:
            return "Spear"
        elif 1500 <= item_id < 1550:
            return "Mace"
        elif 1550 <= item_id < 1600:
            return "Book"
        elif 1600 <= item_id < 1650:
            return "Staff"
        elif 1650 <= item_id < 1700:
            return "Two-Hand Staff"
        elif 1700 <= item_id < 1750:
            return "Bow"
        elif 1750 <= item_id < 1800:
            return "Instrument/Whip"
        else:
            return "Unknown"
    
    # ==========================================================================
    # GETTERS
    # ==========================================================================
    
    def get_headgear_name(self, item_id: int) -> str:
        """
        Get headgear name by ID.
        
        Args:
            item_id: Headgear item ID
            
        Returns:
            Item name or "Unknown Headgear {id}" if not found
        """
        if item_id in self.headgear:
            return self.headgear[item_id].name
        return f"Headgear {item_id}"
    
    def get_headgear_info(self, item_id: int) -> Optional[ItemInfo]:
        """Get full headgear info by ID."""
        return self.headgear.get(item_id)
    
    def get_weapon_name(self, item_id: int) -> str:
        """Get weapon name by ID."""
        if item_id in self.weapons:
            return self.weapons[item_id].name
        return f"Weapon {item_id}"
    
    def get_weapon_type(self, item_id: int) -> str:
        """Get weapon type (Sword, Staff, etc.) by ID."""
        if item_id in self.weapons:
            return self.weapons[item_id].weapon_type
        return self._guess_weapon_type(item_id)
    
    def get_shield_name(self, item_id: int) -> str:
        """Get shield name by ID."""
        if item_id in self.shields:
            return self.shields[item_id].name
        return f"Shield {item_id}"
    
    def get_all_headgear(self) -> List[ItemInfo]:
        """Get all headgear sorted by ID."""
        return sorted(self.headgear.values(), key=lambda x: x.id)
    
    def get_all_weapons(self) -> List[WeaponInfo]:
        """Get all weapons sorted by ID."""
        return sorted(self.weapons.values(), key=lambda x: x.id)
    
    def get_all_shields(self) -> List[ItemInfo]:
        """Get all shields sorted by ID."""
        return sorted(self.shields.values(), key=lambda x: x.id)
    
    def search_headgear(self, query: str) -> List[ItemInfo]:
        """
        Search headgear by name.
        
        Args:
            query: Search string (case-insensitive)
            
        Returns:
            List of matching headgear
        """
        query_lower = query.lower()
        return [
            hg for hg in self.headgear.values()
            if query_lower in hg.name.lower()
        ]
    
    def search_weapons(self, query: str) -> List[WeaponInfo]:
        """Search weapons by name."""
        query_lower = query.lower()
        return [
            w for w in self.weapons.values()
            if query_lower in w.name.lower()
        ]


# ==============================================================================
# SINGLETON INSTANCE
# ==============================================================================

# Global item database instance
_item_db: Optional[ItemDatabase] = None

def get_item_database() -> ItemDatabase:
    """
    Get the global item database instance.
    
    Creates and loads defaults on first call.
    
    Returns:
        ItemDatabase instance
    """
    global _item_db
    if _item_db is None:
        _item_db = ItemDatabase()
        _item_db.load_defaults()
    return _item_db


# ==============================================================================
# STANDALONE TEST
# ==============================================================================

if __name__ == "__main__":
    db = ItemDatabase()
    db.load_defaults()
    
    print("\n--- Sample Headgear ---")
    for hg in db.get_all_headgear()[:10]:
        print(f"  [{hg.id}] {hg.name} ({hg.slot})")
    
    print("\n--- Sample Weapons ---")
    for w in db.get_all_weapons()[:10]:
        print(f"  [{w.id}] {w.name} ({w.weapon_type})")
    
    print("\n--- Search: 'hat' ---")
    for hg in db.search_headgear("hat")[:5]:
        print(f"  [{hg.id}] {hg.name}")
