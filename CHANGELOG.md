# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-11-16

### Added
- Initial release of MCP Knowledge Graph Skills
- Core graph database operations with Neo4j 6.0.3
- Five MCP tools: nodes, relationships, env, execute, query
- Automatic secret detection and sanitization
- PEP 723 inline script metadata support
- Script execution with uv integration
- Dynamic dependency resolution
- Comprehensive test suite (unit + integration)
- Docker Compose for development and testing
- GitHub Actions CI/CD pipeline
- Example starter data and scripts
- Development helper scripts and Makefile
- Full documentation and contributing guide

### Core Features
- **Node Types**: SKILL, KNOWLEDGE, SCRIPT, ENV
- **Relationship Types**: CONTAINS, RELATE_TO
- **Security**: Pattern-based secret detection, output sanitization
- **Execution**: Dynamic script composition, automatic dependency management
- **Database**: Abstract interface with Neo4j implementation
- **Configuration**: YAML-based with environment variable substitution

### Tools
- `nodes`: Create, read, update, delete, and list nodes
- `relationships`: Manage graph relationships with circular dependency detection
- `env`: Environment variable management with secret protection
- `execute`: Execute Python code with dynamic script imports
- `query`: Read-only Cypher query execution

### Development
- Comprehensive unit test suite
- Integration tests with real Neo4j
- End-to-end workflow tests
- Test coverage reporting
- Automated linting and type checking
- Docker-based development environment

### Documentation
- Complete README with examples
- Contributing guidelines
- API documentation for all tools
- Example scripts and use cases
- Development setup guide

[Unreleased]: https://github.com/yourusername/mcp-kg-skills/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/mcp-kg-skills/releases/tag/v0.1.0
