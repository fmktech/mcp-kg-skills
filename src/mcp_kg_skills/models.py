"""Pydantic models for MCP Knowledge Graph Skills."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class NodeType(str, Enum):
    """Valid node types in the knowledge graph."""

    SKILL = "SKILL"
    KNOWLEDGE = "KNOWLEDGE"
    SCRIPT = "SCRIPT"
    ENV = "ENV"


class RelationshipType(str, Enum):
    """Valid relationship types in the knowledge graph."""

    CONTAINS = "CONTAINS"
    RELATE_TO = "RELATE_TO"


class BaseNode(BaseModel):
    """Base model for all graph nodes."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique node identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )

    model_config = {"from_attributes": True, "populate_by_name": True}


class SkillNode(BaseNode):
    """SKILL node - High-level organizational unit."""

    name: str = Field(..., min_length=1, max_length=255, description="Unique skill name")
    description: str = Field(
        ..., min_length=1, max_length=1000, description="Brief skill description"
    )
    body: str = Field(..., description="Markdown content for the skill")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is properly formatted."""
        return v.strip()


class KnowledgeNode(BaseNode):
    """KNOWLEDGE node - Documentation and context."""

    name: str = Field(..., min_length=1, max_length=255, description="Knowledge item name")
    description: str = Field(..., min_length=1, max_length=1000, description="Brief description")
    body: str = Field(..., description="Markdown content for the knowledge")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is properly formatted."""
        return v.strip()


class ScriptNode(BaseNode):
    """SCRIPT node - Python functions with PEP 723 dependencies."""

    name: str = Field(..., min_length=1, max_length=255, description="Unique script name")
    description: str = Field(..., min_length=1, max_length=1000, description="What the script does")
    body: str = Field(..., description="Python code with PEP 723 metadata")
    function_signature: str = Field(
        ..., description='Function signature, e.g., "add(x: int, y: int) -> int"'
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is properly formatted."""
        return v.strip()

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str) -> str:
        """Ensure body contains valid Python code."""
        if not v.strip():
            raise ValueError("Script body cannot be empty")
        return v


class EnvNode(BaseNode):
    """ENV node - Environment variable collections."""

    name: str = Field(..., min_length=1, max_length=255, description="Environment name")
    description: str = Field(
        ..., min_length=1, max_length=1000, description="Environment description"
    )
    variables: dict[str, str] = Field(
        default_factory=dict, description="Non-secret environment variables (visible to LLM)"
    )
    secret_keys: list[str] = Field(
        default_factory=list, description="Names of secret variables only (values hidden)"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is properly formatted."""
        return v.strip()


class Relationship(BaseModel):
    """Relationship between nodes in the knowledge graph."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique relationship ID")
    type: RelationshipType = Field(..., description="Relationship type")
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    properties: dict[str, Any] = Field(default_factory=dict, description="Additional properties")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")

    model_config = {"from_attributes": True}


class NodeFilter(BaseModel):
    """Filter criteria for listing nodes."""

    name: str | None = Field(None, description="Filter by name (partial match)")
    created_after: datetime | None = Field(None, description="Filter by creation date")
    created_before: datetime | None = Field(None, description="Filter by creation date")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Offset for pagination")


class RelationshipFilter(BaseModel):
    """Filter criteria for listing relationships."""

    source_id: str | None = Field(None, description="Filter by source node ID")
    target_id: str | None = Field(None, description="Filter by target node ID")
    relationship_type: RelationshipType | None = Field(None, description="Filter by type")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Offset for pagination")


class ExecutionRequest(BaseModel):
    """Request to execute Python code with imported scripts."""

    code: str = Field(..., min_length=1, description="Python code to execute")
    imports: list[str] = Field(
        default_factory=list, description="List of SCRIPT node names to import"
    )
    timeout: int = Field(300, ge=1, le=600, description="Execution timeout in seconds")


class ExecutionResult(BaseModel):
    """Result of script execution."""

    success: bool = Field(..., description="Whether execution succeeded")
    stdout: str = Field(default="", description="Standard output (sanitized)")
    stderr: str = Field(default="", description="Standard error (sanitized)")
    return_code: int = Field(..., description="Process return code")
    execution_time: float = Field(..., description="Execution time in seconds")
    error: str | None = Field(None, description="Error message if failed")


class QueryRequest(BaseModel):
    """Request to execute a Cypher query."""

    cypher: str = Field(..., min_length=1, description="Cypher query string")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")


class QueryResult(BaseModel):
    """Result of a Cypher query."""

    success: bool = Field(..., description="Whether query succeeded")
    results: list[dict[str, Any]] = Field(default_factory=list, description="Query results")
    count: int = Field(..., description="Number of results returned")
    error: str | None = Field(None, description="Error message if failed")
