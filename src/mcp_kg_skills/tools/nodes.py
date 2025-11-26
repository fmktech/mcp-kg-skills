"""Node CRUD operations MCP tool."""

import logging
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from ..database.abstract import DatabaseInterface
from ..exceptions import (
    NodeAlreadyExistsError,
    NodeNotFoundError,
    ValidationError,
)
from ..models import (
    EnvNode,
    KnowledgeNode,
    NodeFilter,
    NodeType,
    ScriptNode,
    SkillNode,
)
from ..security.secrets import SecretDetector
from ..utils.env_file import EnvFileManager

logger = logging.getLogger(__name__)


class NodesTool:
    """Handles node CRUD operations."""

    def __init__(
        self,
        db: DatabaseInterface,
        env_manager: EnvFileManager,
        secret_detector: SecretDetector,
    ):
        """Initialize nodes tool.

        Args:
            db: Database interface
            env_manager: Environment file manager
            secret_detector: Secret detector for ENV nodes
        """
        self.db = db
        self.env_manager = env_manager
        self.secret_detector = secret_detector

    async def handle(
        self,
        operation: str,
        node_type: str,
        node_id: str | None = None,
        data: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle node operations.

        Args:
            operation: Operation to perform (create, read, update, delete, list)
            node_type: Type of node (SKILL, KNOWLEDGE, SCRIPT, ENV)
            node_id: Node ID (for read, update, delete)
            data: Node data (for create, update)
            filters: Filter criteria (for list)

        Returns:
            Operation result

        Raises:
            ValidationError: If operation or parameters are invalid
            NodeNotFoundError: If node doesn't exist (for read, update, delete)
            NodeAlreadyExistsError: If node name already exists (for create)
        """
        # Validate operation
        valid_operations = ["create", "read", "update", "delete", "list"]
        if operation not in valid_operations:
            raise ValidationError(
                f"Invalid operation '{operation}'. Must be one of: {', '.join(valid_operations)}"
            )

        # Validate node type
        try:
            node_type_enum = NodeType(node_type)
        except ValueError:
            raise ValidationError(
                f"Invalid node type '{node_type}'. "
                f"Must be one of: {', '.join([t.value for t in NodeType])}"
            )

        # Route to appropriate handler
        if operation == "create":
            return await self._create(node_type_enum, data or {})
        elif operation == "read":
            if not node_id:
                raise ValidationError("node_id is required for read operation")
            return await self._read(node_type_enum, node_id)
        elif operation == "update":
            if not node_id:
                raise ValidationError("node_id is required for update operation")
            return await self._update(node_type_enum, node_id, data or {})
        elif operation == "delete":
            if not node_id:
                raise ValidationError("node_id is required for delete operation")
            return await self._delete(node_type_enum, node_id)
        elif operation == "list":
            return await self._list(node_type_enum, filters or {})

        raise ValidationError(f"Unhandled operation: {operation}")

    async def _create(self, node_type: NodeType, data: dict[str, Any]) -> dict[str, Any]:
        """Create a new node."""
        try:
            # Validate and create appropriate model
            if node_type == NodeType.SKILL:
                node_model = SkillNode(**data)
            elif node_type == NodeType.KNOWLEDGE:
                node_model = KnowledgeNode(**data)
            elif node_type == NodeType.SCRIPT:
                node_model = ScriptNode(**data)
            elif node_type == NodeType.ENV:
                # Special handling for ENV nodes with secrets
                return await self._create_env(data)
            else:
                raise ValidationError(f"Unknown node type: {node_type}")

            # Convert to dict and create in database
            # Use mode="json" to serialize datetime objects to ISO format strings
            node_data = node_model.model_dump(mode="json")
            created_node = await self.db.create_node(node_type.value, node_data)

            logger.info(f"Created {node_type.value} node: {created_node['id']}")

            return {
                "success": True,
                "node": created_node,
                "message": f"{node_type.value} node created successfully",
            }

        except PydanticValidationError as e:
            raise ValidationError(f"Invalid node data: {e}")
        except NodeAlreadyExistsError:
            raise
        except Exception as e:
            logger.error(f"Failed to create {node_type.value} node: {e}")
            raise

    async def _create_env(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create an ENV node with secret handling."""
        # Extract all variables (public + secret)
        all_variables = data.get("variables", {})

        # Separate public variables and secrets
        public_vars, secret_keys, secret_values = self.secret_detector.extract_secrets(
            all_variables
        )

        # Create ENV node with only public variables visible
        env_data = {
            "name": data.get("name"),
            "description": data.get("description", ""),
            "variables": public_vars,
            "secret_keys": secret_keys,
        }

        env_model = EnvNode(**env_data)
        node_data = env_model.model_dump(mode="json")
        created_node = await self.db.create_node("ENV", node_data)

        # Create .env file with ALL variables (public + secret)
        env_id = created_node["id"]
        self.env_manager.write_env_file(env_id, public_vars, secret_values)

        logger.info(
            f"Created ENV node: {env_id} "
            f"({len(public_vars)} public, {len(secret_keys)} secret variables)"
        )

        # Return sanitized response
        response_node = dict(created_node)
        response_node["variables"] = self.secret_detector.sanitize_env_response(
            all_variables, secret_keys
        )

        return {
            "success": True,
            "node": response_node,
            "message": "ENV node created successfully",
        }

    async def _read(self, node_type: NodeType, node_id: str) -> dict[str, Any]:
        """Read a node by ID."""
        node = await self.db.read_node(node_id)

        if not node:
            raise NodeNotFoundError(node_id, node_type.value)

        # Sanitize ENV nodes
        if node_type == NodeType.ENV:
            node = self._sanitize_env_node(node)

        return {
            "success": True,
            "node": node,
        }

    async def _update(
        self, node_type: NodeType, node_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing node."""
        # Check node exists
        existing = await self.db.read_node(node_id)
        if not existing:
            raise NodeNotFoundError(node_id, node_type.value)

        # Special handling for ENV nodes
        if node_type == NodeType.ENV:
            return await self._update_env(node_id, data)

        # Update node in database
        updated_node = await self.db.update_node(node_id, data)

        logger.info(f"Updated {node_type.value} node: {node_id}")

        return {
            "success": True,
            "node": updated_node,
            "message": f"{node_type.value} node updated successfully",
        }

    async def _update_env(self, node_id: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update an ENV node with secret handling."""
        # Get existing ENV node
        existing = await self.db.read_node(node_id)
        if not existing:
            raise NodeNotFoundError(node_id, "ENV")

        # If variables are being updated, handle secrets
        if "variables" in data:
            all_variables = data["variables"]

            # Separate public variables and secrets
            public_vars, secret_keys, secret_values = self.secret_detector.extract_secrets(
                all_variables
            )

            # Update node data
            data["variables"] = public_vars
            data["secret_keys"] = secret_keys

            # Update database
            updated_node = await self.db.update_node(node_id, data)

            # Regenerate .env file
            self.env_manager.write_env_file(node_id, public_vars, secret_values)

            logger.info(f"Updated ENV node: {node_id}")

            # Return sanitized response
            response_node = dict(updated_node)
            response_node["variables"] = self.secret_detector.sanitize_env_response(
                all_variables, secret_keys
            )

            return {
                "success": True,
                "node": response_node,
                "message": "ENV node updated successfully",
            }
        else:
            # No variables update, just update other fields
            updated_node = await self.db.update_node(node_id, data)
            return {
                "success": True,
                "node": self._sanitize_env_node(updated_node),
                "message": "ENV node updated successfully",
            }

    async def _delete(self, node_type: NodeType, node_id: str) -> dict[str, Any]:
        """Delete a node.

        This operation is idempotent - deleting a non-existent node returns success.
        """
        # Special handling for ENV nodes - delete .env file
        if node_type == NodeType.ENV:
            self.env_manager.delete_env_file(node_id)

        deleted = await self.db.delete_node(node_id)

        if deleted:
            logger.info(f"Deleted {node_type.value} node: {node_id}")
            return {
                "success": True,
                "message": f"{node_type.value} node deleted successfully",
            }
        else:
            logger.debug(f"{node_type.value} node not found (already deleted): {node_id}")
            return {
                "success": True,
                "message": f"{node_type.value} node not found (may have been already deleted)",
                "already_deleted": True,
            }

    async def _list(self, node_type: NodeType, filters: dict[str, Any]) -> dict[str, Any]:
        """List nodes with filtering."""
        try:
            # Validate filters
            filter_model = NodeFilter(**filters)
            filter_dict = filter_model.model_dump(exclude_none=True)

            # Extract limit and offset
            limit = filter_dict.pop("limit", 100)
            offset = filter_dict.pop("offset", 0)

            # Query database
            nodes = await self.db.list_nodes(
                node_type.value, filter_dict, limit=limit, offset=offset
            )

            # Sanitize ENV nodes
            if node_type == NodeType.ENV:
                nodes = [self._sanitize_env_node(node) for node in nodes]

            return {
                "success": True,
                "nodes": nodes,
                "count": len(nodes),
                "limit": limit,
                "offset": offset,
            }

        except PydanticValidationError as e:
            raise ValidationError(f"Invalid filter criteria: {e}")

    def _sanitize_env_node(self, node: dict[str, Any]) -> dict[str, Any]:
        """Sanitize ENV node to hide secret values."""
        sanitized = dict(node)
        variables = sanitized.get("variables", {}).copy()
        secret_keys = sanitized.get("secret_keys", [])

        # Add secret keys with masked values to the variables dict
        for key in secret_keys:
            variables[key] = "<SECRET>"

        sanitized["variables"] = variables

        return sanitized
