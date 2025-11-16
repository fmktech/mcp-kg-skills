"""End-to-end integration tests for complete workflows."""

import os

import pytest

from mcp_kg_skills.database.abstract import DatabaseInterface
from mcp_kg_skills.execution.runner import ScriptRunner
from mcp_kg_skills.security.secrets import SecretDetector
from mcp_kg_skills.tools.env import EnvTool
from mcp_kg_skills.tools.execute import ExecuteTool
from mcp_kg_skills.tools.nodes import NodesTool
from mcp_kg_skills.tools.relationships import RelationshipsTool
from mcp_kg_skills.utils.env_file import EnvFileManager

# Check if we're using Neo4j or SQLite
IS_NEO4J = os.getenv("TEST_DB") == "neo4j"


@pytest.mark.asyncio
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    async def test_simple_script_execution(
        self, clean_db: DatabaseInterface, script_runner: ScriptRunner
    ):
        """Test creating and executing a simple script."""
        # Create a simple script
        script_data = {
            "name": "greet",
            "description": "Greeting function",
            "function_signature": "greet(name: str) -> str",
            "body": """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

def greet(name: str) -> str:
    return f"Hello, {name}!"
""",
        }

        created = await clean_db.create_node("SCRIPT", script_data)
        assert created["id"] is not None

        # Execute code using the script
        result = await script_runner.execute(
            code='print(greet("World"))',
            imports=["greet"],
            timeout=30,
        )

        assert result["success"] is True
        assert "Hello, World!" in result["stdout"]
        assert result["return_code"] == 0

    async def test_multi_script_composition(
        self, clean_db: DatabaseInterface, script_runner: ScriptRunner
    ):
        """Test composing and executing multiple scripts."""
        # Create first script
        script1 = {
            "name": "add",
            "description": "Add two numbers",
            "function_signature": "add(a: int, b: int) -> int",
            "body": """# /// script
# requires-python = ">=3.12"
# ///

def add(a: int, b: int) -> int:
    return a + b
""",
        }

        # Create second script
        script2 = {
            "name": "multiply",
            "description": "Multiply two numbers",
            "function_signature": "multiply(a: int, b: int) -> int",
            "body": """# /// script
# requires-python = ">=3.12"
# ///

def multiply(a: int, b: int) -> int:
    return a * b
""",
        }

        await clean_db.create_node("SCRIPT", script1)
        await clean_db.create_node("SCRIPT", script2)

        # Execute code using both scripts
        result = await script_runner.execute(
            code="""
result = multiply(add(2, 3), 4)
print(f"Result: {result}")
""",
            imports=["add", "multiply"],
            timeout=30,
        )

        assert result["success"] is True
        assert "Result: 20" in result["stdout"]

    async def test_skill_with_scripts_and_env(
        self,
        clean_db: DatabaseInterface,
        env_manager: EnvFileManager,
        secret_detector: SecretDetector,
        script_runner: ScriptRunner,
        temp_dir,
    ):
        """Test complete skill with scripts and environment variables."""
        # Create tools
        nodes_tool = NodesTool(clean_db, env_manager, secret_detector)
        relationships_tool = RelationshipsTool(clean_db)
        env_tool = EnvTool(clean_db, env_manager, secret_detector)

        # 1. Create a SKILL
        skill_result = await nodes_tool.handle(
            operation="create",
            node_type="SKILL",
            data={
                "name": "greeting-skill",
                "description": "Greeting utilities",
                "body": "# Greeting Skill\n\nProvides greeting functions",
            },
        )
        skill_id = skill_result["node"]["id"]

        # 2. Create a SCRIPT
        script_result = await nodes_tool.handle(
            operation="create",
            node_type="SCRIPT",
            data={
                "name": "greet_user",
                "description": "Greet a user",
                "function_signature": "greet_user(name: str) -> str",
                "body": """# /// script
# requires-python = ">=3.12"
# ///

import os

def greet_user(name: str) -> str:
    prefix = os.getenv('GREETING_PREFIX', 'Hello')
    return f"{prefix}, {name}!"
""",
            },
        )
        script_id = script_result["node"]["id"]

        # 3. Create ENV
        env_result = await env_tool.handle(
            operation="create",
            name="greeting-env",
            description="Greeting configuration",
            variables={
                "GREETING_PREFIX": "Welcome",
                "SECRET_KEY": "my-secret",  # Will be detected as secret
            },
        )
        env_id = env_result["node"]["id"]

        # 4. Create relationships
        await relationships_tool.handle(
            operation="create",
            relationship_type="CONTAINS",
            source_id=skill_id,
            target_id=script_id,
        )

        await relationships_tool.handle(
            operation="create",
            relationship_type="CONTAINS",
            source_id=script_id,
            target_id=env_id,
        )

        # 5. Execute the script
        result = await script_runner.execute(
            code='print(greet_user("Alice"))',
            imports=["greet_user"],
            timeout=30,
        )

        assert result["success"] is True
        assert "Welcome, Alice!" in result["stdout"]
        # Verify secret is NOT in output
        assert "my-secret" not in result["stdout"]

    async def test_dependency_merging(
        self, clean_db: DatabaseInterface, script_runner: ScriptRunner
    ):
        """Test that dependencies from multiple scripts are merged."""
        # Create scripts with different dependencies
        script1 = {
            "name": "script_a",
            "description": "Script with dependency A",
            "function_signature": "func_a() -> str",
            "body": """# /// script
# dependencies = ["requests>=2.31.0"]
# ///

def func_a() -> str:
    return "A"
""",
        }

        script2 = {
            "name": "script_b",
            "description": "Script with dependency B",
            "function_signature": "func_b() -> str",
            "body": """# /// script
# dependencies = ["pyyaml>=6.0"]
# ///

def func_b() -> str:
    return "B"
""",
        }

        await clean_db.create_node("SCRIPT", script1)
        await clean_db.create_node("SCRIPT", script2)

        # Execute will merge dependencies
        result = await script_runner.execute(
            code='print(func_a() + func_b())',
            imports=["script_a", "script_b"],
            timeout=60,  # Longer timeout for dependency installation
        )

        assert result["success"] is True
        assert "AB" in result["stdout"]

    @pytest.mark.skipif(not IS_NEO4J, reason="Cypher queries only supported on Neo4j")
    async def test_query_graph_structure(
        self,
        clean_db: DatabaseInterface,
        env_manager: EnvFileManager,
        secret_detector: SecretDetector,
    ):
        """Test querying the graph structure."""
        nodes_tool = NodesTool(clean_db, env_manager, secret_detector)
        relationships_tool = RelationshipsTool(clean_db)

        # Create a graph structure
        skill = await nodes_tool.handle(
            operation="create",
            node_type="SKILL",
            data={
                "name": "test-skill",
                "description": "Test",
                "body": "Test",
            },
        )

        script1 = await nodes_tool.handle(
            operation="create",
            node_type="SCRIPT",
            data={
                "name": "script1",
                "description": "Script 1",
                "function_signature": "f1()",
                "body": "def f1(): pass",
            },
        )

        script2 = await nodes_tool.handle(
            operation="create",
            node_type="SCRIPT",
            data={
                "name": "script2",
                "description": "Script 2",
                "function_signature": "f2()",
                "body": "def f2(): pass",
            },
        )

        # Create relationships
        await relationships_tool.handle(
            operation="create",
            relationship_type="CONTAINS",
            source_id=skill["node"]["id"],
            target_id=script1["node"]["id"],
        )

        await relationships_tool.handle(
            operation="create",
            relationship_type="CONTAINS",
            source_id=skill["node"]["id"],
            target_id=script2["node"]["id"],
        )

        # Query the structure
        results = await clean_db.execute_query(
            """
            MATCH (skill:SKILL {name: $skill_name})-[:CONTAINS]->(script:SCRIPT)
            RETURN script.name as script_name
            ORDER BY script_name
            """,
            parameters={"skill_name": "test-skill"},
        )

        assert len(results) == 2
        assert results[0]["script_name"] == "script1"
        assert results[1]["script_name"] == "script2"

    async def test_secret_sanitization_throughout_flow(
        self,
        clean_db: DatabaseInterface,
        env_manager: EnvFileManager,
        secret_detector: SecretDetector,
        script_runner: ScriptRunner,
    ):
        """Test that secrets are sanitized throughout the entire flow."""
        nodes_tool = NodesTool(clean_db, env_manager, secret_detector)
        env_tool = EnvTool(clean_db, env_manager, secret_detector)

        # Create ENV with secrets
        env_result = await env_tool.handle(
            operation="create",
            name="secret-env",
            description="Environment with secrets",
            variables={
                "PUBLIC_VAR": "public-value",
                "SECRET_KEY": "super-secret-123",
                "API_PASSWORD": "password-456",
            },
        )
        env_id = env_result["node"]["id"]

        # Verify secrets are masked in read response
        read_result = await env_tool.handle(operation="read", env_id=env_id)

        env_node = read_result["node"]
        assert env_node["variables"]["PUBLIC_VAR"] == "public-value"
        assert env_node["variables"]["SECRET_KEY"] == "<SECRET>"
        assert env_node["variables"]["API_PASSWORD"] == "<SECRET>"

        # Create script that uses environment
        script_result = await nodes_tool.handle(
            operation="create",
            node_type="SCRIPT",
            data={
                "name": "use_env",
                "description": "Use environment variables",
                "function_signature": "use_env()",
                "body": """# /// script
# requires-python = ">=3.12"
# ///

import os

def use_env():
    secret = os.getenv('SECRET_KEY', 'not-found')
    password = os.getenv('API_PASSWORD', 'not-found')
    print(f"Secret: {secret}")
    print(f"Password: {password}")
""",
            },
        )
        script_id = script_result["node"]["id"]

        # Link script to env
        await clean_db.create_relationship("CONTAINS", script_id, env_id)

        # Execute script
        result = await script_runner.execute(
            code="use_env()",
            imports=["use_env"],
            timeout=30,
        )

        # Verify execution succeeded
        assert result["success"] is True

        # Verify secrets are sanitized in output
        assert "super-secret-123" not in result["stdout"]
        assert "password-456" not in result["stdout"]
        assert "<REDACTED>" in result["stdout"]

    async def test_error_handling_in_execution(
        self, clean_db: DatabaseInterface, script_runner: ScriptRunner
    ):
        """Test error handling during script execution."""
        # Create script with error
        script_data = {
            "name": "error_script",
            "description": "Script that raises error",
            "function_signature": "raise_error()",
            "body": """# /// script
# requires-python = ">=3.12"
# ///

def raise_error():
    raise ValueError("Test error")
""",
        }

        await clean_db.create_node("SCRIPT", script_data)

        # Execute script that will error
        result = await script_runner.execute(
            code="raise_error()",
            imports=["error_script"],
            timeout=30,
        )

        assert result["success"] is False
        assert result["return_code"] != 0
        assert "ValueError" in result["stderr"] or "ValueError" in result["stdout"]

    async def test_timeout_handling(
        self, clean_db: DatabaseInterface, script_runner: ScriptRunner
    ):
        """Test that script execution respects timeout."""
        script_data = {
            "name": "slow_script",
            "description": "Slow script",
            "function_signature": "slow_func()",
            "body": """# /// script
# requires-python = ">=3.12"
# ///

import time

def slow_func():
    time.sleep(10)
    print("Done")
""",
        }

        await clean_db.create_node("SCRIPT", script_data)

        # Execute with short timeout
        from mcp_kg_skills.exceptions import ScriptExecutionError

        with pytest.raises(ScriptExecutionError, match="timed out"):
            await script_runner.execute(
                code="slow_func()",
                imports=["slow_script"],
                timeout=2,  # Short timeout
            )


@pytest.mark.asyncio
class TestComplexWorkflows:
    """Test more complex real-world workflows."""

    async def test_data_pipeline_workflow(
        self,
        clean_db: DatabaseInterface,
        env_manager: EnvFileManager,
        secret_detector: SecretDetector,
        script_runner: ScriptRunner,
    ):
        """Test a complete data pipeline workflow."""
        nodes_tool = NodesTool(clean_db, env_manager, secret_detector)
        relationships_tool = RelationshipsTool(clean_db)

        # Create skill
        skill_result = await nodes_tool.handle(
            operation="create",
            node_type="SKILL",
            data={
                "name": "data-pipeline",
                "description": "Data processing pipeline",
                "body": "# Data Pipeline\n\nETL operations",
            },
        )
        skill_id = skill_result["node"]["id"]

        # Create extract script
        extract_result = await nodes_tool.handle(
            operation="create",
            node_type="SCRIPT",
            data={
                "name": "extract_data",
                "description": "Extract data",
                "function_signature": "extract_data() -> list",
                "body": """# /// script
# requires-python = ">=3.12"
# ///

def extract_data() -> list:
    return [1, 2, 3, 4, 5]
""",
            },
        )

        # Create transform script
        transform_result = await nodes_tool.handle(
            operation="create",
            node_type="SCRIPT",
            data={
                "name": "transform_data",
                "description": "Transform data",
                "function_signature": "transform_data(data: list) -> list",
                "body": """# /// script
# requires-python = ">=3.12"
# ///

def transform_data(data: list) -> list:
    return [x * 2 for x in data]
""",
            },
        )

        # Create load script
        load_result = await nodes_tool.handle(
            operation="create",
            node_type="SCRIPT",
            data={
                "name": "load_data",
                "description": "Load data",
                "function_signature": "load_data(data: list) -> None",
                "body": """# /// script
# requires-python = ">=3.12"
# ///

def load_data(data: list) -> None:
    print(f"Loaded {len(data)} items: {data}")
""",
            },
        )

        # Link all scripts to skill
        for script_result in [extract_result, transform_result, load_result]:
            await relationships_tool.handle(
                operation="create",
                relationship_type="CONTAINS",
                source_id=skill_id,
                target_id=script_result["node"]["id"],
            )

        # Execute complete pipeline
        result = await script_runner.execute(
            code="""
# ETL Pipeline
data = extract_data()
transformed = transform_data(data)
load_data(transformed)
""",
            imports=["extract_data", "transform_data", "load_data"],
            timeout=30,
        )

        assert result["success"] is True
        assert "Loaded 5 items: [2, 4, 6, 8, 10]" in result["stdout"]
