"""Custom exceptions for MCP Knowledge Graph Skills."""


class MCPKGSkillsError(Exception):
    """Base exception for all MCP KG Skills errors."""

    pass


class NodeNotFoundError(MCPKGSkillsError):
    """Raised when a requested node does not exist."""

    def __init__(self, node_id: str, node_type: str | None = None):
        self.node_id = node_id
        self.node_type = node_type
        msg = f"Node '{node_id}'"
        if node_type:
            msg += f" of type '{node_type}'"
        msg += " not found"
        super().__init__(msg)


class NodeAlreadyExistsError(MCPKGSkillsError):
    """Raised when attempting to create a node with a name that already exists."""

    def __init__(self, name: str, node_type: str):
        self.name = name
        self.node_type = node_type
        super().__init__(f"{node_type} node with name '{name}' already exists")


class CircularDependencyError(MCPKGSkillsError):
    """Raised when a CONTAINS relationship would create a circular dependency."""

    def __init__(self, source_id: str, target_id: str):
        self.source_id = source_id
        self.target_id = target_id
        super().__init__(
            f"Creating CONTAINS relationship from '{source_id}' to '{target_id}' "
            "would create a circular dependency"
        )


class RelationshipNotFoundError(MCPKGSkillsError):
    """Raised when a requested relationship does not exist."""

    def __init__(
        self, rel_id: str | None = None, source_id: str | None = None, target_id: str | None = None
    ):
        self.rel_id = rel_id
        self.source_id = source_id
        self.target_id = target_id
        if rel_id:
            msg = f"Relationship '{rel_id}' not found"
        else:
            msg = f"Relationship from '{source_id}' to '{target_id}' not found"
        super().__init__(msg)


class ScriptExecutionError(MCPKGSkillsError):
    """Raised when script execution fails."""

    def __init__(self, message: str, return_code: int | None = None, stderr: str | None = None):
        self.return_code = return_code
        self.stderr = stderr
        super().__init__(message)


class InvalidQueryError(MCPKGSkillsError):
    """Raised when a Cypher query is invalid or not read-only."""

    def __init__(self, message: str):
        super().__init__(message)


class DatabaseConnectionError(MCPKGSkillsError):
    """Raised when database connection fails."""

    def __init__(self, message: str):
        super().__init__(f"Database connection error: {message}")


class ConfigurationError(MCPKGSkillsError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str):
        super().__init__(f"Configuration error: {message}")


class ValidationError(MCPKGSkillsError):
    """Raised when data validation fails."""

    def __init__(self, message: str):
        super().__init__(f"Validation error: {message}")


class EnvFileError(MCPKGSkillsError):
    """Raised when environment file operations fail."""

    def __init__(self, message: str, env_id: str | None = None):
        self.env_id = env_id
        if env_id:
            super().__init__(f"ENV file error for '{env_id}': {message}")
        else:
            super().__init__(f"ENV file error: {message}")


class DependencyParseError(MCPKGSkillsError):
    """Raised when PEP 723 dependency parsing fails."""

    def __init__(self, message: str, script_name: str | None = None):
        self.script_name = script_name
        if script_name:
            super().__init__(f"Dependency parse error in '{script_name}': {message}")
        else:
            super().__init__(f"Dependency parse error: {message}")
