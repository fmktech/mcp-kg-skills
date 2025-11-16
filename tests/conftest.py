"""Pytest configuration and fixtures for MCP Knowledge Graph Skills tests."""

import asyncio
import os
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from neo4j import AsyncGraphDatabase

from mcp_kg_skills.config import AppConfig, DatabaseConfig, ExecutionConfig
from mcp_kg_skills.database.neo4j import Neo4jDatabase
from mcp_kg_skills.execution.runner import ScriptRunner
from mcp_kg_skills.security.secrets import SecretDetector
from mcp_kg_skills.utils.env_file import EnvFileManager


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set event loop policy for async tests."""
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session")
def test_config() -> AppConfig:
    """Create test configuration."""
    return AppConfig(
        database=DatabaseConfig(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7688"),
            username="neo4j",
            password=os.getenv("NEO4J_PASSWORD", "testpassword"),
            database="neo4j",
        ),
        execution=ExecutionConfig(
            cache_dir=Path(".mcp-kg-skills-test/cache"),
            env_dir=Path(".mcp-kg-skills-test/envs"),
            default_timeout=60,
            max_timeout=120,
        ),
    )


@pytest_asyncio.fixture
async def db(test_config: AppConfig) -> AsyncGenerator[Neo4jDatabase, None]:
    """Create and initialize test database connection."""
    database = Neo4jDatabase(
        uri=test_config.database.uri,
        username=test_config.database.username,
        password=test_config.database.password,
        database=test_config.database.database,
    )

    await database.connect()
    await database.initialize_schema()

    yield database

    # Cleanup: Delete all nodes and relationships
    async with database.driver.session(database=database.database) as session:
        await session.run("MATCH (n) DETACH DELETE n")

    await database.disconnect()


@pytest_asyncio.fixture
async def clean_db(db: Neo4jDatabase) -> AsyncGenerator[Neo4jDatabase, None]:
    """Provide a clean database for each test."""
    # Clean before test
    async with db.driver.session(database=db.database) as session:
        await session.run("MATCH (n) DETACH DELETE n")

    yield db

    # Clean after test
    async with db.driver.session(database=db.database) as session:
        await session.run("MATCH (n) DETACH DELETE n")


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create temporary directory for tests."""
    test_dir = tmp_path / "mcp-kg-skills-test"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


@pytest.fixture
def env_manager(temp_dir: Path) -> EnvFileManager:
    """Create environment file manager for tests."""
    env_dir = temp_dir / "envs"
    env_dir.mkdir(parents=True, exist_ok=True)
    return EnvFileManager(env_dir)


@pytest.fixture
def secret_detector() -> SecretDetector:
    """Create secret detector for tests."""
    return SecretDetector()


@pytest_asyncio.fixture
async def script_runner(
    clean_db: Neo4jDatabase, temp_dir: Path, secret_detector: SecretDetector
) -> ScriptRunner:
    """Create script runner for tests."""
    cache_dir = temp_dir / "cache"
    env_dir = temp_dir / "envs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    env_dir.mkdir(parents=True, exist_ok=True)

    return ScriptRunner(
        db=clean_db,
        cache_dir=cache_dir,
        env_dir=env_dir,
        secret_detector=secret_detector,
    )


@pytest.fixture
def sample_skill_data() -> dict:
    """Sample SKILL node data."""
    return {
        "name": "test-skill",
        "description": "A test skill for integration tests",
        "body": "# Test Skill\n\nThis is a test skill.",
    }


@pytest.fixture
def sample_knowledge_data() -> dict:
    """Sample KNOWLEDGE node data."""
    return {
        "name": "test-knowledge",
        "description": "Test knowledge documentation",
        "body": "# Test Knowledge\n\nSome documentation.",
    }


@pytest.fixture
def sample_script_data() -> dict:
    """Sample SCRIPT node data."""
    return {
        "name": "test_script",
        "description": "A test script function",
        "function_signature": "test_function(x: int) -> int",
        "body": """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

def test_function(x: int) -> int:
    return x * 2
""",
    }


@pytest.fixture
def sample_script_with_deps_data() -> dict:
    """Sample SCRIPT node with dependencies."""
    return {
        "name": "fetch_data",
        "description": "Fetch data from URL",
        "function_signature": "fetch_data(url: str) -> str",
        "body": """# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "requests>=2.31.0",
# ]
# ///

import requests

def fetch_data(url: str) -> str:
    response = requests.get(url)
    return response.text
""",
    }


@pytest.fixture
def sample_env_data() -> dict:
    """Sample ENV node data."""
    return {
        "name": "test-env",
        "description": "Test environment variables",
        "variables": {
            "DATABASE_HOST": "localhost",
            "DATABASE_PORT": "5432",
            "DATABASE_PASSWORD": "secret123",  # Will be detected as secret
            "API_KEY": "test-api-key",  # Will be detected as secret
        },
    }


@pytest.fixture(autouse=True)
def cleanup_test_dirs(temp_dir: Path):
    """Cleanup test directories after each test."""
    yield

    # Cleanup
    import shutil

    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
