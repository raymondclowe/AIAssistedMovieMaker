"""Database module for AI-Assisted Movie Maker.

This module provides the Database class for managing projects, tabs, blocks,
assets, history, and dependencies using SQLAlchemy for thread safety.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool


class Database:
    """SQLAlchemy-based database manager for movie projects.
    
    Uses scoped_session for thread-safe database access.
    """

    def __init__(self, db_path: Path):
        """Initialize database connection with SQLAlchemy.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        # Create engine with QueuePool for connection pooling
        # Each thread will get its own connection from the pool
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False
        )
        
        # Enable WAL mode and foreign keys for better concurrent access
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        
        # Create a scoped session factory for thread-safe sessions
        session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(session_factory)
        self._init_schema()
    
    @contextmanager
    def get_session(self):
        """Get a thread-safe database session.
        
        Yields:
            A SQLAlchemy session that will be automatically committed or rolled back.
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            self.Session.remove()

    def _init_schema(self):
        """Initialize database schema."""
        with self.get_session() as session:
            # Projects table
            session.execute(text("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                root_path TEXT NOT NULL
            )
            """))

            # Tabs table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS tabs (
                    id INTEGER PRIMARY KEY,
                    project_id INTEGER REFERENCES projects(id),
                    name TEXT NOT NULL,
                    position INTEGER NOT NULL
                )
            """))

            # Blocks table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS blocks (
                    id INTEGER PRIMARY KEY,
                    tab_id INTEGER REFERENCES tabs(id),
                    parent_id INTEGER REFERENCES blocks(id),
                    type TEXT NOT NULL,
                    content TEXT,
                    tags TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # Assets table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS assets (
                    id INTEGER PRIMARY KEY,
                    project_id INTEGER REFERENCES projects(id),
                    hash TEXT NOT NULL UNIQUE,
                    path TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    meta_json TEXT
                )
            """))

            # Block-Asset linking table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS block_assets (
                    block_id INTEGER REFERENCES blocks(id),
                    asset_id INTEGER REFERENCES assets(id),
                    role TEXT,
                    PRIMARY KEY (block_id, asset_id)
                )
            """))

            # History table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY,
                    block_id INTEGER REFERENCES blocks(id),
                    action TEXT NOT NULL,
                    payload TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))

            # Dependencies table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS dependencies (
                    src_block_id INTEGER REFERENCES blocks(id),
                    dst_block_id INTEGER REFERENCES blocks(id),
                    type TEXT,
                    PRIMARY KEY (src_block_id, dst_block_id)
                )
            """))

    def create_project(self, name: str, root_path: str) -> int:
        """Create a new project.

        Args:
            name: Project name.
            root_path: Root path for project assets.

        Returns:
            Project ID.
        """
        with self.get_session() as session:
            result = session.execute(
                text("INSERT INTO projects (name, root_path) VALUES (:name, :root_path)"),
                {"name": name, "root_path": root_path}
            )
            return result.lastrowid

    def get_project(self, project_id: int) -> Optional[dict]:
        """Get project by ID.

        Args:
            project_id: Project ID.

        Returns:
            Project dict or None.
        """
        with self.get_session() as session:
            result = session.execute(
                text("SELECT * FROM projects WHERE id = :id"),
                {"id": project_id}
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None

    def get_all_projects(self) -> list:
        """Get all projects.

        Returns:
            List of project dicts.
        """
        with self.get_session() as session:
            result = session.execute(
                text("SELECT * FROM projects ORDER BY created_at DESC")
            )
            return [dict(row._mapping) for row in result.fetchall()]

    def create_tab(self, project_id: int, name: str, position: int) -> int:
        """Create a new tab for a project.

        Args:
            project_id: Project ID.
            name: Tab name.
            position: Tab position.

        Returns:
            Tab ID.
        """
        with self.get_session() as session:
            result = session.execute(
                text("INSERT INTO tabs (project_id, name, position) VALUES (:project_id, :name, :position)"),
                {"project_id": project_id, "name": name, "position": position}
            )
            return result.lastrowid

    def get_tabs(self, project_id: int) -> list:
        """Get all tabs for a project.

        Args:
            project_id: Project ID.

        Returns:
            List of tab dicts.
        """
        with self.get_session() as session:
            result = session.execute(
                text("SELECT * FROM tabs WHERE project_id = :project_id ORDER BY position"),
                {"project_id": project_id}
            )
            return [dict(row._mapping) for row in result.fetchall()]

    def add_block(
        self,
        tab_id: int,
        block_type: str,
        content: str = "",
        tags: Optional[list] = None,
        parent_id: Optional[int] = None
    ) -> int:
        """Add a new block.

        Args:
            tab_id: Tab ID.
            block_type: Block type (e.g., 'scene_heading', 'dialogue', 'note').
            content: Block content.
            tags: List of tags.
            parent_id: Parent block ID (for hierarchical blocks).

        Returns:
            Block ID.
        """
        with self.get_session() as session:
            tags_json = json.dumps(tags) if tags else None
            result = session.execute(
                text("""INSERT INTO blocks (tab_id, parent_id, type, content, tags)
                   VALUES (:tab_id, :parent_id, :type, :content, :tags)"""),
                {"tab_id": tab_id, "parent_id": parent_id, "type": block_type,
                 "content": content, "tags": tags_json}
            )
            block_id = result.lastrowid

            # Record in history
            self._record_history_in_session(session, block_id, "create", {"content": content, "tags": tags})
            return block_id

    def get_block(self, block_id: int) -> Optional[dict]:
        """Get block by ID.

        Args:
            block_id: Block ID.

        Returns:
            Block dict or None.
        """
        with self.get_session() as session:
            result = session.execute(
                text("SELECT * FROM blocks WHERE id = :id"),
                {"id": block_id}
            )
            row = result.fetchone()
            if row:
                block = dict(row._mapping)
                block["tags"] = json.loads(block["tags"]) if block["tags"] else []
                return block
            return None

    def get_blocks_by_tab(self, tab_id: int) -> list:
        """Get all blocks for a tab.

        Args:
            tab_id: Tab ID.

        Returns:
            List of block dicts.
        """
        with self.get_session() as session:
            result = session.execute(
                text("SELECT * FROM blocks WHERE tab_id = :tab_id ORDER BY created_at"),
                {"tab_id": tab_id}
            )
            blocks = []
            for row in result.fetchall():
                block = dict(row._mapping)
                block["tags"] = json.loads(block["tags"]) if block["tags"] else []
                blocks.append(block)
            return blocks

    def update_block(
        self,
        block_id: int,
        content: Optional[str] = None,
        tags: Optional[list] = None
    ) -> bool:
        """Update a block.

        Args:
            block_id: Block ID.
            content: New content (optional).
            tags: New tags (optional).

        Returns:
            True if updated successfully.
        """
        # Get current block first (outside transaction for read)
        old_block = self.get_block(block_id)
        if not old_block:
            return False

        with self.get_session() as session:
            # Use explicit UPDATE queries to avoid dynamic SQL construction
            updated_at = datetime.now().isoformat()

            if content is not None and tags is not None:
                session.execute(
                    text("""UPDATE blocks
                       SET content = :content, tags = :tags, version = version + 1, updated_at = :updated_at
                       WHERE id = :id"""),
                    {"content": content, "tags": json.dumps(tags), "updated_at": updated_at, "id": block_id}
                )
            elif content is not None:
                session.execute(
                    text("""UPDATE blocks
                       SET content = :content, version = version + 1, updated_at = :updated_at
                       WHERE id = :id"""),
                    {"content": content, "updated_at": updated_at, "id": block_id}
                )
            elif tags is not None:
                session.execute(
                    text("""UPDATE blocks
                       SET tags = :tags, version = version + 1, updated_at = :updated_at
                       WHERE id = :id"""),
                    {"tags": json.dumps(tags), "updated_at": updated_at, "id": block_id}
                )
            else:
                return False

            # Record in history
            self._record_history_in_session(session, block_id, "edit", {
                "old_content": old_block["content"],
                "new_content": content,
                "old_tags": old_block["tags"],
                "new_tags": tags
            })

            return True

    def delete_block(self, block_id: int) -> bool:
        """Delete a block.

        Args:
            block_id: Block ID.

        Returns:
            True if deleted successfully.
        """
        # Get block for history (outside transaction for read)
        block = self.get_block(block_id)
        
        with self.get_session() as session:
            if block:
                self._record_history_in_session(session, block_id, "delete", {"content": block["content"]})

            # Delete associated data
            session.execute(text("DELETE FROM block_assets WHERE block_id = :id"), {"id": block_id})
            session.execute(
                text("DELETE FROM dependencies WHERE src_block_id = :id OR dst_block_id = :id"),
                {"id": block_id}
            )
            result = session.execute(text("DELETE FROM blocks WHERE id = :id"), {"id": block_id})
            return result.rowcount > 0

    def link_block_asset(self, block_id: int, asset_id: int, role: str = "preview"):
        """Link an asset to a block.

        Args:
            block_id: Block ID.
            asset_id: Asset ID.
            role: Asset role (e.g., 'preview', 'full_clip', 'reference').
        """
        with self.get_session() as session:
            session.execute(
                text("INSERT OR REPLACE INTO block_assets (block_id, asset_id, role) VALUES (:block_id, :asset_id, :role)"),
                {"block_id": block_id, "asset_id": asset_id, "role": role}
            )

    def get_block_assets(self, block_id: int) -> list:
        """Get all assets linked to a block.

        Args:
            block_id: Block ID.

        Returns:
            List of asset dicts with role.
        """
        with self.get_session() as session:
            result = session.execute(
                text("""
                SELECT a.*, ba.role FROM assets a
                JOIN block_assets ba ON a.id = ba.asset_id
                WHERE ba.block_id = :block_id
            """),
                {"block_id": block_id}
            )
            return [dict(row._mapping) for row in result.fetchall()]

    def add_dependency(self, src_block_id: int, dst_block_id: int, dep_type: str):
        """Add a dependency between blocks.

        Args:
            src_block_id: Source block ID.
            dst_block_id: Destination block ID.
            dep_type: Dependency type.
        """
        with self.get_session() as session:
            session.execute(
                text("INSERT OR REPLACE INTO dependencies (src_block_id, dst_block_id, type) VALUES (:src, :dst, :type)"),
                {"src": src_block_id, "dst": dst_block_id, "type": dep_type}
            )

    def get_dependencies(self, src_block_id: int) -> list:
        """Get all dependencies from a source block.

        Args:
            src_block_id: Source block ID.

        Returns:
            List of dependency dicts.
        """
        with self.get_session() as session:
            result = session.execute(
                text("SELECT * FROM dependencies WHERE src_block_id = :src"),
                {"src": src_block_id}
            )
            return [dict(row._mapping) for row in result.fetchall()]

    def get_reverse_dependencies(self, dst_block_id: int) -> list:
        """Get all dependencies pointing to a destination block.

        Args:
            dst_block_id: Destination block ID.

        Returns:
            List of dependency dicts where this block is the destination.
        """
        with self.get_session() as session:
            result = session.execute(
                text("SELECT * FROM dependencies WHERE dst_block_id = :dst"),
                {"dst": dst_block_id}
            )
            return [dict(row._mapping) for row in result.fetchall()]

    def get_history(self, block_id: int) -> list:
        """Get history for a block.

        Args:
            block_id: Block ID.

        Returns:
            List of history entries.
        """
        with self.get_session() as session:
            result = session.execute(
                text("SELECT * FROM history WHERE block_id = :block_id ORDER BY timestamp DESC"),
                {"block_id": block_id}
            )
            history = []
            for row in result.fetchall():
                entry = dict(row._mapping)
                entry["payload"] = json.loads(entry["payload"]) if entry["payload"] else {}
                history.append(entry)
            return history

    def _record_history_entry(self, block_id: int, action: str, payload: dict):
        """Record an action in history (public method for external use).

        Args:
            block_id: Block ID.
            action: Action type (e.g., "create", "edit", "model_used").
            payload: Action payload as a dict.
        """
        with self.get_session() as session:
            session.execute(
                text("INSERT INTO history (block_id, action, payload) VALUES (:block_id, :action, :payload)"),
                {"block_id": block_id, "action": action, "payload": json.dumps(payload)}
            )

    def _record_history_in_session(self, session, block_id: int, action: str, payload: dict):
        """Record an action in history within an existing session.

        Args:
            session: SQLAlchemy session.
            block_id: Block ID.
            action: Action type.
            payload: Action payload.
        """
        session.execute(
            text("INSERT INTO history (block_id, action, payload) VALUES (:block_id, :action, :payload)"),
            {"block_id": block_id, "action": action, "payload": json.dumps(payload)}
        )

    def invalidate_downstream(self, src_block_id: int):
        """Mark downstream blocks as needing regeneration.

        Args:
            src_block_id: Source block ID.
        """
        with self.get_session() as session:
            # Get dependencies in same session
            result = session.execute(
                text("SELECT * FROM dependencies WHERE src_block_id = :src"),
                {"src": src_block_id}
            )
            deps = [dict(row._mapping) for row in result.fetchall()]
            
            for dep in deps:
                dst_block_id = dep["dst_block_id"]
                # Get block in same session
                result = session.execute(
                    text("SELECT * FROM blocks WHERE id = :id"),
                    {"id": dst_block_id}
                )
                row = result.fetchone()
                if row:
                    block = dict(row._mapping)
                    tags = json.loads(block["tags"]) if block["tags"] else []
                    if "needs_regen" not in tags:
                        tags.append("needs_regen")
                        updated_at = datetime.now().isoformat()
                        session.execute(
                            text("""UPDATE blocks
                               SET tags = :tags, version = version + 1, updated_at = :updated_at
                               WHERE id = :id"""),
                            {"tags": json.dumps(tags), "updated_at": updated_at, "id": dst_block_id}
                        )

    def close(self):
        """Close database connection."""
        self.Session.remove()
        self.engine.dispose()
