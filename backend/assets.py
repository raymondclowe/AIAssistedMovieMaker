"""Asset management module for AI-Assisted Movie Maker.

This module provides the AssetManager class for storing and managing
binary assets (images, videos, audio) with hash-based deduplication.
"""

import hashlib
import mimetypes
import json
import sqlite3
from pathlib import Path
from typing import Optional


class AssetManager:
    """Manages binary assets with hash-based storage."""

    def __init__(self, project_root: Path, db_conn: sqlite3.Connection):
        """Initialize asset manager.

        Args:
            project_root: Root path of the project.
            db_conn: Database connection.
        """
        self.project_root = project_root
        self.assets_dir = project_root / "assets"
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.conn = db_conn

    def store_asset(
        self,
        src_file: Path,
        project_id: int,
        meta: Optional[dict] = None
    ) -> int:
        """Store an asset file with hash-based deduplication.

        Args:
            src_file: Source file path.
            project_id: Project ID.
            meta: Optional metadata dictionary.

        Returns:
            Asset ID.
        """
        # Read and hash the file
        data = src_file.read_bytes()
        file_hash = hashlib.sha256(data).hexdigest()

        # Check if asset already exists
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM assets WHERE hash = ?", (file_hash,))
        existing = cursor.fetchone()
        if existing:
            return existing[0]

        # Copy file to assets directory
        dest = self.assets_dir / f"{file_hash}{src_file.suffix}"
        if not dest.exists():
            dest.write_bytes(data)

        # Determine MIME type
        mime_type = mimetypes.guess_type(str(src_file))[0] or "application/octet-stream"

        # Insert metadata row
        cursor.execute(
            """INSERT INTO assets (project_id, hash, path, mime_type, size_bytes, meta_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                project_id,
                file_hash,
                str(dest.relative_to(self.project_root)),
                mime_type,
                len(data),
                json.dumps(meta) if meta else None
            )
        )
        self.conn.commit()
        return cursor.lastrowid

    def store_asset_from_bytes(
        self,
        data: bytes,
        filename: str,
        project_id: int,
        meta: Optional[dict] = None
    ) -> int:
        """Store an asset from bytes with hash-based deduplication.

        Args:
            data: File bytes.
            filename: Original filename (for extension).
            project_id: Project ID.
            meta: Optional metadata dictionary.

        Returns:
            Asset ID.
        
        Raises:
            IOError: If file operations fail.
            sqlite3.Error: If database operations fail.
        """
        import sqlite3

        # Hash the data
        file_hash = hashlib.sha256(data).hexdigest()

        # Check if asset already exists
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM assets WHERE hash = ?", (file_hash,))
        existing = cursor.fetchone()
        if existing:
            return existing[0]

        # Get file extension
        suffix = Path(filename).suffix or ".bin"

        # Write file to assets directory
        dest = self.assets_dir / f"{file_hash}{suffix}"
        try:
            if not dest.exists():
                dest.write_bytes(data)
        except OSError as e:
            raise IOError(f"Failed to write asset file: {e}")

        # Determine MIME type
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        # Insert metadata row with conflict handling for race conditions
        try:
            cursor.execute(
                """INSERT INTO assets (project_id, hash, path, mime_type, size_bytes, meta_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    project_id,
                    file_hash,
                    str(dest.relative_to(self.project_root)),
                    mime_type,
                    len(data),
                    json.dumps(meta) if meta else None
                )
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Race condition: another process inserted the same hash
            # Return the existing asset ID
            cursor.execute("SELECT id FROM assets WHERE hash = ?", (file_hash,))
            existing = cursor.fetchone()
            if existing:
                return existing[0]
            raise  # Re-raise if we still can't find it

    def store_asset_from_file(
        self,
        file_obj,
        filename: str,
        project_id: int,
        meta: Optional[dict] = None,
        chunk_size: int = 8192
    ) -> int:
        """Store an asset from a file-like object with streaming and hash-based deduplication.

        This method reads the file in chunks to avoid loading large files entirely into memory.

        Args:
            file_obj: File-like object (e.g., Streamlit UploadedFile).
            filename: Original filename (for extension).
            project_id: Project ID.
            meta: Optional metadata dictionary.
            chunk_size: Size of chunks to read at a time (default 8KB).

        Returns:
            Asset ID.
        
        Raises:
            IOError: If file operations fail.
            sqlite3.Error: If database operations fail.
        """
        import tempfile
        import shutil
        import sqlite3

        # Get file extension
        suffix = Path(filename).suffix or ".bin"

        hasher = hashlib.sha256()
        total_size = 0
        tmp_path = None

        try:
            # Stream the file to a temporary location while computing hash
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_path = Path(tmp_file.name)
                while True:
                    chunk = file_obj.read(chunk_size)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    tmp_file.write(chunk)
                    total_size += len(chunk)

            file_hash = hasher.hexdigest()

            # Check if asset already exists
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM assets WHERE hash = ?", (file_hash,))
            existing = cursor.fetchone()
            if existing:
                # Clean up temp file and return existing asset
                if tmp_path and tmp_path.exists():
                    tmp_path.unlink()
                return existing[0]

            # Move temp file to assets directory
            dest = self.assets_dir / f"{file_hash}{suffix}"
            try:
                if not dest.exists():
                    shutil.move(str(tmp_path), str(dest))
                    tmp_path = None  # Mark as moved
                else:
                    # File already exists (race condition), just use existing
                    if tmp_path and tmp_path.exists():
                        tmp_path.unlink()
                    tmp_path = None
            except (OSError, shutil.Error) as e:
                raise IOError(f"Failed to move asset file: {e}")

            # Determine MIME type
            mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

            # Insert metadata row with conflict handling for race conditions
            try:
                cursor.execute(
                    """INSERT INTO assets (project_id, hash, path, mime_type, size_bytes, meta_json)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        project_id,
                        file_hash,
                        str(dest.relative_to(self.project_root)),
                        mime_type,
                        total_size,
                        json.dumps(meta) if meta else None
                    )
                )
                self.conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Race condition: another process inserted the same hash
                # Return the existing asset ID
                cursor.execute("SELECT id FROM assets WHERE hash = ?", (file_hash,))
                existing = cursor.fetchone()
                if existing:
                    return existing[0]
                raise  # Re-raise if we still can't find it

        except Exception:
            # Clean up temp file on any error
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass  # Best effort cleanup
            raise

    def get_asset(self, asset_id: int) -> Optional[dict]:
        """Get asset metadata by ID.

        Args:
            asset_id: Asset ID.

        Returns:
            Asset dict or None.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
        row = cursor.fetchone()
        if row:
            asset = dict(row)
            asset["meta"] = json.loads(asset["meta_json"]) if asset.get("meta_json") else {}
            asset["full_path"] = self.project_root / asset["path"]
            return asset
        return None

    def get_asset_by_hash(self, file_hash: str) -> Optional[dict]:
        """Get asset metadata by hash.

        Args:
            file_hash: SHA-256 hash of the file.

        Returns:
            Asset dict or None.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM assets WHERE hash = ?", (file_hash,))
        row = cursor.fetchone()
        if row:
            asset = dict(row)
            asset["meta"] = json.loads(asset["meta_json"]) if asset.get("meta_json") else {}
            asset["full_path"] = self.project_root / asset["path"]
            return asset
        return None

    def get_all_assets(self, project_id: int) -> list:
        """Get all assets for a project.

        Args:
            project_id: Project ID.

        Returns:
            List of asset dicts.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM assets WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,)
        )
        assets = []
        for row in cursor.fetchall():
            asset = dict(row)
            asset["meta"] = json.loads(asset["meta_json"]) if asset.get("meta_json") else {}
            asset["full_path"] = self.project_root / asset["path"]
            assets.append(asset)
        return assets

    def delete_asset(self, asset_id: int) -> bool:
        """Delete an asset.

        Args:
            asset_id: Asset ID.

        Returns:
            True if deleted successfully.
        """
        cursor = self.conn.cursor()

        # Get asset info
        asset = self.get_asset(asset_id)
        if not asset:
            return False

        # Remove file if it exists
        full_path = self.project_root / asset["path"]
        if full_path.exists():
            full_path.unlink()

        # Delete from database
        cursor.execute("DELETE FROM block_assets WHERE asset_id = ?", (asset_id,))
        cursor.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        self.conn.commit()
        return True

    def search_assets_by_tag(self, project_id: int, tag: str) -> list:
        """Search assets by tag in metadata.

        Args:
            project_id: Project ID.
            tag: Tag to search for.

        Returns:
            List of matching asset dicts.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT * FROM assets
               WHERE project_id = ?
                 AND EXISTS (
                     SELECT 1 FROM json_each(assets.meta_json, '$.tags')
                     WHERE value = ?
                 )
               ORDER BY created_at DESC""",
            (project_id, tag)
        )
        assets = []
        for row in cursor.fetchall():
            asset = dict(row)
            asset["meta"] = json.loads(asset["meta_json"]) if asset.get("meta_json") else {}
            asset["full_path"] = self.project_root / asset["path"]
            assets.append(asset)
        return assets
