"""Relationship management MCP tool."""

import logging
from typing import Any

from ..database.abstract import DatabaseInterface
from ..exceptions import (
    CircularDependencyError,
    NodeNotFoundError,
    ValidationError,
)
from ..models import RelationshipType

logger = logging.getLogger(__name__)


class RelationshipsTool:
    """Handles relationship operations."""

    def __init__(self, db: DatabaseInterface):
        """Initialize relationships tool.

        Args:
            db: Database interface
        """
        self.db = db

    async def handle(
        self,
        operation: str,
        relationship_type: str | None = None,
        source_id: str | None = None,
        target_id: str | None = None,
        properties: dict[str, Any] | None = None,
        rel_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Handle relationship operations.

        Args:
            operation: Operation to perform (create, delete, list)
            relationship_type: Type of relationship (CONTAINS, RELATE_TO)
            source_id: Source node ID
            target_id: Target node ID
            properties: Relationship properties
            rel_id: Relationship ID (for delete)
            limit: Maximum results (for list)
            offset: Offset for pagination (for list)

        Returns:
            Operation result

        Raises:
            ValidationError: If operation or parameters are invalid
            NodeNotFoundError: If source or target node doesn't exist
            CircularDependencyError: If creating CONTAINS would create a cycle
            RelationshipNotFoundError: If relationship doesn't exist (for delete)
        """
        # Validate operation
        valid_operations = ["create", "delete", "list"]
        if operation not in valid_operations:
            raise ValidationError(
                f"Invalid operation '{operation}'. Must be one of: {', '.join(valid_operations)}"
            )

        # Route to appropriate handler
        if operation == "create":
            return await self._create(relationship_type, source_id, target_id, properties)
        elif operation == "delete":
            return await self._delete(rel_id, source_id, target_id, relationship_type)
        elif operation == "list":
            return await self._list(source_id, target_id, relationship_type, limit, offset)

        raise ValidationError(f"Unhandled operation: {operation}")

    async def _create(
        self,
        relationship_type: str | None,
        source_id: str | None,
        target_id: str | None,
        properties: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Create a new relationship."""
        # Validate required parameters
        if not relationship_type:
            raise ValidationError("relationship_type is required for create operation")
        if not source_id:
            raise ValidationError("source_id is required for create operation")
        if not target_id:
            raise ValidationError("target_id is required for create operation")

        # Validate relationship type
        try:
            rel_type_enum = RelationshipType(relationship_type)
        except ValueError:
            raise ValidationError(
                f"Invalid relationship type '{relationship_type}'. "
                f"Must be one of: {', '.join([t.value for t in RelationshipType])}"
            )

        # Verify source and target nodes exist
        source_node = await self.db.read_node(source_id)
        if not source_node:
            raise NodeNotFoundError(source_id)

        target_node = await self.db.read_node(target_id)
        if not target_node:
            raise NodeNotFoundError(target_id)

        # Check for circular dependencies if CONTAINS
        if rel_type_enum == RelationshipType.CONTAINS:
            if await self.db.check_circular_dependency(source_id, target_id):
                raise CircularDependencyError(source_id, target_id)

        # Create relationship
        try:
            relationship = await self.db.create_relationship(
                rel_type_enum.value,
                source_id,
                target_id,
                properties or {},
            )

            logger.info(f"Created {rel_type_enum.value} relationship: {source_id} -> {target_id}")

            return {
                "success": True,
                "relationship": relationship,
                "message": f"{rel_type_enum.value} relationship created successfully",
            }

        except CircularDependencyError:
            raise
        except Exception as e:
            logger.error(f"Failed to create relationship: {e}")
            raise

    async def _delete(
        self,
        rel_id: str | None,
        source_id: str | None,
        target_id: str | None,
        relationship_type: str | None,
    ) -> dict[str, Any]:
        """Delete a relationship.

        This operation is idempotent - deleting a non-existent relationship returns success.
        """
        if rel_id:
            # Delete by relationship ID
            deleted = await self.db.delete_relationship(rel_id)

            if deleted:
                logger.info(f"Deleted relationship: {rel_id}")
                return {
                    "success": True,
                    "message": "Relationship deleted successfully",
                }
            else:
                logger.debug(f"Relationship not found (already deleted): {rel_id}")
                return {
                    "success": True,
                    "message": "Relationship not found (may have been already deleted)",
                    "already_deleted": True,
                }

        elif source_id or target_id or relationship_type:
            # Delete by criteria
            deleted_count = await self.db.delete_relationships(
                source_id=source_id,
                target_id=target_id,
                rel_type=relationship_type,
            )

            logger.info(f"Deleted {deleted_count} relationship(s)")

            return {
                "success": True,
                "count": deleted_count,
                "message": f"Deleted {deleted_count} relationship(s)",
            }

        else:
            raise ValidationError(
                "Either rel_id or (source_id/target_id/relationship_type) "
                "must be provided for delete operation"
            )

    async def _list(
        self,
        source_id: str | None,
        target_id: str | None,
        relationship_type: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        """List relationships with filtering."""
        try:
            # Validate relationship type if provided
            rel_type_enum = None
            if relationship_type:
                try:
                    rel_type_enum = RelationshipType(relationship_type)
                except ValueError:
                    raise ValidationError(
                        f"Invalid relationship type '{relationship_type}'. "
                        f"Must be one of: {', '.join([t.value for t in RelationshipType])}"
                    )

            # Query database
            relationships = await self.db.list_relationships(
                source_id=source_id,
                target_id=target_id,
                rel_type=rel_type_enum.value if rel_type_enum else None,
                limit=limit,
                offset=offset,
            )

            return {
                "success": True,
                "relationships": relationships,
                "count": len(relationships),
                "limit": limit,
                "offset": offset,
            }

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to list relationships: {e}")
            raise ValidationError(f"Failed to list relationships: {e}")
