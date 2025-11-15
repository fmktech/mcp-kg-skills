"""FastMCP server for MCP Knowledge Graph Skills."""

import logging
from typing import Any

from fastmcp import FastMCP

from .config import AppConfig, get_default_config_path, load_config
from .database.abstract import DatabaseInterface
from .database.neo4j import Neo4jDatabase
from .exceptions import MCPKGSkillsError
from .execution.runner import ScriptRunner
from .security.secrets import SecretDetector
from .tools.env import EnvTool
from .tools.execute import ExecuteTool
from .tools.nodes import NodesTool
from .tools.query import QueryTool
from .tools.relationships import RelationshipsTool
from .utils.env_file import EnvFileManager

logger = logging.getLogger(__name__)

# Create FastMCP instance
mcp = FastMCP("mcp-kg-skills")

# Global state
_config: AppConfig | None = None
_db: DatabaseInterface | None = None
_nodes_tool: NodesTool | None = None
_relationships_tool: RelationshipsTool | None = None
_env_tool: EnvTool | None = None
_execute_tool: ExecuteTool | None = None
_query_tool: QueryTool | None = None


@mcp.on_startup
async def initialize() -> None:
    """Initialize the MCP server.

    Loads configuration, connects to database, and initializes tools.
    """
    global _config, _db, _nodes_tool, _relationships_tool, _env_tool, _execute_tool, _query_tool

    try:
        # Load configuration
        config_path = get_default_config_path()
        _config = load_config(config_path)

        # Setup logging
        _config.setup_logging()

        # Ensure directories exist
        _config.ensure_directories()

        logger.info("MCP Knowledge Graph Skills server starting...")

        # Initialize database
        _db = Neo4jDatabase(
            uri=_config.database.uri,
            username=_config.database.username,
            password=_config.database.password,
            database=_config.database.database,
        )

        await _db.connect()
        await _db.initialize_schema()

        # Verify database health
        if not await _db.health_check():
            raise Exception("Database health check failed")

        # Initialize components
        env_manager = EnvFileManager(_config.execution.env_dir)
        secret_detector = SecretDetector(_config.security.secret_patterns)

        script_runner = ScriptRunner(
            db=_db,
            cache_dir=_config.execution.cache_dir,
            env_dir=_config.execution.env_dir,
            secret_detector=secret_detector,
        )

        # Initialize tools
        _nodes_tool = NodesTool(_db, env_manager, secret_detector)
        _relationships_tool = RelationshipsTool(_db)
        _env_tool = EnvTool(_db, env_manager, secret_detector)
        _execute_tool = ExecuteTool(script_runner)
        _query_tool = QueryTool(_db, secret_detector)

        logger.info("MCP Knowledge Graph Skills server initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize server: {e}")
        raise


@mcp.on_shutdown
async def cleanup() -> None:
    """Cleanup resources on server shutdown."""
    global _db

    try:
        logger.info("Shutting down MCP Knowledge Graph Skills server...")

        if _db:
            await _db.disconnect()

        logger.info("Server shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


@mcp.tool()
async def nodes(
    operation: str,
    node_type: str,
    node_id: str | None = None,
    data: dict[str, Any] | None = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Manage graph nodes (SKILL, KNOWLEDGE, SCRIPT, ENV).

    Supports create, read, update, delete, and list operations.

    Args:
        operation: Operation to perform (create, read, update, delete, list)
        node_type: Type of node (SKILL, KNOWLEDGE, SCRIPT, ENV)
        node_id: Node ID (for read, update, delete)
        data: Node data (for create, update)
        filters: Filter criteria (for list)

    Returns:
        Operation result

    Examples:
        Create a SKILL node:
        ```
        nodes(
            operation="create",
            node_type="SKILL",
            data={
                "name": "data-pipeline",
                "description": "ETL pipeline for data processing",
                "body": "# Data Pipeline\\n\\nThis skill..."
            }
        )
        ```

        List SCRIPT nodes:
        ```
        nodes(
            operation="list",
            node_type="SCRIPT",
            filters={"name": "fetch"}
        )
        ```
    """
    if not _nodes_tool:
        raise MCPKGSkillsError("Server not initialized")

    try:
        return await _nodes_tool.handle(
            operation=operation,
            node_type=node_type,
            node_id=node_id,
            data=data,
            filters=filters,
        )
    except MCPKGSkillsError:
        raise
    except Exception as e:
        logger.error(f"nodes tool error: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def relationships(
    operation: str,
    relationship_type: str | None = None,
    source_id: str | None = None,
    target_id: str | None = None,
    properties: dict[str, Any] | None = None,
    rel_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Manage relationships between nodes (CONTAINS, RELATE_TO).

    Supports create, delete, and list operations.
    Prevents circular CONTAINS dependencies.

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

    Examples:
        Create CONTAINS relationship:
        ```
        relationships(
            operation="create",
            relationship_type="CONTAINS",
            source_id="skill-123",
            target_id="script-456"
        )
        ```

        List relationships from a node:
        ```
        relationships(
            operation="list",
            source_id="skill-123"
        )
        ```
    """
    if not _relationships_tool:
        raise MCPKGSkillsError("Server not initialized")

    try:
        return await _relationships_tool.handle(
            operation=operation,
            relationship_type=relationship_type,
            source_id=source_id,
            target_id=target_id,
            properties=properties,
            rel_id=rel_id,
            limit=limit,
            offset=offset,
        )
    except MCPKGSkillsError:
        raise
    except Exception as e:
        logger.error(f"relationships tool error: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def env(
    operation: str,
    env_id: str | None = None,
    name: str | None = None,
    description: str | None = None,
    variables: dict[str, str] | None = None,
    keys: list[str] | None = None,
) -> dict[str, Any]:
    """Manage environment variables with automatic secret detection.

    Variables matching SECRET_*, *_KEY, *_PASSWORD, *_TOKEN patterns
    are automatically detected and hidden from LLM responses.
    ENV files are stored at .mcp-kg-skills/envs/{env_id}.env

    Args:
        operation: Operation to perform (create, read, update, delete, list_keys)
        env_id: ENV node ID
        name: ENV name (for create)
        description: ENV description
        variables: Environment variables
        keys: Variable keys to retrieve (for list_keys)

    Returns:
        Operation result with secrets masked

    Examples:
        Create environment:
        ```
        env(
            operation="create",
            name="production",
            description="Production environment",
            variables={
                "DATABASE_HOST": "prod.db.example.com",
                "DATABASE_PASSWORD": "secret123",  # Auto-detected as secret
                "API_KEY": "abc123"  # Auto-detected as secret
            }
        )
        ```

        List variable keys only:
        ```
        env(
            operation="list_keys",
            env_id="env-123"
        )
        ```
    """
    if not _env_tool:
        raise MCPKGSkillsError("Server not initialized")

    try:
        return await _env_tool.handle(
            operation=operation,
            env_id=env_id,
            name=name,
            description=description,
            variables=variables,
            keys=keys,
        )
    except MCPKGSkillsError:
        raise
    except Exception as e:
        logger.error(f"env tool error: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def execute(
    code: str,
    imports: list[str] | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Execute Python code with dynamically imported functions from SCRIPT nodes.

    The system automatically:
    - Loads specified SCRIPT nodes
    - Merges their PEP 723 dependencies
    - Loads connected ENV variables (with secrets available but hidden from output)
    - Executes code using 'uv run'
    - Sanitizes output to remove secret values

    Args:
        code: Python code to execute
        imports: List of SCRIPT node names to import (their functions will be available)
        timeout: Execution timeout in seconds (max 600)

    Returns:
        Execution result with sanitized output:
        {
            'success': bool,
            'stdout': str (sanitized),
            'stderr': str (sanitized),
            'return_code': int,
            'execution_time': float
        }

    Examples:
        Execute code with imported scripts:
        ```
        execute(
            code=\"\"\"
            # Imported functions are available
            data = fetch_data("https://api.example.com/data")
            df = process_data(data)
            print(df.head())
            \"\"\",
            imports=["fetch_data", "process_data"],
            timeout=60
        )
        ```

        Execute standalone code:
        ```
        execute(
            code="print('Hello, World!')",
            timeout=10
        )
        ```
    """
    if not _execute_tool:
        raise MCPKGSkillsError("Server not initialized")

    try:
        return await _execute_tool.handle(
            code=code,
            imports=imports,
            timeout=min(timeout, _config.execution.max_timeout)
            if _config
            else timeout,
        )
    except MCPKGSkillsError:
        raise
    except Exception as e:
        logger.error(f"execute tool error: {e}")
        return {
            "success": False,
            "error": str(e),
            "stdout": "",
            "stderr": str(e),
            "return_code": 1,
            "execution_time": 0.0,
        }


@mcp.tool()
async def query(
    cypher: str,
    parameters: dict[str, Any] | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Execute read-only Cypher queries to explore the knowledge graph.

    Only MATCH, RETURN, WITH, WHERE, ORDER BY operations are allowed.
    Results are automatically sanitized to hide secret values.

    Args:
        cypher: Read-only Cypher query
        parameters: Query parameters
        limit: Maximum number of results (max 1000)

    Returns:
        Query results (sanitized)

    Examples:
        Find all scripts in a skill:
        ```
        query(
            cypher=\"\"\"
            MATCH (s:SKILL {name: $skill_name})-[:CONTAINS]->(script:SCRIPT)
            RETURN script.name, script.function_signature
            \"\"\",
            parameters={"skill_name": "data-pipeline"}
        )
        ```

        Find scripts using a specific ENV:
        ```
        query(
            cypher=\"\"\"
            MATCH (script:SCRIPT)-[:CONTAINS]->(env:ENV {name: $env_name})
            RETURN script.name, script.description
            \"\"\",
            parameters={"env_name": "production"}
        )
        ```

        Find related skills:
        ```
        query(
            cypher=\"\"\"
            MATCH (s1:SKILL)-[:RELATE_TO]-(s2:SKILL)
            WHERE s1.name = $name
            RETURN s2.name, s2.description
            \"\"\",
            parameters={"name": "etl-pipeline"}
        )
        ```
    """
    if not _query_tool:
        raise MCPKGSkillsError("Server not initialized")

    try:
        return await _query_tool.handle(
            cypher=cypher,
            parameters=parameters,
            limit=min(limit, 1000),
        )
    except MCPKGSkillsError:
        raise
    except Exception as e:
        logger.error(f"query tool error: {e}")
        return {"success": False, "error": str(e), "results": [], "count": 0}


def main() -> None:
    """Main entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
