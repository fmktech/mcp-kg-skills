"""FastMCP server for MCP Knowledge Graph Skills."""

import json
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

# Global state - initialized lazily
_initialized = False
_config: AppConfig | None = None
_db: DatabaseInterface | None = None
_nodes_tool: NodesTool | None = None
_relationships_tool: RelationshipsTool | None = None
_env_tool: EnvTool | None = None
_execute_tool: ExecuteTool | None = None
_query_tool: QueryTool | None = None


async def _ensure_initialized() -> None:
    """Lazy initialization of server components."""
    global \
        _initialized, \
        _config, \
        _db, \
        _nodes_tool, \
        _relationships_tool, \
        _env_tool, \
        _execute_tool, \
        _query_tool

    if _initialized:
        return

    try:
        # Load configuration
        config_path = get_default_config_path()
        _config = load_config(config_path)

        # Setup logging
        _config.setup_logging()

        # Ensure directories exist
        _config.ensure_directories()

        logger.info("MCP Knowledge Graph Skills server initializing...")

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

        _initialized = True
        logger.info("MCP Knowledge Graph Skills server initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize server: {e}")
        raise


@mcp.tool()
async def nodes(
    operation: str,
    node_type: str,
    node_id: str | None = None,
    data: dict[str, Any] | str | None = None,
    filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
    """Manage graph nodes (SKILL, KNOWLEDGE, SCRIPT, ENV).

        Supports create, read, update, delete, and list operations.

        Args:
            operation: Operation to perform (create, read, update, delete, list)
            node_type: Type of node (SKILL, KNOWLEDGE, SCRIPT, ENV)
            node_id: Node ID (for read, update, delete)
            data: Node data (for create, update) - can be dict or JSON string
            filters: Filter criteria (for list) - can be dict or JSON string

        Returns:
            Operation result

        SCRIPT Node Best Practices:
            - Do NOT include `if __name__ == '__main__':` blocks - they are
              automatically stripped during execution to prevent unintended side effects
            - Export functions/classes that should be callable from user code
            - Keep example/test code in separate functions, not in __main__ blocks
            - Use PEP 723 metadata for dependencies
            - To use environment variables, create an ENV node and connect it to the
              SCRIPT using a CONTAINS relationship: SCRIPT -[:CONTAINS]-> ENV
              The ENV variables will be automatically loaded during execution

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

            Create a SCRIPT node (note: no __main__ block):
            ```
            nodes(
                operation="create",
                node_type="SCRIPT",
                data={
                    "name": "fetch_data",
                    "description": "Fetch data from API",
                    "function_signature": "fetch_data(url: str) -> dict",
                    "body": '''# /// script
    # requires-python = ">=3.12"
    # dependencies = ["requests>=2.31.0"]
    # ///

    import requests

    def fetch_data(url: str) -> dict:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    '''
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
    await _ensure_initialized()

    if not _nodes_tool:
        raise MCPKGSkillsError("Server not initialized")

    try:
        # Parse JSON strings if provided
        parsed_data: dict[str, Any] | None = None
        if isinstance(data, str):
            try:
                parsed_data = json.loads(data)
            except json.JSONDecodeError as e:
                return {"success": False, "error": f"Invalid JSON in data parameter: {e}"}
        elif data is not None:
            parsed_data = data

        parsed_filters: dict[str, Any] | None = None
        if isinstance(filters, str):
            try:
                parsed_filters = json.loads(filters)
            except json.JSONDecodeError as e:
                return {"success": False, "error": f"Invalid JSON in filters parameter: {e}"}
        elif filters is not None:
            parsed_filters = filters

        return await _nodes_tool.handle(
            operation=operation,
            node_type=node_type,
            node_id=node_id,
            data=parsed_data,
            filters=parsed_filters,
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
    properties: dict[str, Any] | str | None = None,
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
        properties: Relationship properties - can be dict or JSON string
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
    await _ensure_initialized()

    if not _relationships_tool:
        raise MCPKGSkillsError("Server not initialized")

    try:
        # Parse JSON string if provided
        parsed_properties: dict[str, Any] | None = None
        if isinstance(properties, str):
            try:
                parsed_properties = json.loads(properties)
                # Handle double-encoded JSON (e.g., "{}" as a string containing "{}")
                if isinstance(parsed_properties, str):
                    parsed_properties = json.loads(parsed_properties)
            except json.JSONDecodeError as e:
                return {"success": False, "error": f"Invalid JSON in properties parameter: {e}"}
        elif properties is not None:
            parsed_properties = properties

        return await _relationships_tool.handle(
            operation=operation,
            relationship_type=relationship_type,
            source_id=source_id,
            target_id=target_id,
            properties=parsed_properties,
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
    variables: dict[str, str] | str | None = None,
    keys: list[str] | str | None = None,
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
        variables: Environment variables - can be dict or JSON string
        keys: Variable keys to retrieve (for list_keys) - can be list or JSON string

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
    await _ensure_initialized()

    if not _env_tool:
        raise MCPKGSkillsError("Server not initialized")

    try:
        # Parse JSON strings if provided
        parsed_variables: dict[str, str] | None = None
        if isinstance(variables, str):
            try:
                parsed_variables = json.loads(variables)
            except json.JSONDecodeError as e:
                return {"success": False, "error": f"Invalid JSON in variables parameter: {e}"}
        elif variables is not None:
            parsed_variables = variables

        parsed_keys: list[str] | None = None
        if isinstance(keys, str):
            try:
                parsed_keys = json.loads(keys)
            except json.JSONDecodeError as e:
                return {"success": False, "error": f"Invalid JSON in keys parameter: {e}"}
        elif keys is not None:
            parsed_keys = keys

        return await _env_tool.handle(
            operation=operation,
            env_id=env_id,
            name=name,
            description=description,
            variables=parsed_variables,
            keys=parsed_keys,
        )
    except MCPKGSkillsError:
        raise
    except Exception as e:
        logger.error(f"env tool error: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool()
async def execute(
    code: str,
    imports: list[str] | str | None = None,
    envs: list[str] | str | None = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Execute Python code with dynamically imported functions from SCRIPT nodes.

    The system automatically:
    - Loads specified SCRIPT nodes
    - Merges their PEP 723 dependencies
    - Loads ENV variables from connected nodes AND directly specified envs
    - Executes code using 'uv run'
    - Sanitizes output to remove secret values

    IMPORTANT - How imports work:
        Scripts are CONCATENATED into a single file, NOT loaded as Python modules.
        All classes, functions, and variables defined in imported scripts are
        directly available in your code's namespace.

        WRONG: from my_script import MyClass  # Scripts are NOT modules!
        CORRECT: obj = MyClass()  # Class is already in scope

    Args:
        code: Python code to execute
        imports: List of SCRIPT node names to import - can be list or JSON string
        envs: List of ENV node names to load directly - can be list or JSON string
              (in addition to ENVs connected to imported scripts via CONTAINS)
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
            # Functions/classes from imported scripts are directly available
            # Do NOT use: from fetch_data import fetch_data
            data = fetch_data("https://api.example.com/data")
            df = process_data(data)
            print(df.head())
            \"\"\",
            imports=["fetch_data", "process_data"],
            timeout=60
        )
        ```

        Execute with direct ENV loading:
        ```
        execute(
            code=\"\"\"
            import os
            api_key = os.getenv("API_KEY")
            print(f"Using API key: {api_key[:4]}...")
            \"\"\",
            envs=["production-env"],
            timeout=10
        )
        ```
    """
    await _ensure_initialized()

    if not _execute_tool:
        raise MCPKGSkillsError("Server not initialized")

    try:
        # Parse JSON strings if provided
        parsed_imports: list[str] | None = None
        if isinstance(imports, str):
            try:
                parsed_imports = json.loads(imports)
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Invalid JSON in imports parameter: {e}",
                    "stdout": "",
                    "stderr": str(e),
                    "return_code": 1,
                    "execution_time": 0.0,
                }
        elif imports is not None:
            parsed_imports = imports

        parsed_envs: list[str] | None = None
        if isinstance(envs, str):
            try:
                parsed_envs = json.loads(envs)
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Invalid JSON in envs parameter: {e}",
                    "stdout": "",
                    "stderr": str(e),
                    "return_code": 1,
                    "execution_time": 0.0,
                }
        elif envs is not None:
            parsed_envs = envs

        return await _execute_tool.handle(
            code=code,
            imports=parsed_imports,
            envs=parsed_envs,
            timeout=min(timeout, _config.execution.max_timeout) if _config else timeout,
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
    parameters: dict[str, Any] | str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Execute read-only Cypher queries to explore the knowledge graph.

    Only MATCH, RETURN, WITH, WHERE, ORDER BY operations are allowed.
    Results are automatically sanitized to hide secret values.

    Args:
        cypher: Read-only Cypher query
        parameters: Query parameters - can be dict or JSON string
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
    await _ensure_initialized()

    if not _query_tool:
        raise MCPKGSkillsError("Server not initialized")

    try:
        # Parse JSON string if provided
        parsed_parameters: dict[str, Any] | None = None
        if isinstance(parameters, str):
            try:
                parsed_parameters = json.loads(parameters)
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Invalid JSON in parameters parameter: {e}",
                    "results": [],
                    "count": 0,
                }
        elif parameters is not None:
            parsed_parameters = parameters

        return await _query_tool.handle(
            cypher=cypher,
            parameters=parsed_parameters,
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
