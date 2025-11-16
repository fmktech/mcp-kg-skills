## Contributing to MCP Knowledge Graph Skills

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

## Development Setup

### Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) - Fast Python package installer
- Docker and Docker Compose
- Neo4j 5.x (via Docker)
- Git

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/mcp-kg-skills.git
cd mcp-kg-skills

# Run setup
./dev.sh setup

# Start Neo4j
./dev.sh start

# Run tests
./dev.sh test
```

### Development Environment

The `dev.sh` script provides all common development operations:

```bash
./dev.sh setup      # Setup development environment
./dev.sh start      # Start Neo4j services
./dev.sh stop       # Stop services
./dev.sh test       # Run all tests
./dev.sh test-cov   # Run tests with coverage
./dev.sh format     # Format code with ruff
./dev.sh lint       # Lint code
./dev.sh typecheck  # Run type checking
./dev.sh logs       # Show service logs
./dev.sh clean      # Clean all data
```

### Manual Setup

If you prefer manual setup:

```bash
# Install dependencies
uv pip install -e ".[dev]"

# Start Neo4j
docker compose up -d neo4j

# Create config
cp .mcp-kg-skills/config/database.yaml.example \
   .mcp-kg-skills/config/database.yaml

# Set password
export NEO4J_PASSWORD="testpassword"
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `test/` - Test additions/fixes
- `refactor/` - Code refactoring

### 2. Make Changes

Follow the [Code Standards](#code-standards) below.

### 3. Run Tests

```bash
# Run all tests
./dev.sh test

# Run specific test file
./dev.sh test tests/unit/test_security.py

# Run with coverage
./dev.sh test-cov
```

### 4. Format and Lint

```bash
# Format code
./dev.sh format

# Lint
./dev.sh lint

# Type check
./dev.sh typecheck
```

### 5. Commit Changes

Use conventional commits:

```bash
git commit -m "feat: add new script execution feature"
git commit -m "fix: resolve circular dependency issue"
git commit -m "docs: update README examples"
git commit -m "test: add integration tests for relationships"
```

Commit types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `test`: Tests
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `chore`: Maintenance

### 6. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## Code Standards

### Python Style

We use [Ruff](https://docs.astral.sh/ruff/) for formatting and linting.

```bash
# Format code
ruff format .

# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .
```

### Type Hints

All code must have type hints:

```python
# Good
def process_data(data: list[dict[str, Any]]) -> pd.DataFrame:
    ...

# Bad
def process_data(data):
    ...
```

### Docstrings

Use Google-style docstrings:

```python
def fetch_data(url: str, timeout: int = 30) -> dict:
    """Fetch data from a URL.

    Args:
        url: The URL to fetch from
        timeout: Request timeout in seconds

    Returns:
        JSON response data

    Raises:
        RequestError: If request fails
    """
    ...
```

### Error Handling

Use custom exceptions from `exceptions.py`:

```python
from mcp_kg_skills.exceptions import NodeNotFoundError

async def read_node(node_id: str) -> dict:
    node = await db.read_node(node_id)
    if not node:
        raise NodeNotFoundError(node_id)
    return node
```

### Async/Await

Use async/await consistently:

```python
# Good
async def process_items(items: list[str]) -> None:
    for item in items:
        await process_item(item)

# Bad - blocking in async function
async def process_items(items: list[str]) -> None:
    for item in items:
        time.sleep(1)  # Don't block!
```

## Testing

### Test Organization

```
tests/
├── unit/              # Unit tests (no external dependencies)
│   ├── test_security.py
│   ├── test_dependency_parser.py
│   └── test_models.py
└── integration/       # Integration tests (require Neo4j)
    ├── test_database.py
    └── test_end_to_end.py
```

### Writing Tests

Use pytest with async support:

```python
import pytest

@pytest.mark.asyncio
class TestMyFeature:
    """Tests for my feature."""

    async def test_basic_operation(self, clean_db):
        """Test basic operation."""
        result = await my_function()
        assert result == expected
```

### Test Fixtures

Use fixtures from `tests/conftest.py`:

```python
async def test_with_database(clean_db: Neo4jDatabase):
    """Test using clean database fixture."""
    node = await clean_db.create_node("SKILL", {...})
    assert node is not None
```

### Test Coverage

Aim for > 80% code coverage:

```bash
# Run with coverage
./dev.sh test-cov

# View HTML report
open htmlcov/index.html
```

### Integration Tests

Integration tests require Neo4j:

```bash
# Start test Neo4j
docker compose up -d neo4j-test

# Run integration tests
export NEO4J_URI="bolt://localhost:7688"
export NEO4J_PASSWORD="testpassword"
pytest tests/integration/ -v
```

## Pull Request Process

### Before Submitting

1. **All tests pass**: `./dev.sh test`
2. **Code is formatted**: `./dev.sh format`
3. **No lint errors**: `./dev.sh lint`
4. **Type checks pass**: `./dev.sh typecheck`
5. **Tests added** for new features
6. **Documentation updated** if needed

### PR Description

Include:
- **What**: What does this PR do?
- **Why**: Why is this change needed?
- **How**: How does it work?
- **Testing**: How was it tested?
- **Breaking Changes**: Any breaking changes?

Template:

```markdown
## Description
Brief description of changes

## Motivation
Why is this change needed?

## Changes
- Change 1
- Change 2

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Code formatted with ruff
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Type hints added
```

### Review Process

1. Automated checks run (CI)
2. Maintainer review
3. Address feedback
4. Final approval
5. Merge

## Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- `MAJOR.MINOR.PATCH`
- `MAJOR`: Breaking changes
- `MINOR`: New features (backward compatible)
- `PATCH`: Bug fixes

### Creating a Release

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Create git tag:
   ```bash
   git tag -a v0.2.0 -m "Release v0.2.0"
   git push origin v0.2.0
   ```
4. GitHub Actions will build and publish

## Architecture Guidelines

### Adding a New Node Type

1. Add enum to `models.py`:
   ```python
   class NodeType(str, Enum):
       NEW_TYPE = "NEW_TYPE"
   ```

2. Create Pydantic model:
   ```python
   class NewTypeNode(BaseNode):
       field1: str
       field2: int
   ```

3. Update database constraints in `database/neo4j.py`
4. Add tool support in `tools/nodes.py`
5. Add tests

### Adding a New MCP Tool

1. Create tool module in `tools/`:
   ```python
   # tools/my_tool.py
   class MyTool:
       def __init__(self, db, ...):
           ...

       async def handle(self, ...):
           ...
   ```

2. Add to server in `server.py`:
   ```python
   @mcp.tool()
   async def my_tool(...) -> dict:
       """Tool description."""
       return await _my_tool.handle(...)
   ```

3. Add integration tests
4. Update documentation

## Documentation

### Inline Documentation

- All public functions/classes need docstrings
- Use type hints everywhere
- Add examples in docstrings when helpful

### README Updates

Update `README.md` when adding:
- New features
- New tools
- New configuration options
- Breaking changes

### API Documentation

Tool docstrings appear in MCP client - make them clear:

```python
@mcp.tool()
async def my_tool(param: str) -> dict:
    """Clear one-line description.

    Longer description with details about what the tool does,
    when to use it, and any important notes.

    Args:
        param: Description of parameter

    Returns:
        Description of return value

    Examples:
        my_tool(param="value")
    """
```

## Getting Help

- **Issues**: Open an issue on GitHub
- **Discussions**: Use GitHub Discussions
- **Questions**: Tag maintainers in issues

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers
- Accept constructive criticism
- Focus on what's best for the project

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to MCP Knowledge Graph Skills! 🎉
