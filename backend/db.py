"""Database module for AI-Assisted Movie Maker.

This module provides the Database class for managing projects, tabs, blocks,
assets, history, and dependencies using SQLite.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class Database:
    """SQLite database manager for movie projects."""

    def __init__(self, db_path: Path):
        """Initialize database connection.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Projects table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                root_path TEXT NOT NULL
            )
        """)

        # Tabs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tabs (
                id INTEGER PRIMARY KEY,
                project_id INTEGER REFERENCES projects(id),
                name TEXT NOT NULL,
                position INTEGER NOT NULL
            )
        """)

        # Blocks table
        cursor.execute("""
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
        """)

        # Assets table
        cursor.execute("""
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
        """)

        # Block-Asset linking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS block_assets (
                block_id INTEGER REFERENCES blocks(id),
                asset_id INTEGER REFERENCES assets(id),
                role TEXT,
                PRIMARY KEY (block_id, asset_id)
            )
        """)

        # History table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY,
                block_id INTEGER REFERENCES blocks(id),
                action TEXT NOT NULL,
                payload TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Dependencies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dependencies (
                src_block_id INTEGER REFERENCES blocks(id),
                dst_block_id INTEGER REFERENCES blocks(id),
                type TEXT,
                PRIMARY KEY (src_block_id, dst_block_id)
            )
        """)

        self.conn.commit()

    def create_project(self, name: str, root_path: str) -> int:
        """Create a new project.

        Args:
            name: Project name.
            root_path: Root path for project assets.

        Returns:
            Project ID.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO projects (name, root_path) VALUES (?, ?)",
            (name, root_path)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_project(self, project_id: int) -> Optional[dict]:
        """Get project by ID.

        Args:
            project_id: Project ID.

        Returns:
            Project dict or None.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_projects(self) -> list:
        """Get all projects.

        Returns:
            List of project dicts.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

    def create_tab(self, project_id: int, name: str, position: int) -> int:
        """Create a new tab for a project.

        Args:
            project_id: Project ID.
            name: Tab name.
            position: Tab position.

        Returns:
            Tab ID.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO tabs (project_id, name, position) VALUES (?, ?, ?)",
            (project_id, name, position)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_tabs(self, project_id: int) -> list:
        """Get all tabs for a project.

        Args:
            project_id: Project ID.

        Returns:
            List of tab dicts.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM tabs WHERE project_id = ? ORDER BY position",
            (project_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

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
        cursor = self.conn.cursor()
        tags_json = json.dumps(tags) if tags else None
        cursor.execute(
            """INSERT INTO blocks (tab_id, parent_id, type, content, tags)
               VALUES (?, ?, ?, ?, ?)""",
            (tab_id, parent_id, block_type, content, tags_json)
        )
        block_id = cursor.lastrowid

        # Record in history
        self._record_history(block_id, "create", {"content": content, "tags": tags})
        self.conn.commit()
        return block_id

    def get_block(self, block_id: int) -> Optional[dict]:
        """Get block by ID.

        Args:
            block_id: Block ID.

        Returns:
            Block dict or None.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM blocks WHERE id = ?", (block_id,))
        row = cursor.fetchone()
        if row:
            block = dict(row)
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
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM blocks WHERE tab_id = ? ORDER BY created_at",
            (tab_id,)
        )
        blocks = []
        for row in cursor.fetchall():
            block = dict(row)
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
        cursor = self.conn.cursor()

        # Get current block
        old_block = self.get_block(block_id)
        if not old_block:
            return False

        # Use explicit UPDATE queries to avoid dynamic SQL construction
        updated_at = datetime.now().isoformat()

        if content is not None and tags is not None:
            cursor.execute(
                """UPDATE blocks
                   SET content = ?, tags = ?, version = version + 1, updated_at = ?
                   WHERE id = ?""",
                (content, json.dumps(tags), updated_at, block_id)
            )
        elif content is not None:
            cursor.execute(
                """UPDATE blocks
                   SET content = ?, version = version + 1, updated_at = ?
                   WHERE id = ?""",
                (content, updated_at, block_id)
            )
        elif tags is not None:
            cursor.execute(
                """UPDATE blocks
                   SET tags = ?, version = version + 1, updated_at = ?
                   WHERE id = ?""",
                (json.dumps(tags), updated_at, block_id)
            )
        else:
            return False

        # Record in history
        self._record_history(block_id, "edit", {
            "old_content": old_block["content"],
            "new_content": content,
            "old_tags": old_block["tags"],
            "new_tags": tags
        })

        self.conn.commit()
        return True

    def delete_block(self, block_id: int) -> bool:
        """Delete a block.

        Args:
            block_id: Block ID.

        Returns:
            True if deleted successfully.
        """
        cursor = self.conn.cursor()

        # Record deletion in history
        block = self.get_block(block_id)
        if block:
            self._record_history(block_id, "delete", {"content": block["content"]})

        # Delete associated data
        cursor.execute("DELETE FROM block_assets WHERE block_id = ?", (block_id,))
        cursor.execute("DELETE FROM dependencies WHERE src_block_id = ? OR dst_block_id = ?",
                       (block_id, block_id))
        cursor.execute("DELETE FROM blocks WHERE id = ?", (block_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def link_block_asset(self, block_id: int, asset_id: int, role: str = "preview"):
        """Link an asset to a block.

        Args:
            block_id: Block ID.
            asset_id: Asset ID.
            role: Asset role (e.g., 'preview', 'full_clip', 'reference').
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO block_assets (block_id, asset_id, role) VALUES (?, ?, ?)",
            (block_id, asset_id, role)
        )
        self.conn.commit()

    def get_block_assets(self, block_id: int) -> list:
        """Get all assets linked to a block.

        Args:
            block_id: Block ID.

        Returns:
            List of asset dicts with role.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT a.*, ba.role FROM assets a
            JOIN block_assets ba ON a.id = ba.asset_id
            WHERE ba.block_id = ?
        """, (block_id,))
        return [dict(row) for row in cursor.fetchall()]

    def add_dependency(self, src_block_id: int, dst_block_id: int, dep_type: str):
        """Add a dependency between blocks.

        Args:
            src_block_id: Source block ID.
            dst_block_id: Destination block ID.
            dep_type: Dependency type.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO dependencies (src_block_id, dst_block_id, type) VALUES (?, ?, ?)",
            (src_block_id, dst_block_id, dep_type)
        )
        self.conn.commit()

    def get_dependencies(self, src_block_id: int) -> list:
        """Get all dependencies from a source block.

        Args:
            src_block_id: Source block ID.

        Returns:
            List of dependency dicts.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM dependencies WHERE src_block_id = ?",
            (src_block_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_history(self, block_id: int) -> list:
        """Get history for a block.

        Args:
            block_id: Block ID.

        Returns:
            List of history entries.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM history WHERE block_id = ? ORDER BY timestamp DESC",
            (block_id,)
        )
        history = []
        for row in cursor.fetchall():
            entry = dict(row)
            entry["payload"] = json.loads(entry["payload"]) if entry["payload"] else {}
            history.append(entry)
        return history

    def _record_history(self, block_id: int, action: str, payload: dict):
        """Record an action in history.

        Args:
            block_id: Block ID.
            action: Action type.
            payload: Action payload.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO history (block_id, action, payload) VALUES (?, ?, ?)",
            (block_id, action, json.dumps(payload))
        )

    def invalidate_downstream(self, src_block_id: int):
        """Mark downstream blocks as needing regeneration.

        Args:
            src_block_id: Source block ID.
        """
        deps = self.get_dependencies(src_block_id)
        for dep in deps:
            block = self.get_block(dep["dst_block_id"])
            if block:
                tags = block.get("tags", [])
                if "needs_regen" not in tags:
                    tags.append("needs_regen")
                    self.update_block(dep["dst_block_id"], tags=tags)

    def close(self):
        """Close database connection."""
        self.conn.close()
