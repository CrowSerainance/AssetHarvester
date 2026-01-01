# ==============================================================================
# DATABASE MODULE
# ==============================================================================
# SQLite database for storing all metadata about games, servers, clients,
# and extracted assets. Uses SQLAlchemy ORM for clean data access.
#
# Tables:
#   - games:        Supported games and their archive formats
#   - servers:      Private servers registered in the system
#   - clients:      Downloaded client folders
#   - vanilla_files: Baseline file hashes for each game
#   - assets:       Extracted assets with comparison status
#   - asset_types:  Categories for organizing assets
# ==============================================================================

import os
from datetime import datetime
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# ==============================================================================
# SQLAlchemy Base Class
# ==============================================================================
# This is the base class that all our database models inherit from.
# It provides the foundation for creating database tables from Python classes.
Base = declarative_base()


# ==============================================================================
# GAME MODEL
# ==============================================================================
# Represents a supported game in the system. Each game has specific archive
# formats and an associated extractor module that knows how to read its files.
#
# Example:
#   game = Game(name="Ragnarok Online", archive_format=".grf", 
#               extractor_module="grf_extractor")
# ==============================================================================
class Game(Base):
    """
    A supported game that Asset Harvester can extract assets from.
    
    Attributes:
        id (int):               Unique identifier for the game
        name (str):             Human-readable game name (e.g., "Ragnarok Online")
        archive_format (str):   Primary archive extension (e.g., ".grf")
        extractor_module (str): Python module name for extraction (e.g., "grf_extractor")
        description (str):      Optional description of the game
        created_at (datetime):  When this game was added to the system
    """
    __tablename__ = 'games'
    
    # Primary key - auto-incrementing integer
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Game name - must be unique and not empty
    name = Column(String(100), unique=True, nullable=False)
    
    # Archive format - the file extension this game uses (e.g., ".grf", ".vfs")
    archive_format = Column(String(50), nullable=False)
    
    # Extractor module - the Python module that handles this format
    extractor_module = Column(String(100), nullable=False)
    
    # Optional description
    description = Column(Text, nullable=True)
    
    # Timestamp when this game was added
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships - a game can have many servers and vanilla files
    servers = relationship("Server", back_populates="game", cascade="all, delete-orphan")
    vanilla_files = relationship("VanillaFile", back_populates="game", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Game(id={self.id}, name='{self.name}', format='{self.archive_format}')>"


# ==============================================================================
# SERVER MODEL
# ==============================================================================
# Represents a private server. Servers belong to a specific game and can have
# multiple downloaded clients associated with them.
#
# Example:
#   server = Server(game_id=1, name="NovaRO", 
#                   website="https://novaragnarok.com",
#                   status="active")
# ==============================================================================
class Server(Base):
    """
    A private server entry in the registry.
    
    Attributes:
        id (int):           Unique identifier
        game_id (int):      Foreign key to the parent game
        name (str):         Server name (e.g., "NovaRO")
        website (str):      Server's website URL
        download_url (str): Direct link to client download (optional)
        status (str):       Current status: "active", "dead", "unknown"
        has_custom (bool):  Whether server is known to have custom content
        notes (str):        Any additional notes about this server
        created_at:         When this server was added
        updated_at:         Last time this entry was modified
    """
    __tablename__ = 'servers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False)
    name = Column(String(100), nullable=False)
    website = Column(String(255), nullable=True)
    download_url = Column(String(500), nullable=True)
    status = Column(String(20), default='unknown')  # active, dead, unknown
    has_custom = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    game = relationship("Game", back_populates="servers")
    clients = relationship("Client", back_populates="server", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Server(id={self.id}, name='{self.name}', game_id={self.game_id})>"


# ==============================================================================
# CLIENT MODEL
# ==============================================================================
# Represents a downloaded client folder from a private server.
# A client is a specific version/download of a server's game files.
#
# Example:
#   client = Client(server_id=1, path="E:\\Clients\\NovaRO_2025",
#                   extracted=False)
# ==============================================================================
class Client(Base):
    """
    A downloaded client folder from a private server.
    
    Attributes:
        id (int):           Unique identifier
        server_id (int):    Foreign key to the parent server
        path (str):         Local filesystem path to the client folder
        downloaded_at:      When this client was downloaded/added
        extracted (bool):   Whether assets have been extracted from this client
        extracted_at:       When extraction was completed
        total_files (int):  Total number of files in the client
        custom_files (int): Number of files identified as custom content
    """
    __tablename__ = 'clients'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey('servers.id'), nullable=False)
    path = Column(String(500), nullable=False)
    downloaded_at = Column(DateTime, default=datetime.utcnow)
    extracted = Column(Boolean, default=False)
    extracted_at = Column(DateTime, nullable=True)
    total_files = Column(Integer, default=0)
    custom_files = Column(Integer, default=0)
    
    # Relationships
    server = relationship("Server", back_populates="clients")
    assets = relationship("Asset", back_populates="client", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Client(id={self.id}, server_id={self.server_id}, path='{self.path}')>"


# ==============================================================================
# VANILLA FILE MODEL
# ==============================================================================
# Represents a file from the original/vanilla game client.
# These serve as the baseline for comparison - any file that doesn't match
# a vanilla file (or doesn't exist in vanilla) is considered custom content.
#
# Example:
#   vanilla = VanillaFile(game_id=1, path="data\\sprite\\monster.spr",
#                         hash="abc123...", size=12345)
# ==============================================================================
class VanillaFile(Base):
    """
    A baseline file from an original/vanilla game client.
    
    Attributes:
        id (int):           Unique identifier
        game_id (int):      Foreign key to the parent game
        path (str):         Relative path within the game client
        hash_md5 (str):     MD5 hash of the file contents
        hash_sha256 (str):  SHA256 hash for more secure comparison
        size (int):         File size in bytes
        modified_at:        File's last modification timestamp
    """
    __tablename__ = 'vanilla_files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey('games.id'), nullable=False)
    path = Column(String(500), nullable=False)
    hash_md5 = Column(String(32), nullable=False)
    hash_sha256 = Column(String(64), nullable=True)
    size = Column(Integer, nullable=False)
    modified_at = Column(DateTime, nullable=True)
    
    # Relationship
    game = relationship("Game", back_populates="vanilla_files")
    
    def __repr__(self):
        return f"<VanillaFile(game_id={self.game_id}, path='{self.path}')>"


# ==============================================================================
# ASSET TYPE MODEL
# ==============================================================================
# Categories for organizing extracted assets (monsters, items, maps, etc.)
# Each type has associated file extensions to help with auto-categorization.
#
# Example:
#   asset_type = AssetType(name="Textures", 
#                          extensions=".bmp,.tga,.dds,.png",
#                          description="2D texture files")
# ==============================================================================
class AssetType(Base):
    """
    A category for organizing assets.
    
    Attributes:
        id (int):           Unique identifier
        name (str):         Category name (e.g., "Monsters", "Items", "Maps")
        extensions (str):   Comma-separated file extensions for this type
        description (str):  Description of what this category contains
    """
    __tablename__ = 'asset_types'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    extensions = Column(String(200), nullable=True)  # Comma-separated: ".spr,.act"
    description = Column(Text, nullable=True)
    
    # Relationship
    assets = relationship("Asset", back_populates="asset_type")
    
    def __repr__(self):
        return f"<AssetType(id={self.id}, name='{self.name}')>"


# ==============================================================================
# ASSET MODEL
# ==============================================================================
# Represents an extracted asset from a client. Each asset is compared against
# the vanilla baseline and marked with a status indicating whether it's
# identical, modified, or completely new (custom).
#
# Status values:
#   - "identical": Hash matches vanilla file exactly
#   - "modified":  Same path as vanilla but different hash
#   - "new":       Path doesn't exist in vanilla (custom content!)
#   - "unknown":   Not yet compared
# ==============================================================================
class Asset(Base):
    """
    An extracted asset from a client.
    
    Attributes:
        id (int):           Unique identifier
        client_id (int):    Foreign key to the parent client
        asset_type_id (int): Foreign key to the asset type (optional)
        path (str):         Relative path within the client
        hash_md5 (str):     MD5 hash of the file
        size (int):         File size in bytes
        status (str):       Comparison status: identical, modified, new, unknown
        extracted_path (str): Path where the file was extracted to (if extracted)
    """
    __tablename__ = 'assets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    asset_type_id = Column(Integer, ForeignKey('asset_types.id'), nullable=True)
    path = Column(String(500), nullable=False)
    hash_md5 = Column(String(32), nullable=True)
    size = Column(Integer, nullable=True)
    status = Column(String(20), default='unknown')  # identical, modified, new, unknown
    extracted_path = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    client = relationship("Client", back_populates="assets")
    asset_type = relationship("AssetType", back_populates="assets")
    
    def __repr__(self):
        return f"<Asset(id={self.id}, path='{self.path}', status='{self.status}')>"


# ==============================================================================
# DATABASE CLASS
# ==============================================================================
# Main database manager class. Handles connection, session management,
# and provides convenience methods for common operations.
#
# Usage:
#   db = Database("E:\\2026 PROJECT\\AssetHarvester\\data\\harvester.db")
#   db.add_game("Ragnarok Online", ".grf", "grf_extractor")
#   games = db.get_all_games()
# ==============================================================================
class Database:
    """
    Database manager for Asset Harvester.
    
    This class provides a clean interface for interacting with the SQLite
    database. It handles connection management, table creation, and common
    CRUD operations.
    
    Attributes:
        db_path (str): Path to the SQLite database file
        engine: SQLAlchemy engine instance
        Session: SQLAlchemy session factory
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the database connection.
        
        Args:
            db_path: Path to the SQLite database file.
                    The file will be created if it doesn't exist.
        """
        # Store the database path for reference
        self.db_path = db_path
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Create the SQLAlchemy engine
        # The 'sqlite:///' prefix tells SQLAlchemy to use SQLite
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        
        # Create a session factory
        # Sessions are used for all database operations
        self.Session = sessionmaker(bind=self.engine)
        
        # Create all tables if they don't exist
        self._create_tables()
        
        # Insert default data (asset types, initial games)
        self._seed_defaults()
    
    def _create_tables(self):
        """Create all database tables if they don't exist."""
        Base.metadata.create_all(self.engine)
    
    def _seed_defaults(self):
        """Insert default asset types and supported games."""
        session = self.Session()
        try:
            # Default asset types (only add if table is empty)
            if session.query(AssetType).count() == 0:
                default_types = [
                    AssetType(name="Textures", extensions=".bmp,.tga,.dds,.png,.jpg,.jpeg",
                             description="2D texture and image files"),
                    AssetType(name="Models", extensions=".rsm,.zms,.smd,.obj,.fbx",
                             description="3D model files"),
                    AssetType(name="Sprites", extensions=".spr,.act",
                             description="2D sprite animations"),
                    AssetType(name="Audio", extensions=".wav,.mp3,.ogg,.bgm",
                             description="Sound effects and music"),
                    AssetType(name="Maps", extensions=".rsw,.gnd,.gat,.him,.zon",
                             description="Map and terrain data"),
                    AssetType(name="Data", extensions=".txt,.xml,.lua,.yml,.yaml,.json",
                             description="Configuration and data files"),
                    AssetType(name="Effects", extensions=".str,.edf,.eff",
                             description="Visual effect files"),
                    AssetType(name="UI", extensions=".bmp,.png,.xml",
                             description="User interface elements"),
                    AssetType(name="Other", extensions="",
                             description="Uncategorized files")
                ]
                session.add_all(default_types)
            
            # Default games (only add if table is empty)
            if session.query(Game).count() == 0:
                default_games = [
                    Game(name="Ragnarok Online", archive_format=".grf",
                         extractor_module="grf_extractor",
                         description="Gravity's classic MMORPG - GRF/GPF/THOR archives"),
                    Game(name="ROSE Online", archive_format=".vfs",
                         extractor_module="vfs_extractor",
                         description="Rush On Seven Episodes - VFS/IDX archives"),
                    Game(name="RF Online", archive_format=".pak",
                         extractor_module="rf_extractor",
                         description="Rising Force Online - PAK/DAT/EDF archives"),
                ]
                session.add_all(default_games)
            
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    # ==========================================================================
    # GAME OPERATIONS
    # ==========================================================================
    
    def add_game(self, name: str, archive_format: str, extractor_module: str,
                 description: str = None) -> Game:
        """
        Add a new supported game to the database.
        
        Args:
            name: Human-readable game name
            archive_format: Primary archive extension (e.g., ".grf")
            extractor_module: Python module name for extraction
            description: Optional description
            
        Returns:
            The created Game object
        """
        session = self.Session()
        try:
            game = Game(
                name=name,
                archive_format=archive_format,
                extractor_module=extractor_module,
                description=description
            )
            session.add(game)
            session.commit()
            session.refresh(game)
            return game
        finally:
            session.close()
    
    def get_all_games(self) -> List[Game]:
        """Get all supported games."""
        session = self.Session()
        try:
            return session.query(Game).all()
        finally:
            session.close()
    
    def get_game_by_name(self, name: str) -> Optional[Game]:
        """Get a game by its name."""
        session = self.Session()
        try:
            return session.query(Game).filter(Game.name == name).first()
        finally:
            session.close()
    
    # ==========================================================================
    # SERVER OPERATIONS
    # ==========================================================================
    
    def add_server(self, game_id: int, name: str, website: str = None,
                   download_url: str = None, notes: str = None) -> Server:
        """
        Add a new private server to the registry.
        
        Args:
            game_id: ID of the parent game
            name: Server name
            website: Server's website URL
            download_url: Direct link to client download
            notes: Additional notes
            
        Returns:
            The created Server object
        """
        session = self.Session()
        try:
            server = Server(
                game_id=game_id,
                name=name,
                website=website,
                download_url=download_url,
                notes=notes
            )
            session.add(server)
            session.commit()
            session.refresh(server)
            return server
        finally:
            session.close()
    
    def get_servers_by_game(self, game_id: int) -> List[Server]:
        """Get all servers for a specific game."""
        session = self.Session()
        try:
            return session.query(Server).filter(Server.game_id == game_id).all()
        finally:
            session.close()
    
    def get_all_servers(self) -> List[Server]:
        """Get all registered servers."""
        session = self.Session()
        try:
            return session.query(Server).all()
        finally:
            session.close()
    
    # ==========================================================================
    # CLIENT OPERATIONS
    # ==========================================================================
    
    def add_client(self, server_id: int, path: str) -> Client:
        """
        Add a downloaded client folder.
        
        Args:
            server_id: ID of the parent server
            path: Local filesystem path to the client folder
            
        Returns:
            The created Client object
        """
        session = self.Session()
        try:
            client = Client(
                server_id=server_id,
                path=path
            )
            session.add(client)
            session.commit()
            session.refresh(client)
            return client
        finally:
            session.close()
    
    def update_client_extraction(self, client_id: int, total_files: int,
                                  custom_files: int):
        """Update client after extraction is complete."""
        session = self.Session()
        try:
            client = session.query(Client).get(client_id)
            if client:
                client.extracted = True
                client.extracted_at = datetime.utcnow()
                client.total_files = total_files
                client.custom_files = custom_files
                session.commit()
        finally:
            session.close()
    
    # ==========================================================================
    # VANILLA FILE OPERATIONS
    # ==========================================================================
    
    def add_vanilla_file(self, game_id: int, path: str, hash_md5: str,
                         size: int, hash_sha256: str = None) -> VanillaFile:
        """Add a vanilla baseline file."""
        session = self.Session()
        try:
            vanilla = VanillaFile(
                game_id=game_id,
                path=path,
                hash_md5=hash_md5,
                hash_sha256=hash_sha256,
                size=size
            )
            session.add(vanilla)
            session.commit()
            session.refresh(vanilla)
            return vanilla
        finally:
            session.close()
    
    def get_vanilla_file(self, game_id: int, path: str) -> Optional[VanillaFile]:
        """Get a vanilla file by game and path."""
        session = self.Session()
        try:
            return session.query(VanillaFile).filter(
                VanillaFile.game_id == game_id,
                VanillaFile.path == path
            ).first()
        finally:
            session.close()
    
    def get_vanilla_hash(self, game_id: int, path: str) -> Optional[str]:
        """Get just the MD5 hash for a vanilla file."""
        vanilla = self.get_vanilla_file(game_id, path)
        return vanilla.hash_md5 if vanilla else None
    
    # ==========================================================================
    # ASSET OPERATIONS
    # ==========================================================================
    
    def add_asset(self, client_id: int, path: str, hash_md5: str = None,
                  size: int = None, status: str = 'unknown') -> Asset:
        """Add an extracted asset."""
        session = self.Session()
        try:
            asset = Asset(
                client_id=client_id,
                path=path,
                hash_md5=hash_md5,
                size=size,
                status=status
            )
            session.add(asset)
            session.commit()
            session.refresh(asset)
            return asset
        finally:
            session.close()
    
    def add_assets_bulk(self, assets: List[dict]):
        """Add multiple assets in a single transaction (much faster)."""
        session = self.Session()
        try:
            session.bulk_insert_mappings(Asset, assets)
            session.commit()
        finally:
            session.close()
    
    def get_custom_assets(self, client_id: int) -> List[Asset]:
        """Get all custom (new or modified) assets for a client."""
        session = self.Session()
        try:
            return session.query(Asset).filter(
                Asset.client_id == client_id,
                Asset.status.in_(['new', 'modified'])
            ).all()
        finally:
            session.close()
    
    def get_assets_by_status(self, client_id: int, status: str) -> List[Asset]:
        """Get assets by their comparison status."""
        session = self.Session()
        try:
            return session.query(Asset).filter(
                Asset.client_id == client_id,
                Asset.status == status
            ).all()
        finally:
            session.close()
    
    # ==========================================================================
    # STATISTICS
    # ==========================================================================
    
    def get_stats(self) -> dict:
        """Get overall statistics about the database."""
        session = self.Session()
        try:
            return {
                'games': session.query(Game).count(),
                'servers': session.query(Server).count(),
                'clients': session.query(Client).count(),
                'vanilla_files': session.query(VanillaFile).count(),
                'total_assets': session.query(Asset).count(),
                'custom_assets': session.query(Asset).filter(
                    Asset.status.in_(['new', 'modified'])
                ).count()
            }
        finally:
            session.close()
