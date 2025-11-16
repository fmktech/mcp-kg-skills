"""SQLite database implementation for MCP Knowledge Graph Skills.

This is a lightweight alternative to Neo4j for testing and development.
It stores the graph structure in relational tables.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from ..exceptions import (
    CircularDependencyError,
    DatabaseConnectionError,
    InvalidQueryError,
    NodeAlreadyExistsError,
    NodeNotFoundError,
)
from .abstract import DatabaseInterface

logger = logging.getLogger(__name__)


class SQLiteDatabase(DatabaseInterface):
    """SQLite implementation of the database interface.

    This adapter stores graph data in SQLite tables:
    - nodes: All node types with JSON properties
    - relationships: Edges between nodes
    - Provides graph query capabilities via SQL
    """

    def __init__(self, db_path: str | Path = ":memory:"):
        """Initialize SQLite database connection.

        Args:
            db_path: Path to SQLite database file, or ":memory:" for in-memory database
        """
        self.db_path = str(db_path) if db_path != ":memory:" else ":memory:"
        self.connection: sqlite3.Connection | None = None

    async def connect(self) -> None:
        """Establish connection to SQLite."""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Enable dict-like access
            logger.info(f"Connected to SQLite at {self.db_path}")
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to connect to SQLite: {e}")

    async def disconnect(self) -> None:
        """Close SQLite connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info("Disconnected from SQLite")

    async def initialize_schema(self) -> None:
        """Initialize database schema."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        cursor = self.connection.cursor()

        # Nodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                node_type TEXT NOT NULL,
                name TEXT,
                properties TEXT NOT NULL,  -- JSON
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Relationships table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rel_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                properties TEXT,  -- JSON
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES nodes(id) ON DELETE CASCADE
            )
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_nodes_type_name
            ON nodes(node_type, name)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_nodes_created
            ON nodes(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_relationships_source
            ON relationships(source_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_relationships_target
            ON relationships(target_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_relationships_type
            ON relationships(rel_type)
        """)

        # Unique constraints for node names (per type)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_name
            ON nodes(node_type, name)
            WHERE node_type = 'SKILL' AND name IS NOT NULL
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_script_name
            ON nodes(node_type, name)
            WHERE node_type = 'SCRIPT' AND name IS NOT NULL
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_env_name
            ON nodes(node_type, name)
            WHERE node_type = 'ENV' AND name IS NOT NULL
        """)

        self.connection.commit()
        logger.info("SQLite schema initialized")

    async def health_check(self) -> bool:
        """Check database connection health."""
        if not self.connection:
            return False

        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    # Node Operations

    async def create_node(self, node_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new node."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        cursor = self.connection.cursor()

        # Make a copy to avoid modifying the input
        data = data.copy()

        # Extract common fields
        node_id = data.get("id")
        if not node_id:
            # Generate UUID if not provided
            import uuid
            node_id = str(uuid.uuid4())
            data["id"] = node_id

        name = data.get("name")
        now = datetime.utcnow().isoformat()

        # Store all data as JSON in properties
        properties = json.dumps(data)

        try:
            cursor.execute(
                """
                INSERT INTO nodes (id, node_type, name, properties, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (node_id, node_type, name, properties, now, now),
            )
            self.connection.commit()

            # Return the created node
            return {**data, "created_at": now, "updated_at": now}

        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                raise NodeAlreadyExistsError(name or "unknown", node_type)
            raise DatabaseConnectionError(f"Failed to create node: {e}")

    async def read_node(self, node_id: str) -> dict[str, Any] | None:
        """Retrieve a node by ID."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT properties FROM nodes WHERE id = ?",
            (node_id,),
        )
        row = cursor.fetchone()

        if row:
            return json.loads(row["properties"])
        return None

    async def read_node_by_name(self, node_type: str, name: str) -> dict[str, Any] | None:
        """Retrieve a node by type and name."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT properties FROM nodes WHERE node_type = ? AND name = ?",
            (node_type, name),
        )
        row = cursor.fetchone()

        if row:
            return json.loads(row["properties"])
        return None

    async def update_node(self, node_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing node."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        # First, get existing node
        existing = await self.read_node(node_id)
        if not existing:
            raise NodeNotFoundError(node_id)

        # Merge updates
        updated_data = {**existing, **data}
        updated_data["updated_at"] = datetime.utcnow().isoformat()

        cursor = self.connection.cursor()
        properties = json.dumps(updated_data)
        name = updated_data.get("name")

        try:
            cursor.execute(
                """
                UPDATE nodes
                SET properties = ?, name = ?, updated_at = ?
                WHERE id = ?
                """,
                (properties, name, updated_data["updated_at"], node_id),
            )
            self.connection.commit()

            return updated_data

        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e):
                raise NodeAlreadyExistsError(name or "unknown", "node")
            raise DatabaseConnectionError(f"Failed to update node: {e}")

    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its relationships."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        cursor = self.connection.cursor()

        # Delete relationships first (CASCADE should handle this, but be explicit)
        cursor.execute(
            "DELETE FROM relationships WHERE source_id = ? OR target_id = ?",
            (node_id, node_id),
        )

        # Delete node
        cursor.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        deleted = cursor.rowcount > 0

        self.connection.commit()

        if deleted:
            logger.info(f"Deleted node: {node_id}")
        return deleted

    async def list_nodes(
        self,
        node_type: str,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List nodes with optional filtering."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        filters = filters or {}
        cursor = self.connection.cursor()

        # Build query
        query = "SELECT properties FROM nodes WHERE node_type = ?"
        params: list[Any] = [node_type]

        if "name" in filters and filters["name"]:
            query += " AND name LIKE ?"
            params.append(f"%{filters['name']}%")

        if "created_after" in filters and filters["created_after"]:
            query += " AND created_at >= ?"
            params.append(filters["created_after"].isoformat())

        if "created_before" in filters and filters["created_before"]:
            query += " AND created_at <= ?"
            params.append(filters["created_before"].isoformat())

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [json.loads(row["properties"]) for row in rows]

    # Relationship Operations

    async def create_relationship(
        self,
        rel_type: str,
        source_id: str,
        target_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a relationship between nodes."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        # Check nodes exist
        source = await self.read_node(source_id)
        if not source:
            raise NodeNotFoundError(source_id)

        target = await self.read_node(target_id)
        if not target:
            raise NodeNotFoundError(target_id)

        # Check for circular dependencies if CONTAINS
        if rel_type == "CONTAINS":
            if await self.check_circular_dependency(source_id, target_id):
                raise CircularDependencyError(source_id, target_id)

        properties = properties or {}
        properties["created_at"] = datetime.utcnow().isoformat()
        props_json = json.dumps(properties)

        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO relationships (rel_type, source_id, target_id, properties, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (rel_type, source_id, target_id, props_json, properties["created_at"]),
        )
        self.connection.commit()

        rel_id = cursor.lastrowid

        logger.info(f"Created {rel_type} relationship: {source_id} -> {target_id}")

        return {
            "id": str(rel_id),
            "type": rel_type,
            "source_id": source_id,
            "target_id": target_id,
            **properties,
        }

    async def delete_relationship(self, rel_id: str) -> bool:
        """Delete a relationship by ID."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM relationships WHERE id = ?", (int(rel_id),))
        deleted = cursor.rowcount > 0
        self.connection.commit()

        if deleted:
            logger.info(f"Deleted relationship: {rel_id}")
        return deleted

    async def delete_relationships(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        rel_type: str | None = None,
    ) -> int:
        """Delete relationships matching criteria."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        query = "DELETE FROM relationships WHERE 1=1"
        params: list[Any] = []

        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)

        if target_id:
            query += " AND target_id = ?"
            params.append(target_id)

        if rel_type:
            query += " AND rel_type = ?"
            params.append(rel_type)

        cursor = self.connection.cursor()
        cursor.execute(query, params)
        deleted = cursor.rowcount
        self.connection.commit()

        if deleted > 0:
            logger.info(f"Deleted {deleted} relationship(s)")
        return deleted

    async def list_relationships(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        rel_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List relationships matching criteria."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        query = "SELECT id, rel_type, source_id, target_id, properties FROM relationships WHERE 1=1"
        params: list[Any] = []

        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)

        if target_id:
            query += " AND target_id = ?"
            params.append(target_id)

        if rel_type:
            query += " AND rel_type = ?"
            params.append(rel_type)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self.connection.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        relationships = []
        for row in rows:
            props = json.loads(row["properties"]) if row["properties"] else {}
            relationship = {
                "id": str(row["id"]),
                "type": row["rel_type"],
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                **props,
            }
            relationships.append(relationship)

        return relationships

    async def check_circular_dependency(self, source_id: str, target_id: str) -> bool:
        """Check if creating CONTAINS relationship would create a cycle."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        # Use recursive CTE to find paths
        cursor = self.connection.cursor()
        cursor.execute(
            """
            WITH RECURSIVE path(node_id, depth) AS (
                SELECT ?, 0
                UNION ALL
                SELECT r.target_id, p.depth + 1
                FROM relationships r
                JOIN path p ON r.source_id = p.node_id
                WHERE r.rel_type = 'CONTAINS' AND p.depth < 100
            )
            SELECT 1 FROM path WHERE node_id = ? LIMIT 1
            """,
            (target_id, source_id),
        )

        return cursor.fetchone() is not None

    async def get_connected_nodes(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        """Get nodes connected to a given node."""
        if not self.connection:
            raise DatabaseConnectionError("Not connected to database")

        cursor = self.connection.cursor()

        if direction == "outgoing":
            query = """
                SELECT n.properties
                FROM nodes n
                JOIN relationships r ON n.id = r.target_id
                WHERE r.source_id = ?
            """
            params: list[Any] = [node_id]
            if rel_type:
                query += " AND r.rel_type = ?"
                params.append(rel_type)

        elif direction == "incoming":
            query = """
                SELECT n.properties
                FROM nodes n
                JOIN relationships r ON n.id = r.source_id
                WHERE r.target_id = ?
            """
            params = [node_id]
            if rel_type:
                query += " AND r.rel_type = ?"
                params.append(rel_type)

        elif direction == "both":
            query = """
                SELECT DISTINCT n.properties
                FROM nodes n
                JOIN relationships r ON (n.id = r.target_id OR n.id = r.source_id)
                WHERE (r.source_id = ? OR r.target_id = ?)
                AND n.id != ?
            """
            params = [node_id, node_id, node_id]
            if rel_type:
                query += " AND r.rel_type = ?"
                params.append(rel_type)

        else:
            raise ValueError(f"Invalid direction: {direction}")

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [json.loads(row["properties"]) for row in rows]

    # Query Operations

    async def execute_query(
        self,
        cypher: str,
        parameters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Execute a read-only query.

        Note: This accepts Cypher syntax but translates simple queries to SQL.
        For complex graph queries, use Neo4j instead.
        """
        # For SQLite, we don't support full Cypher queries
        # This is a simplified implementation for testing
        raise InvalidQueryError(
            "SQLite adapter does not support Cypher queries. "
            "Use Neo4j for advanced graph queries, or use the "
            "list_nodes/list_relationships methods instead."
        )
