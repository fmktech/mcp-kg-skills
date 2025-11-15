"""Abstract database interface for MCP Knowledge Graph Skills."""

from abc import ABC, abstractmethod
from typing import Any


class DatabaseInterface(ABC):
    """Abstract interface for database operations.

    This interface defines all database operations required by the MCP KG Skills server.
    Implementations can use different graph databases (Neo4j, etc.).
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish database connection.

        Raises:
            DatabaseConnectionError: If connection fails
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close database connection."""
        pass

    @abstractmethod
    async def initialize_schema(self) -> None:
        """Initialize database schema (constraints, indexes).

        Creates:
        - Unique constraints on node names (SKILL, SCRIPT, ENV)
        - Indexes on node IDs and timestamps
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if database connection is healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        pass

    # Node Operations

    @abstractmethod
    async def create_node(self, node_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new node in the graph.

        Args:
            node_type: Type of node (SKILL, KNOWLEDGE, SCRIPT, ENV)
            data: Node properties

        Returns:
            Created node with all properties including generated ID

        Raises:
            NodeAlreadyExistsError: If node with same name exists (for types with unique names)
            ValidationError: If data is invalid
        """
        pass

    @abstractmethod
    async def read_node(self, node_id: str) -> dict[str, Any] | None:
        """Retrieve a node by ID.

        Args:
            node_id: Node identifier

        Returns:
            Node properties or None if not found
        """
        pass

    @abstractmethod
    async def read_node_by_name(self, node_type: str, name: str) -> dict[str, Any] | None:
        """Retrieve a node by type and name.

        Args:
            node_type: Type of node
            name: Node name

        Returns:
            Node properties or None if not found
        """
        pass

    @abstractmethod
    async def update_node(self, node_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an existing node.

        Args:
            node_id: Node identifier
            data: Properties to update

        Returns:
            Updated node with all properties

        Raises:
            NodeNotFoundError: If node does not exist
            ValidationError: If data is invalid
        """
        pass

    @abstractmethod
    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and all its relationships.

        Args:
            node_id: Node identifier

        Returns:
            True if node was deleted, False if not found
        """
        pass

    @abstractmethod
    async def list_nodes(
        self,
        node_type: str,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List nodes of a specific type with optional filtering.

        Args:
            node_type: Type of nodes to list
            filters: Optional filter criteria (name, created_after, created_before)
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of nodes matching criteria
        """
        pass

    # Relationship Operations

    @abstractmethod
    async def create_relationship(
        self,
        rel_type: str,
        source_id: str,
        target_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a relationship between two nodes.

        Args:
            rel_type: Relationship type (CONTAINS, RELATE_TO)
            source_id: Source node ID
            target_id: Target node ID
            properties: Optional relationship properties

        Returns:
            Created relationship with all properties

        Raises:
            NodeNotFoundError: If source or target node not found
            CircularDependencyError: If creating CONTAINS would create a cycle
        """
        pass

    @abstractmethod
    async def delete_relationship(self, rel_id: str) -> bool:
        """Delete a relationship by ID.

        Args:
            rel_id: Relationship identifier

        Returns:
            True if relationship was deleted, False if not found
        """
        pass

    @abstractmethod
    async def delete_relationships(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        rel_type: str | None = None,
    ) -> int:
        """Delete relationships matching criteria.

        Args:
            source_id: Optional source node filter
            target_id: Optional target node filter
            rel_type: Optional relationship type filter

        Returns:
            Number of relationships deleted
        """
        pass

    @abstractmethod
    async def list_relationships(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        rel_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List relationships matching criteria.

        Args:
            source_id: Optional source node filter
            target_id: Optional target node filter
            rel_type: Optional relationship type filter
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of relationships
        """
        pass

    @abstractmethod
    async def check_circular_dependency(self, source_id: str, target_id: str) -> bool:
        """Check if creating a CONTAINS relationship would create a circular dependency.

        Args:
            source_id: Source node ID
            target_id: Target node ID

        Returns:
            True if circular dependency would be created, False otherwise
        """
        pass

    @abstractmethod
    async def get_connected_nodes(
        self,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "outgoing",
    ) -> list[dict[str, Any]]:
        """Get nodes connected to a given node.

        Args:
            node_id: Node identifier
            rel_type: Optional relationship type filter
            direction: Direction to traverse ('outgoing', 'incoming', 'both')

        Returns:
            List of connected nodes
        """
        pass

    # Query Operations

    @abstractmethod
    async def execute_query(
        self,
        cypher: str,
        parameters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Execute a read-only Cypher query.

        Args:
            cypher: Cypher query string
            parameters: Query parameters
            limit: Maximum number of results

        Returns:
            Query results

        Raises:
            InvalidQueryError: If query is not read-only or is malformed
        """
        pass
