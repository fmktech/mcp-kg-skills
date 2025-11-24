# MCP Knowledge Graph Skills

A Model Context Protocol (MCP) server that manages a graph of reusable Python functions, documentation, and environment variables. Claude can dynamically compose and execute scripts by importing functions from the graph.

## Features

- **Graph-Based Knowledge Management**: Organize skills, scripts, documentation, and environments in a Neo4j knowledge graph
- **Dynamic Script Composition**: Import and combine Python functions at execution time
- **Automatic Dependency Management**: PEP 723 inline script metadata with uv-powered execution
- **Secret Protection**: Automatic detection and sanitization of sensitive environment variables
- **Relationship Tracking**: Connect related skills and resources with CONTAINS and RELATE_TO relationships
- **Flexible Querying**: Explore the knowledge graph using read-only Cypher queries

## Architecture

```
┌─────────────────────────────────────────────────────┐
│         LLM (Claude via MCP Client)                 │
└─────────────────┬───────────────────────────────────┘
                  │ MCP Protocol (FastMCP 2.10)
┌─────────────────▼───────────────────────────────────┐
│  MCP Server (mcp-kg-skills)                         │
│  ┌───────────────────────────────────────────────┐  │
│  │  Tools: nodes, relationships, env,            │  │
│  │         execute, query                        │  │
│  └────────────────┬──────────────────────────────┘  │
│  ┌────────────────▼──────────────────────────────┐  │
│  │  Script Executor + Secret Protection          │  │
│  │  (uv run + PEP 723)                           │  │
│  └────────────────┬──────────────────────────────┘  │
│  ┌────────────────▼──────────────────────────────┐  │
│  │  Neo4j Database Interface                     │  │
│  └────────────────┬──────────────────────────────┘  │
└───────────────────┼───────────────────────────────┘
                    │
┌───────────────────▼───────────────────────────────┐
│  Neo4j Graph Database                             │
│  Nodes: SKILL, KNOWLEDGE, SCRIPT, ENV             │
│  Relationships: CONTAINS, RELATE_TO               │
└───────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) - Fast Python package installer
- Neo4j 4.4+, 5.x, or 2025.x
- MCP-compatible client (e.g., Claude Desktop)

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Install MCP Knowledge Graph Skills

```bash
# Clone the repository
git clone https://github.com/yourusername/mcp-kg-skills.git
cd mcp-kg-skills

# Install with uv
uv pip install -e .
```

### Install Neo4j

#### Option 1: Docker (Recommended)

```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:latest
```

#### Option 2: Neo4j Desktop

Download from [neo4j.com/download](https://neo4j.com/download/)

#### Option 3: Neo4j Aura (Cloud)

Sign up at [console.neo4j.io](https://console.neo4j.io)

## Configuration

### 1. Create Configuration File

```bash
# Create config directory in home
mkdir -p ~/.mcp-kg-skills/config

# Copy example configuration to home directory
cp .mcp-kg-skills/config/database.yaml.example \
   ~/.mcp-kg-skills/config/database.yaml
```

### 2. Edit Configuration

Edit `~/.mcp-kg-skills/config/database.yaml`:

```yaml
database:
  uri: "bolt://localhost:7687"
  username: "neo4j"
  password: "${NEO4J_PASSWORD}"  # Or set directly: "your-password"
  database: "neo4j"

execution:
  cache_dir: "~/.mcp-kg-skills/cache"
  env_dir: "~/.mcp-kg-skills/envs"
  default_timeout: 300
  max_timeout: 600

security:
  secret_patterns:
    - "SECRET_*"
    - "*_SECRET"
    - "*_KEY"
    - "*_PASSWORD"
    - "*_TOKEN"
    - "*_API_KEY"
    - "*_PRIVATE_KEY"

logging:
  level: "INFO"
```

### 3. Set Environment Variables

```bash
# Set Neo4j password
export NEO4J_PASSWORD="your-password"
```

## MCP Client Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "mcp-kg-skills": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/mcp-kg-skills",
        "run",
        "mcp-kg-skills"
      ],
      "env": {
        "NEO4J_PASSWORD": "your-password"
      }
    }
  }
}
```

## Usage

### Node Types

#### SKILL - High-level organizational unit
```python
{
    "name": "data-pipeline",
    "description": "ETL pipeline for data processing",
    "body": "# Data Pipeline\n\nMarkdown content..."
}
```

#### KNOWLEDGE - Documentation and context
```python
{
    "name": "api-documentation",
    "description": "REST API documentation",
    "body": "# API Docs\n\nMarkdown content..."
}
```

#### SCRIPT - Python functions with PEP 723 dependencies
```python
{
    "name": "fetch_data",
    "description": "Fetch data from API",
    "function_signature": "fetch_data(url: str) -> dict",
    "body": """
# /// script
# requires-python = ">=3.12"
# dependencies = ["requests>=2.31.0"]
# ///

import requests

def fetch_data(url: str) -> dict:
    response = requests.get(url)
    response.raise_for_status()
    return response.json()
"""
}
```

#### ENV - Environment variable collections
```python
{
    "name": "production",
    "description": "Production environment variables",
    "variables": {
        "DATABASE_HOST": "prod.db.example.com",
        "DATABASE_PORT": "5432",
        "DATABASE_PASSWORD": "secret123"  # Auto-detected as secret
    }
}
```

### MCP Tools

#### 1. nodes - Manage nodes

**Create a SKILL:**
```python
nodes(
    operation="create",
    node_type="SKILL",
    data={
        "name": "data-pipeline",
        "description": "ETL data processing pipeline",
        "body": "# Data Pipeline\n\nThis skill manages ETL processes..."
    }
)
```

**Create a SCRIPT:**
```python
nodes(
    operation="create",
    node_type="SCRIPT",
    data={
        "name": "fetch_data",
        "description": "Fetch JSON data from URL",
        "function_signature": "fetch_data(url: str) -> dict",
        "body": """
# /// script
# requires-python = ">=3.12"
# dependencies = ["requests>=2.31.0"]
# ///

import requests

def fetch_data(url: str) -> dict:
    response = requests.get(url)
    return response.json()
"""
    }
)
```

**List nodes:**
```python
nodes(
    operation="list",
    node_type="SCRIPT",
    filters={"name": "fetch", "limit": 10}
)
```

**Read a node:**
```python
nodes(
    operation="read",
    node_type="SCRIPT",
    node_id="script-123"
)
```

**Update a node:**
```python
nodes(
    operation="update",
    node_type="SCRIPT",
    node_id="script-123",
    data={"description": "Updated description"}
)
```

**Delete a node:**
```python
nodes(
    operation="delete",
    node_type="SCRIPT",
    node_id="script-123"
)
```

#### 2. relationships - Manage relationships

**Create CONTAINS relationship:**
```python
relationships(
    operation="create",
    relationship_type="CONTAINS",
    source_id="skill-123",
    target_id="script-456"
)
```

**Create RELATE_TO relationship:**
```python
relationships(
    operation="create",
    relationship_type="RELATE_TO",
    source_id="skill-123",
    target_id="skill-789",
    properties={"reason": "related functionality"}
)
```

**List relationships:**
```python
relationships(
    operation="list",
    source_id="skill-123"
)
```

**Delete relationship:**
```python
relationships(
    operation="delete",
    rel_id="rel-123"
)
```

#### 3. env - Manage environment variables

**Create environment:**
```python
env(
    operation="create",
    name="production",
    description="Production environment",
    variables={
        "DATABASE_HOST": "prod.db.example.com",
        "DATABASE_PASSWORD": "secret123",  # Auto-detected as secret
        "API_KEY": "abc123xyz"  # Auto-detected as secret
    }
)
```

**Read environment (secrets masked):**
```python
env(
    operation="read",
    env_id="env-123"
)
# Returns: {"DATABASE_HOST": "prod.db.example.com", "DATABASE_PASSWORD": "<SECRET>", ...}
```

**Update environment:**
```python
env(
    operation="update",
    env_id="env-123",
    variables={"NEW_VAR": "value"}
)
```

**List variable keys only:**
```python
env(
    operation="list_keys",
    env_id="env-123"
)
```

#### 4. execute - Execute Python code

**Execute with imported scripts:**
```python
execute(
    code="""
# Imported functions are available by name
data = fetch_data("https://api.example.com/users")
processed = process_users(data)
print(f"Processed {len(processed)} users")
""",
    imports=["fetch_data", "process_users"],
    timeout=60
)
```

**Execute standalone code:**
```python
execute(
    code="print('Hello, World!')",
    timeout=10
)
```

#### 5. query - Query the graph

**Find scripts in a skill:**
```cypher
query(
    cypher="""
    MATCH (s:SKILL {name: $skill_name})-[:CONTAINS]->(script:SCRIPT)
    RETURN script.name, script.function_signature
    """,
    parameters={"skill_name": "data-pipeline"}
)
```

**Find skills using an environment:**
```cypher
query(
    cypher="""
    MATCH (script:SCRIPT)-[:CONTAINS]->(env:ENV {name: $env_name})
    MATCH (skill:SKILL)-[:CONTAINS]->(script)
    RETURN DISTINCT skill.name, skill.description
    """,
    parameters={"env_name": "production"}
)
```

**Explore related skills:**
```cypher
query(
    cypher="""
    MATCH (s1:SKILL)-[:RELATE_TO]-(s2:SKILL)
    WHERE s1.name = $name
    RETURN s2.name, s2.description
    """,
    parameters={"name": "etl-pipeline"}
)
```

## Example Workflow

### 1. Create a Skill

```python
# Create skill
nodes(
    operation="create",
    node_type="SKILL",
    data={
        "name": "web-scraper",
        "description": "Web scraping utilities",
        "body": "# Web Scraper\n\nUtilities for web scraping..."
    }
)
# Returns: {"success": true, "node": {"id": "skill-abc123", ...}}
```

### 2. Create Scripts

```python
# Fetch HTML
nodes(
    operation="create",
    node_type="SCRIPT",
    data={
        "name": "fetch_html",
        "description": "Fetch HTML from URL",
        "function_signature": "fetch_html(url: str) -> str",
        "body": """
# /// script
# requires-python = ">=3.12"
# dependencies = ["requests>=2.31.0"]
# ///

import requests

def fetch_html(url: str) -> str:
    return requests.get(url).text
"""
    }
)
# Returns: {"success": true, "node": {"id": "script-def456", ...}}

# Parse HTML
nodes(
    operation="create",
    node_type="SCRIPT",
    data={
        "name": "parse_html",
        "description": "Extract data from HTML",
        "function_signature": "parse_html(html: str) -> dict",
        "body": """
# /// script
# requires-python = ">=3.12"
# dependencies = ["beautifulsoup4>=4.12.0"]
# ///

from bs4 import BeautifulSoup

def parse_html(html: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    return {
        'title': soup.title.string if soup.title else None,
        'links': [a['href'] for a in soup.find_all('a', href=True)]
    }
"""
    }
)
# Returns: {"success": true, "node": {"id": "script-ghi789", ...}}
```

### 3. Create Environment

```python
env(
    operation="create",
    name="scraper-config",
    description="Web scraper configuration",
    variables={
        "USER_AGENT": "MyBot/1.0",
        "RATE_LIMIT": "10",
        "API_KEY": "secret-key-123"  # Auto-detected as secret
    }
)
# Returns: {"success": true, "node": {"id": "env-jkl012", ...}}
```

### 4. Link Everything Together

```python
# Skill CONTAINS scripts
relationships(
    operation="create",
    relationship_type="CONTAINS",
    source_id="skill-abc123",
    target_id="script-def456"
)

relationships(
    operation="create",
    relationship_type="CONTAINS",
    source_id="skill-abc123",
    target_id="script-ghi789"
)

# Scripts CONTAIN environment
relationships(
    operation="create",
    relationship_type="CONTAINS",
    source_id="script-def456",
    target_id="env-jkl012"
)
```

### 5. Execute Combined Scripts

```python
execute(
    code="""
# Both functions are available
html = fetch_html("https://example.com")
data = parse_html(html)
print(f"Page title: {data['title']}")
print(f"Found {len(data['links'])} links")
""",
    imports=["fetch_html", "parse_html"],
    timeout=30
)
# Dependencies (requests, beautifulsoup4) are automatically installed
# Environment variables from scraper-config are available
# Secrets are sanitized from output
```

## Security Features

### Automatic Secret Detection

Environment variables matching these patterns are automatically detected as secrets:
- `SECRET_*`
- `*_SECRET`
- `*_KEY`
- `*_PASSWORD`
- `*_TOKEN`
- `*_API_KEY`
- `*_PRIVATE_KEY`

### Secret Protection

1. **Storage**: Secrets are stored in `~/.mcp-kg-skills/envs/*.env` files (outside project directory)
2. **API Responses**: Secret values are replaced with `<SECRET>`
3. **Execution Output**: Secret values are replaced with `<REDACTED>`
4. **File Permissions**: `.env` files are created with `0600` permissions

## Testing

### Quick Start

```bash
# Setup development environment
./dev.sh setup

# Start test services
./dev.sh start

# Run all tests
./dev.sh test

# Run with coverage
./dev.sh test-cov
```

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── unit/                # Unit tests (no external dependencies)
│   ├── test_security.py
│   ├── test_dependency_parser.py
│   └── test_models.py
└── integration/         # Integration tests (SQLite by default, Neo4j optional)
    ├── test_database.py
    └── test_end_to_end.py
```

### Database Backends for Testing

Integration tests support two database backends:

- **SQLite (default)**: Fast in-memory testing, no setup required
- **Neo4j (optional)**: Full graph database testing with Cypher queries

```bash
# Run integration tests with SQLite (default - fast, no setup)
pytest tests/integration/

# Run integration tests with Neo4j
export TEST_DB=neo4j
export NEO4J_URI="bolt://localhost:7688"
export NEO4J_PASSWORD="testpassword"
pytest tests/integration/
```

### Running Tests

```bash
# All tests (unit + integration with SQLite)
pytest

# Unit tests only
pytest tests/unit/

# Integration tests with SQLite (default)
pytest tests/integration/

# Integration tests with Neo4j
TEST_DB=neo4j NEO4J_URI=bolt://localhost:7688 NEO4J_PASSWORD=testpassword pytest tests/integration/

# Specific test file
pytest tests/unit/test_security.py -v

# Specific test
pytest tests/unit/test_security.py::TestSecretDetector::test_default_patterns -v

# With coverage
pytest --cov=mcp_kg_skills --cov-report=html
```

### Using the dev.sh Script

```bash
# Run all tests
./dev.sh test

# Run specific tests
./dev.sh test tests/unit/

# Run with coverage report
./dev.sh test-cov

# Format code before committing
./dev.sh format

# Run linter
./dev.sh lint

# Type check
./dev.sh typecheck
```

### Using Make

```bash
# Run tests
make test

# Unit tests only
make test-unit

# Integration tests only
make test-integration

# With coverage
make test-cov

# Code quality checks
make lint format typecheck
```

### Writing Tests

Use pytest fixtures:

```python
import pytest

@pytest.mark.asyncio
async def test_create_node(clean_db, sample_skill_data):
    """Test creating a node."""
    node = await clean_db.create_node("SKILL", sample_skill_data)
    assert node["id"] is not None
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed testing guidelines.

## Development

### Project Structure

```
mcp-kg-skills/
├── src/mcp_kg_skills/
│   ├── __init__.py
│   ├── server.py           # FastMCP server
│   ├── models.py           # Pydantic models
│   ├── config.py           # Configuration
│   ├── exceptions.py       # Custom exceptions
│   ├── database/
│   │   ├── abstract.py     # Database interface
│   │   └── neo4j.py        # Neo4j implementation
│   ├── execution/
│   │   ├── dependency.py   # PEP 723 parser
│   │   └── runner.py       # Script executor
│   ├── security/
│   │   └── secrets.py      # Secret detection
│   ├── tools/
│   │   ├── nodes.py        # Node CRUD
│   │   ├── relationships.py
│   │   ├── env.py
│   │   ├── execute.py
│   │   └── query.py
│   └── utils/
│       └── env_file.py     # ENV file manager
├── tests/
├── pyproject.toml
└── README.md
```

### Running Tests

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# With coverage
pytest --cov=mcp_kg_skills --cov-report=html
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy src/
```

## Troubleshooting

### Neo4j Connection Issues

```bash
# Check Neo4j is running
docker ps | grep neo4j

# Check Neo4j logs
docker logs neo4j

# Test connection
neo4j-admin connectivity test
```

### uv Not Found

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

### Permission Errors

```bash
# Fix directory permissions
chmod 700 ~/.mcp-kg-skills/envs/
chmod 600 ~/.mcp-kg-skills/envs/*.env
```

## License

MIT

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

- Issues: [GitHub Issues](https://github.com/yourusername/mcp-kg-skills/issues)
- Discussions: [GitHub Discussions](https://github.com/yourusername/mcp-kg-skills/discussions)
