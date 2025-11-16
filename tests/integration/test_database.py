"""Integration tests for Neo4j database layer."""

import pytest

from mcp_kg_skills.database.neo4j import Neo4jDatabase
from mcp_kg_skills.exceptions import (
    CircularDependencyError,
    NodeAlreadyExistsError,
    NodeNotFoundError,
)


@pytest.mark.asyncio
class TestDatabaseBasicOperations:
    """Test basic database CRUD operations."""

    async def test_create_node(self, clean_db: Neo4jDatabase, sample_skill_data):
        """Test creating a node."""
        node = await clean_db.create_node("SKILL", sample_skill_data)

        assert node["id"] is not None
        assert node["name"] == sample_skill_data["name"]
        assert node["description"] == sample_skill_data["description"]
        assert node["created_at"] is not None
        assert node["updated_at"] is not None

    async def test_create_duplicate_node_raises_error(
        self, clean_db: Neo4jDatabase, sample_skill_data
    ):
        """Test that creating duplicate node raises error."""
        await clean_db.create_node("SKILL", sample_skill_data)

        with pytest.raises(NodeAlreadyExistsError):
            await clean_db.create_node("SKILL", sample_skill_data)

    async def test_read_node(self, clean_db: Neo4jDatabase, sample_skill_data):
        """Test reading a node by ID."""
        created = await clean_db.create_node("SKILL", sample_skill_data)
        node_id = created["id"]

        node = await clean_db.read_node(node_id)

        assert node is not None
        assert node["id"] == node_id
        assert node["name"] == sample_skill_data["name"]

    async def test_read_nonexistent_node(self, clean_db: Neo4jDatabase):
        """Test reading a node that doesn't exist."""
        node = await clean_db.read_node("nonexistent-id")
        assert node is None

    async def test_read_node_by_name(self, clean_db: Neo4jDatabase, sample_skill_data):
        """Test reading a node by type and name."""
        await clean_db.create_node("SKILL", sample_skill_data)

        node = await clean_db.read_node_by_name("SKILL", sample_skill_data["name"])

        assert node is not None
        assert node["name"] == sample_skill_data["name"]

    async def test_update_node(self, clean_db: Neo4jDatabase, sample_skill_data):
        """Test updating a node."""
        created = await clean_db.create_node("SKILL", sample_skill_data)
        node_id = created["id"]

        updated = await clean_db.update_node(
            node_id, {"description": "Updated description"}
        )

        assert updated["description"] == "Updated description"
        assert updated["name"] == sample_skill_data["name"]

    async def test_update_nonexistent_node(self, clean_db: Neo4jDatabase):
        """Test updating a node that doesn't exist."""
        with pytest.raises(NodeNotFoundError):
            await clean_db.update_node("nonexistent-id", {"description": "test"})

    async def test_delete_node(self, clean_db: Neo4jDatabase, sample_skill_data):
        """Test deleting a node."""
        created = await clean_db.create_node("SKILL", sample_skill_data)
        node_id = created["id"]

        deleted = await clean_db.delete_node(node_id)
        assert deleted is True

        # Verify node is gone
        node = await clean_db.read_node(node_id)
        assert node is None

    async def test_delete_nonexistent_node(self, clean_db: Neo4jDatabase):
        """Test deleting a node that doesn't exist."""
        deleted = await clean_db.delete_node("nonexistent-id")
        assert deleted is False

    async def test_list_nodes(
        self, clean_db: Neo4jDatabase, sample_skill_data, sample_knowledge_data
    ):
        """Test listing nodes."""
        # Create multiple nodes
        await clean_db.create_node("SKILL", sample_skill_data)
        await clean_db.create_node(
            "SKILL",
            {**sample_skill_data, "name": "another-skill"},
        )
        await clean_db.create_node("KNOWLEDGE", sample_knowledge_data)

        # List all SKILLs
        skills = await clean_db.list_nodes("SKILL")

        assert len(skills) == 2
        assert all(s["name"] in ["test-skill", "another-skill"] for s in skills)

    async def test_list_nodes_with_filters(self, clean_db: Neo4jDatabase):
        """Test listing nodes with name filter."""
        # Create nodes with different names
        await clean_db.create_node(
            "SKILL",
            {"name": "data-pipeline", "description": "Test", "body": "Test"},
        )
        await clean_db.create_node(
            "SKILL",
            {"name": "web-scraper", "description": "Test", "body": "Test"},
        )
        await clean_db.create_node(
            "SKILL",
            {"name": "data-processor", "description": "Test", "body": "Test"},
        )

        # Filter by name containing "data"
        nodes = await clean_db.list_nodes("SKILL", filters={"name": "data"})

        assert len(nodes) == 2
        assert all("data" in node["name"] for node in nodes)

    async def test_list_nodes_pagination(self, clean_db: Neo4jDatabase):
        """Test listing nodes with pagination."""
        # Create multiple nodes
        for i in range(5):
            await clean_db.create_node(
                "SKILL",
                {"name": f"skill-{i}", "description": "Test", "body": "Test"},
            )

        # Get first page
        page1 = await clean_db.list_nodes("SKILL", limit=2, offset=0)
        assert len(page1) == 2

        # Get second page
        page2 = await clean_db.list_nodes("SKILL", limit=2, offset=2)
        assert len(page2) == 2

        # Ensure different nodes
        page1_ids = {n["id"] for n in page1}
        page2_ids = {n["id"] for n in page2}
        assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
class TestRelationships:
    """Test relationship operations."""

    async def test_create_relationship(
        self, clean_db: Neo4jDatabase, sample_skill_data, sample_script_data
    ):
        """Test creating a relationship."""
        skill = await clean_db.create_node("SKILL", sample_skill_data)
        script = await clean_db.create_node("SCRIPT", sample_script_data)

        rel = await clean_db.create_relationship(
            "CONTAINS", skill["id"], script["id"]
        )

        assert rel["type"] == "CONTAINS"
        assert rel["source_id"] == skill["id"]
        assert rel["target_id"] == script["id"]

    async def test_create_relationship_nonexistent_source(
        self, clean_db: Neo4jDatabase, sample_script_data
    ):
        """Test creating relationship with nonexistent source."""
        script = await clean_db.create_node("SCRIPT", sample_script_data)

        with pytest.raises(NodeNotFoundError):
            await clean_db.create_relationship(
                "CONTAINS", "nonexistent-id", script["id"]
            )

    async def test_create_relationship_nonexistent_target(
        self, clean_db: Neo4jDatabase, sample_skill_data
    ):
        """Test creating relationship with nonexistent target."""
        skill = await clean_db.create_node("SKILL", sample_skill_data)

        with pytest.raises(NodeNotFoundError):
            await clean_db.create_relationship(
                "CONTAINS", skill["id"], "nonexistent-id"
            )

    async def test_circular_dependency_detection(
        self, clean_db: Neo4jDatabase, sample_skill_data
    ):
        """Test circular dependency detection for CONTAINS relationships."""
        # Create chain: skill1 -> skill2 -> skill3
        skill1 = await clean_db.create_node(
            "SKILL", {**sample_skill_data, "name": "skill1"}
        )
        skill2 = await clean_db.create_node(
            "SKILL", {**sample_skill_data, "name": "skill2"}
        )
        skill3 = await clean_db.create_node(
            "SKILL", {**sample_skill_data, "name": "skill3"}
        )

        await clean_db.create_relationship("CONTAINS", skill1["id"], skill2["id"])
        await clean_db.create_relationship("CONTAINS", skill2["id"], skill3["id"])

        # Try to create circular dependency: skill3 -> skill1
        with pytest.raises(CircularDependencyError):
            await clean_db.create_relationship("CONTAINS", skill3["id"], skill1["id"])

    async def test_relate_to_allows_cycles(
        self, clean_db: Neo4jDatabase, sample_skill_data
    ):
        """Test that RELATE_TO relationships can form cycles."""
        skill1 = await clean_db.create_node(
            "SKILL", {**sample_skill_data, "name": "skill1"}
        )
        skill2 = await clean_db.create_node(
            "SKILL", {**sample_skill_data, "name": "skill2"}
        )

        # Create bidirectional RELATE_TO (this should work)
        rel1 = await clean_db.create_relationship(
            "RELATE_TO", skill1["id"], skill2["id"]
        )
        rel2 = await clean_db.create_relationship(
            "RELATE_TO", skill2["id"], skill1["id"]
        )

        assert rel1 is not None
        assert rel2 is not None

    async def test_list_relationships(
        self, clean_db: Neo4jDatabase, sample_skill_data, sample_script_data
    ):
        """Test listing relationships."""
        skill = await clean_db.create_node("SKILL", sample_skill_data)
        script1 = await clean_db.create_node(
            "SCRIPT", {**sample_script_data, "name": "script1"}
        )
        script2 = await clean_db.create_node(
            "SCRIPT", {**sample_script_data, "name": "script2"}
        )

        await clean_db.create_relationship("CONTAINS", skill["id"], script1["id"])
        await clean_db.create_relationship("CONTAINS", skill["id"], script2["id"])

        # List all relationships from skill
        rels = await clean_db.list_relationships(source_id=skill["id"])

        assert len(rels) == 2
        assert all(r["source_id"] == skill["id"] for r in rels)

    async def test_delete_relationship(
        self, clean_db: Neo4jDatabase, sample_skill_data, sample_script_data
    ):
        """Test deleting a relationship."""
        skill = await clean_db.create_node("SKILL", sample_skill_data)
        script = await clean_db.create_node("SCRIPT", sample_script_data)

        rel = await clean_db.create_relationship(
            "CONTAINS", skill["id"], script["id"]
        )

        deleted = await clean_db.delete_relationship(rel["id"])
        assert deleted is True

        # Verify relationship is gone
        rels = await clean_db.list_relationships(source_id=skill["id"])
        assert len(rels) == 0

    async def test_delete_relationships_by_criteria(
        self, clean_db: Neo4jDatabase, sample_skill_data, sample_script_data
    ):
        """Test deleting relationships by source/target."""
        skill = await clean_db.create_node("SKILL", sample_skill_data)
        script = await clean_db.create_node("SCRIPT", sample_script_data)

        await clean_db.create_relationship("CONTAINS", skill["id"], script["id"])

        count = await clean_db.delete_relationships(
            source_id=skill["id"], target_id=script["id"]
        )

        assert count == 1

    async def test_get_connected_nodes(
        self, clean_db: Neo4jDatabase, sample_skill_data, sample_script_data
    ):
        """Test getting nodes connected via relationships."""
        skill = await clean_db.create_node("SKILL", sample_skill_data)
        script1 = await clean_db.create_node(
            "SCRIPT", {**sample_script_data, "name": "script1"}
        )
        script2 = await clean_db.create_node(
            "SCRIPT", {**sample_script_data, "name": "script2"}
        )

        await clean_db.create_relationship("CONTAINS", skill["id"], script1["id"])
        await clean_db.create_relationship("CONTAINS", skill["id"], script2["id"])

        # Get outgoing connections
        connected = await clean_db.get_connected_nodes(
            skill["id"], rel_type="CONTAINS", direction="outgoing"
        )

        assert len(connected) == 2
        assert all(n["name"] in ["script1", "script2"] for n in connected)


@pytest.mark.asyncio
class TestQueryExecution:
    """Test Cypher query execution."""

    async def test_execute_simple_query(
        self, clean_db: Neo4jDatabase, sample_skill_data
    ):
        """Test executing a simple read-only query."""
        await clean_db.create_node("SKILL", sample_skill_data)
        await clean_db.create_node(
            "SKILL", {**sample_skill_data, "name": "another-skill"}
        )

        results = await clean_db.execute_query(
            "MATCH (s:SKILL) RETURN s.name as name ORDER BY s.name"
        )

        assert len(results) == 2
        assert results[0]["name"] == "another-skill"
        assert results[1]["name"] == "test-skill"

    async def test_execute_query_with_parameters(
        self, clean_db: Neo4jDatabase, sample_skill_data
    ):
        """Test query with parameters."""
        await clean_db.create_node("SKILL", sample_skill_data)

        results = await clean_db.execute_query(
            "MATCH (s:SKILL {name: $name}) RETURN s.description as desc",
            parameters={"name": sample_skill_data["name"]},
        )

        assert len(results) == 1
        assert results[0]["desc"] == sample_skill_data["description"]

    async def test_execute_query_limit(
        self, clean_db: Neo4jDatabase, sample_skill_data
    ):
        """Test query result limiting."""
        # Create 5 nodes
        for i in range(5):
            await clean_db.create_node(
                "SKILL", {**sample_skill_data, "name": f"skill-{i}"}
            )

        results = await clean_db.execute_query(
            "MATCH (s:SKILL) RETURN s.name", limit=3
        )

        assert len(results) == 3

    async def test_readonly_query_validation(self, clean_db: Neo4jDatabase):
        """Test that write queries are rejected."""
        from mcp_kg_skills.exceptions import InvalidQueryError

        with pytest.raises(InvalidQueryError):
            await clean_db.execute_query("CREATE (n:TEST) RETURN n")

        with pytest.raises(InvalidQueryError):
            await clean_db.execute_query("MATCH (n) DELETE n")

        with pytest.raises(InvalidQueryError):
            await clean_db.execute_query("MATCH (n) SET n.prop = 'value'")


@pytest.mark.asyncio
class TestDatabaseSchemaInitialization:
    """Test database schema initialization."""

    async def test_initialize_schema(self, clean_db: Neo4jDatabase):
        """Test that schema initialization creates constraints."""
        # Schema is initialized in fixture, verify it worked
        async with clean_db.driver.session(database=clean_db.database) as session:
            result = await session.run("SHOW CONSTRAINTS")
            constraints = await result.values()

            # Should have constraints for SKILL, SCRIPT, ENV names
            assert len(constraints) >= 3

    async def test_health_check(self, clean_db: Neo4jDatabase):
        """Test database health check."""
        is_healthy = await clean_db.health_check()
        assert is_healthy is True
