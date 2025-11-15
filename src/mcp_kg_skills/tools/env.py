"""Environment variable management MCP tool."""

import logging
from typing import Any

from ..database.abstract import DatabaseInterface
from ..exceptions import NodeNotFoundError, ValidationError
from ..security.secrets import SecretDetector
from ..utils.env_file import EnvFileManager
from .nodes import NodesTool

logger = logging.getLogger(__name__)


class EnvTool:
    """Handles ENV-specific operations.

    This tool provides a specialized interface for ENV nodes,
    delegating to the NodesTool for core CRUD operations.
    """

    def __init__(
        self,
        db: DatabaseInterface,
        env_manager: EnvFileManager,
        secret_detector: SecretDetector,
    ):
        """Initialize env tool.

        Args:
            db: Database interface
            env_manager: Environment file manager
            secret_detector: Secret detector
        """
        self.db = db
        self.env_manager = env_manager
        self.secret_detector = secret_detector
        self.nodes_tool = NodesTool(db, env_manager, secret_detector)

    async def handle(
        self,
        operation: str,
        env_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        variables: dict[str, str] | None = None,
        keys: list[str] | None = None,
    ) -> dict[str, Any]:
        """Handle ENV operations.

        Args:
            operation: Operation to perform (create, read, update, delete, list_keys)
            env_id: ENV node ID
            name: ENV name (for create)
            description: ENV description
            variables: Environment variables
            keys: Variable keys to retrieve (for list_keys)

        Returns:
            Operation result

        Raises:
            ValidationError: If operation or parameters are invalid
            NodeNotFoundError: If ENV node doesn't exist
        """
        # Validate operation
        valid_operations = ["create", "read", "update", "delete", "list_keys"]
        if operation not in valid_operations:
            raise ValidationError(
                f"Invalid operation '{operation}'. "
                f"Must be one of: {', '.join(valid_operations)}"
            )

        # Route to appropriate handler
        if operation == "create":
            return await self._create(name, description, variables)
        elif operation == "read":
            if not env_id:
                raise ValidationError("env_id is required for read operation")
            return await self._read(env_id)
        elif operation == "update":
            if not env_id:
                raise ValidationError("env_id is required for update operation")
            return await self._update(env_id, description, variables)
        elif operation == "delete":
            if not env_id:
                raise ValidationError("env_id is required for delete operation")
            return await self._delete(env_id)
        elif operation == "list_keys":
            if not env_id:
                raise ValidationError("env_id is required for list_keys operation")
            return await self._list_keys(env_id, keys)

        raise ValidationError(f"Unhandled operation: {operation}")

    async def _create(
        self,
        name: str | None,
        description: str | None,
        variables: dict[str, str] | None,
    ) -> dict[str, Any]:
        """Create an ENV node."""
        if not name:
            raise ValidationError("name is required for create operation")

        data = {
            "name": name,
            "description": description or "",
            "variables": variables or {},
        }

        # Delegate to nodes tool
        return await self.nodes_tool.handle(
            operation="create",
            node_type="ENV",
            data=data,
        )

    async def _read(self, env_id: str) -> dict[str, Any]:
        """Read an ENV node (with secrets masked)."""
        return await self.nodes_tool.handle(
            operation="read",
            node_type="ENV",
            node_id=env_id,
        )

    async def _update(
        self,
        env_id: str,
        description: str | None,
        variables: dict[str, str] | None,
    ) -> dict[str, Any]:
        """Update an ENV node."""
        data = {}

        if description is not None:
            data["description"] = description

        if variables is not None:
            data["variables"] = variables

        if not data:
            raise ValidationError(
                "Either description or variables must be provided for update operation"
            )

        return await self.nodes_tool.handle(
            operation="update",
            node_type="ENV",
            node_id=env_id,
            data=data,
        )

    async def _delete(self, env_id: str) -> dict[str, Any]:
        """Delete an ENV node and its .env file."""
        return await self.nodes_tool.handle(
            operation="delete",
            node_type="ENV",
            node_id=env_id,
        )

    async def _list_keys(
        self, env_id: str, keys: list[str] | None
    ) -> dict[str, Any]:
        """List environment variable keys (names only, no values).

        Args:
            env_id: ENV node ID
            keys: Optional list of specific keys to retrieve

        Returns:
            Dictionary with keys and their metadata (not values)
        """
        # Read ENV node
        env_node = await self.db.read_node(env_id)

        if not env_node:
            raise NodeNotFoundError(env_id, "ENV")

        # Get all variable keys
        public_keys = list(env_node.get("variables", {}).keys())
        secret_keys = env_node.get("secret_keys", [])
        all_keys = public_keys + secret_keys

        # Filter to specific keys if requested
        if keys:
            all_keys = [k for k in all_keys if k in keys]

        # Build result with key metadata
        key_info = []
        for key in all_keys:
            is_secret = key in secret_keys
            key_info.append({
                "key": key,
                "is_secret": is_secret,
            })

        logger.debug(f"Listed {len(key_info)} keys from ENV {env_id}")

        return {
            "success": True,
            "env_id": env_id,
            "env_name": env_node.get("name"),
            "keys": key_info,
            "count": len(key_info),
        }
