.PHONY: help setup install test test-unit test-integration test-cov lint format typecheck clean start stop logs dev

# Default target
help:
	@echo "MCP Knowledge Graph Skills - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup          Setup development environment"
	@echo "  make install        Install dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run all tests"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-integration  Run integration tests only"
	@echo "  make test-cov       Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint           Run linting"
	@echo "  make format         Format code"
	@echo "  make typecheck      Run type checking"
	@echo ""
	@echo "Docker:"
	@echo "  make start          Start Neo4j services"
	@echo "  make stop           Stop services"
	@echo "  make logs           Show service logs"
	@echo ""
	@echo "Other:"
	@echo "  make clean          Clean up generated files"
	@echo "  make dev            Start development environment"

setup:
	@echo "Setting up development environment..."
	uv pip install -e ".[dev]"
	mkdir -p .mcp-kg-skills/{config,cache,envs}
	@if [ ! -f .mcp-kg-skills/config/database.yaml ]; then \
		cp .mcp-kg-skills/config/database.yaml.example .mcp-kg-skills/config/database.yaml; \
		echo "Created database.yaml - please update with your settings"; \
	fi
	@echo "Setup complete! Run 'make start' to start Neo4j"

install:
	uv pip install -e ".[dev]"

test:
	@echo "Running all tests..."
	uv run pytest -v

test-unit:
	@echo "Running unit tests..."
	uv run pytest tests/unit/ -v

test-integration:
	@echo "Running integration tests..."
	@export NEO4J_URI=bolt://localhost:7688 NEO4J_PASSWORD=testpassword && \
	uv run pytest tests/integration/ -v

test-cov:
	@echo "Running tests with coverage..."
	@export NEO4J_URI=bolt://localhost:7688 NEO4J_PASSWORD=testpassword && \
	uv run pytest --cov=mcp_kg_skills --cov-report=html --cov-report=term-missing

lint:
	@echo "Running linter..."
	uv run ruff check .

format:
	@echo "Formatting code..."
	uv run ruff format .

typecheck:
	@echo "Running type checker..."
	uv run mypy src/

clean:
	@echo "Cleaning up..."
	rm -rf .mcp-kg-skills/cache/*
	rm -rf .mcp-kg-skills/envs/*.env
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "Cleanup complete"

start:
	@echo "Starting Neo4j services..."
	docker compose up -d
	@echo "Waiting for Neo4j to be ready..."
	@sleep 5
	@echo "Neo4j is ready at bolt://localhost:7687"
	@echo "Neo4j Browser: http://localhost:7474"
	@echo "Username: neo4j, Password: testpassword"

stop:
	@echo "Stopping services..."
	docker compose down

logs:
	docker compose logs -f

dev: start
	@echo "Development environment ready!"
	@echo "Run tests: make test"
	@echo "Format code: make format"
	@echo "Run linter: make lint"
