"""Neo4j database implementation for MCP Knowledge Graph Skills."""

import logging
from datetime import datetime
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from neo4j.exceptions import (
    ConstraintError,
    Neo4jError,
    ServiceUnavailable,
)

from ..exceptions import (
    CircularDependencyError,
    DatabaseConnectionError,
    InvalidQueryError,
    NodeAlreadyExistsError,
    NodeNotFoundError,
    RelationshipNotFoundError,
)
from .abstract import DatabaseInterface

logger = logging.getLogger(__name__)


class Neo4jDatabase(DatabaseInterface):
    """Neo4j implementation of the database interface."""

    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j",
    ):
        """Initialize Neo4j database connection.

        Args:
            uri: Neo4j connection URI (e.g., bolt://localhost:7687)
            username: Database username
            password: Database password
            database: Database name (default: neo4j)
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
            )
            # Verify connectivity
            await self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.uri}")
        except ServiceUnavailable as e:
            raise DatabaseConnectionError(f"Cannot connect to Neo4j at {self.uri}: {e}")
        except Exception as e:
            raise DatabaseConnectionError(f"Failed to connect to Neo4j: {e}")

    async def disconnect(self) -> None:
        """Close Neo4j connection."""
        if self.driver:
            await self.driver.close()
            self.driver = None
            logger.info("Disconnected from Neo4j")

    async def initialize_schema(self) -> None:
        """Create constraints and indexes for the knowledge graph."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        async with self.driver.session(database=self.database) as session:
            # Unique constraints on names
            await session.run(
                """
                CREATE CONSTRAINT skill_name_unique IF NOT EXISTS
                FOR (s:SKILL) REQUIRE s.name IS UNIQUE
                """
            )
            await session.run(
                """
                CREATE CONSTRAINT script_name_unique IF NOT EXISTS
                FOR (s:SCRIPT) REQUIRE s.name IS UNIQUE
                """
            )
            await session.run(
                """
                CREATE CONSTRAINT env_name_unique IF NOT EXISTS
                FOR (e:ENV) REQUIRE e.name IS UNIQUE
                """
            )

            # Index on node IDs for fast lookups
            for node_type in ["SKILL", "KNOWLEDGE", "SCRIPT", "ENV"]:
                await session.run(
                    f"""
                    CREATE INDEX {node_type.lower()}_id_index IF NOT EXISTS
                    FOR (n:{node_type}) ON (n.id)
                    """
                )

            # Index on created_at for temporal queries
            for node_type in ["SKILL", "KNOWLEDGE", "SCRIPT", "ENV"]:
                await session.run(
                    f"""
                    CREATE INDEX {node_type.lower()}_created_at_index IF NOT EXISTS
                    FOR (n:{node_type}) ON (n.created_at)
                    """
                )

            logger.info("Database schema initialized")

    async def health_check(self) -> bool:
        """Check database connection health."""
        if not self.driver:
            return False

        try:
            async with self.driver.session(database=self.database) as session:
                result = await session.run("RETURN 1 AS health")
                record = await result.single()
                return record and record["health"] == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    # Node Operations

    async def create_node(self, node_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new node."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        # Ensure timestamps are set
        now = datetime.utcnow()
        data.setdefault("created_at", now)
        data.setdefault("updated_at", now)

        async with self.driver.session(database=self.database) as session:
            try:
                result = await session.run(
                    f"""
                    CREATE (n:{node_type} $props)
                    RETURN n
                    """,
                    props=data,
                )
                record = await result.single()
                if not record:
                    raise DatabaseConnectionError("Failed to create node")

                node = dict(record["n"])
                logger.info(f"Created {node_type} node: {node.get('id')}")
                return node

            except ConstraintError as e:
                # Unique constraint violation
                name = data.get("name", "unknown")
                raise NodeAlreadyExistsError(name, node_type)
            except Neo4jError as e:
                raise DatabaseConnectionError(f"Failed to create node: {e}")

    async def read_node(self, node_id: str) -> dict[str, Any] | None:
        """Retrieve a node by ID."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        async with self.driver.session(database=self.database) as session:
            result = await session.run(
                """
                MATCH (n {id: $node_id})
                RETURN n
                """,
                node_id=node_id,
            )
            record = await result.single()
            return dict(record["n"]) if record else None

    async def read_node_by_name(self, node_type: str, name: str) -> dict[str, Any] | None:
        """Retrieve a node by type and name."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        async with self.driver.session(database=self.database) as session:
            result = await session.run(
                f"""
                MATCH (n:{node_type} {{name: $name}})
                RETURN n
                """,
                name=name,
            )
            record = await result.single()
            return dict(record["n"]) if record else None

    async def update_node(self, node_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing node."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        # Update timestamp
        data["updated_at"] = datetime.utcnow()

        async with self.driver.session(database=self.database) as session:
            try:
                result = await session.run(
                    """
                    MATCH (n {id: $node_id})
                    SET n += $props
                    RETURN n
                    """,
                    node_id=node_id,
                    props=data,
                )
                record = await result.single()
                if not record:
                    raise NodeNotFoundError(node_id)

                node = dict(record["n"])
                logger.info(f"Updated node: {node_id}")
                return node

            except ConstraintError as e:
                name = data.get("name", "unknown")
                raise NodeAlreadyExistsError(name, "node")
            except Neo4jError as e:
                raise DatabaseConnectionError(f"Failed to update node: {e}")

    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its relationships."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        async with self.driver.session(database=self.database) as session:
            result = await session.run(
                """
                MATCH (n {id: $node_id})
                DETACH DELETE n
                RETURN count(n) AS deleted
                """,
                node_id=node_id,
            )
            record = await result.single()
            deleted = record["deleted"] if record else 0

            if deleted > 0:
                logger.info(f"Deleted node: {node_id}")
                return True
            return False

    async def list_nodes(
        self,
        node_type: str,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List nodes with optional filtering."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        filters = filters or {}
        where_clauses = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        # Build WHERE clauses
        if "name" in filters and filters["name"]:
            where_clauses.append("n.name CONTAINS $name")
            params["name"] = filters["name"]

        if "created_after" in filters and filters["created_after"]:
            where_clauses.append("n.created_at >= $created_after")
            params["created_after"] = filters["created_after"]

        if "created_before" in filters and filters["created_before"]:
            where_clauses.append("n.created_at <= $created_before")
            params["created_before"] = filters["created_before"]

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
        MATCH (n:{node_type})
        {where_clause}
        RETURN n
        ORDER BY n.created_at DESC
        SKIP $offset
        LIMIT $limit
        """

        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, **params)
            records = await result.values()
            return [dict(record[0]) for record in records]

    # Relationship Operations

    async def create_relationship(
        self,
        rel_type: str,
        source_id: str,
        target_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a relationship between nodes."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        # Check for circular dependencies if CONTAINS relationship
        if rel_type == "CONTAINS":
            if await self.check_circular_dependency(source_id, target_id):
                raise CircularDependencyError(source_id, target_id)

        properties = properties or {}
        properties.setdefault("created_at", datetime.utcnow())

        async with self.driver.session(database=self.database) as session:
            result = await session.run(
                f"""
                MATCH (source {{id: $source_id}})
                MATCH (target {{id: $target_id}})
                CREATE (source)-[r:{rel_type} $props]->(target)
                RETURN r, id(r) AS rel_id, source.id AS source_id, target.id AS target_id
                """,
                source_id=source_id,
                target_id=target_id,
                props=properties,
            )
            record = await result.single()
            if not record:
                # Check which node doesn't exist
                source_exists = await self.read_node(source_id)
                if not source_exists:
                    raise NodeNotFoundError(source_id)
                raise NodeNotFoundError(target_id)

            relationship = {
                "id": str(record["rel_id"]),
                "type": rel_type,
                "source_id": record["source_id"],
                "target_id": record["target_id"],
                **dict(record["r"]),
            }

            logger.info(f"Created {rel_type} relationship: {source_id} -> {target_id}")
            return relationship

    async def delete_relationship(self, rel_id: str) -> bool:
        """Delete a relationship by internal ID."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        async with self.driver.session(database=self.database) as session:
            result = await session.run(
                """
                MATCH ()-[r]->()
                WHERE id(r) = toInteger($rel_id)
                DELETE r
                RETURN count(r) AS deleted
                """,
                rel_id=rel_id,
            )
            record = await result.single()
            deleted = record["deleted"] if record else 0

            if deleted > 0:
                logger.info(f"Deleted relationship: {rel_id}")
                return True
            return False

    async def delete_relationships(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        rel_type: str | None = None,
    ) -> int:
        """Delete relationships matching criteria."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        where_clauses = []
        params: dict[str, Any] = {}

        if source_id:
            where_clauses.append("source.id = $source_id")
            params["source_id"] = source_id

        if target_id:
            where_clauses.append("target.id = $target_id")
            params["target_id"] = target_id

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        rel_pattern = f"[r:{rel_type}]" if rel_type else "[r]"

        query = f"""
        MATCH (source)-{rel_pattern}->(target)
        {where_clause}
        DELETE r
        RETURN count(r) AS deleted
        """

        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, **params)
            record = await result.single()
            deleted = record["deleted"] if record else 0

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
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        where_clauses = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}

        if source_id:
            where_clauses.append("source.id = $source_id")
            params["source_id"] = source_id

        if target_id:
            where_clauses.append("target.id = $target_id")
            params["target_id"] = target_id

        where_clause = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        rel_pattern = f"[r:{rel_type}]" if rel_type else "[r]"

        query = f"""
        MATCH (source)-{rel_pattern}->(target)
        {where_clause}
        RETURN r, id(r) AS rel_id, type(r) AS rel_type,
               source.id AS source_id, target.id AS target_id
        ORDER BY r.created_at DESC
        SKIP $offset
        LIMIT $limit
        """

        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, **params)
            records = await result.values()

            relationships = []
            for record in records:
                rel_data = dict(record[0])  # r properties
                relationship = {
                    "id": str(record[1]),  # rel_id
                    "type": record[2],  # rel_type
                    "source_id": record[3],  # source_id
                    "target_id": record[4],  # target_id
                    **rel_data,
                }
                relationships.append(relationship)

            return relationships

    async def check_circular_dependency(self, source_id: str, target_id: str) -> bool:
        """Check if creating CONTAINS relationship would create a cycle."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        # Check if there's already a path from target to source via CONTAINS
        async with self.driver.session(database=self.database) as session:
            result = await session.run(
                """
                MATCH path = (target {id: $target_id})-[:CONTAINS*]->(source {id: $source_id})
                RETURN count(path) > 0 AS has_cycle
                """,
                target_id=target_id,
                source_id=source_id,
            )
            record = await result.single()
            return record["has_cycle"] if record else False

    async def get_connected_nodes(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        """Get nodes connected to a given node."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        rel_pattern = f"[:{rel_type}]" if rel_type else "[]"

        if direction == "outgoing":
            pattern = f"(n {{id: $node_id}})-{rel_pattern}->(connected)"
        elif direction == "incoming":
            pattern = f"(n {{id: $node_id}})<-{rel_pattern}-(connected)"
        elif direction == "both":
            pattern = f"(n {{id: $node_id}})-{rel_pattern}-(connected)"
        else:
            raise ValueError(f"Invalid direction: {direction}")

        query = f"""
        MATCH {pattern}
        RETURN connected
        """

        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, node_id=node_id)
            records = await result.values()
            return [dict(record[0]) for record in records]

    # Query Operations

    async def execute_query(
        self,
        cypher: str,
        parameters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Execute a read-only Cypher query."""
        if not self.driver:
            raise DatabaseConnectionError("Not connected to database")

        # Validate query is read-only
        if not self._is_readonly_query(cypher):
            raise InvalidQueryError(
                "Query must be read-only (only MATCH, RETURN, WITH, WHERE, ORDER BY, etc.)"
            )

        parameters = parameters or {}

        async with self.driver.session(database=self.database) as session:
            try:
                result = await session.run(cypher, **parameters)
                records = await result.values()

                # Convert records to list of dicts
                results = []
                keys = await result.keys()
                for record in records[:limit]:
                    result_dict = {}
                    for i, key in enumerate(keys):
                        value = record[i]
                        # Convert Neo4j types to Python types
                        if hasattr(value, "__dict__"):
                            result_dict[key] = dict(value)
                        else:
                            result_dict[key] = value
                    results.append(result_dict)

                return results

            except Neo4jError as e:
                raise InvalidQueryError(f"Query execution failed: {e}")

    def _is_readonly_query(self, cypher: str) -> bool:
        """Check if a Cypher query is read-only."""
        cypher_upper = cypher.upper()

        # List of write operations
        write_keywords = [
            "CREATE",
            "DELETE",
            "REMOVE",
            "SET",
            "MERGE",
            "DETACH",
            "DROP",
        ]

        for keyword in write_keywords:
            if keyword in cypher_upper:
                return False

        return True
