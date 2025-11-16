#!/bin/bash
# Development and testing helper script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if docker-compose is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    if ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
}

# Start services
start_services() {
    print_info "Starting Neo4j services..."
    docker compose up -d

    print_info "Waiting for Neo4j to be ready..."
    sleep 5

    # Wait for health check
    timeout 60 bash -c 'until docker compose exec -T neo4j cypher-shell -u neo4j -p testpassword "RETURN 1" &>/dev/null; do sleep 2; done' || {
        print_error "Neo4j failed to start"
        docker compose logs neo4j
        exit 1
    }

    print_info "Neo4j is ready at bolt://localhost:7687"
    print_info "Neo4j Browser available at http://localhost:7474"
    print_info "Username: neo4j, Password: testpassword"
}

# Stop services
stop_services() {
    print_info "Stopping services..."
    docker compose down
}

# Run tests
run_tests() {
    export NEO4J_PASSWORD="testpassword"
    export NEO4J_URI="bolt://localhost:7688"

    print_info "Starting test Neo4j instance..."
    docker compose up -d neo4j-test

    print_info "Waiting for test Neo4j to be ready..."
    timeout 60 bash -c 'until docker compose exec -T neo4j-test cypher-shell -u neo4j -p testpassword "RETURN 1" &>/dev/null; do sleep 2; done' || {
        print_error "Test Neo4j failed to start"
        docker compose logs neo4j-test
        exit 1
    }

    print_info "Running tests..."
    uv run pytest -v "$@"

    print_info "Stopping test Neo4j instance..."
    docker compose stop neo4j-test
}

# Run tests with coverage
run_tests_coverage() {
    export NEO4J_PASSWORD="testpassword"
    export NEO4J_URI="bolt://localhost:7688"

    print_info "Starting test Neo4j instance..."
    docker compose up -d neo4j-test

    print_info "Waiting for test Neo4j to be ready..."
    timeout 60 bash -c 'until docker compose exec -T neo4j-test cypher-shell -u neo4j -p testpassword "RETURN 1" &>/dev/null; do sleep 2; done'

    print_info "Running tests with coverage..."
    uv run pytest -v --cov=mcp_kg_skills --cov-report=html --cov-report=term-missing "$@"

    print_info "Coverage report generated in htmlcov/"

    print_info "Stopping test Neo4j instance..."
    docker compose stop neo4j-test
}

# Clean everything
clean() {
    print_warn "Stopping all services and removing volumes..."
    docker compose down -v
    rm -rf .mcp-kg-skills/cache/*
    rm -rf .mcp-kg-skills/envs/*.env
    rm -rf htmlcov/
    rm -f .coverage
    print_info "Cleanup complete"
}

# Setup development environment
setup_dev() {
    print_info "Setting up development environment..."

    # Install dependencies
    print_info "Installing dependencies..."
    uv pip install -e ".[dev]"

    # Create config directories
    print_info "Creating config directories..."
    mkdir -p .mcp-kg-skills/{config,cache,envs}

    # Copy config template if it doesn't exist
    if [ ! -f .mcp-kg-skills/config/database.yaml ]; then
        print_info "Creating database.yaml from template..."
        cat > .mcp-kg-skills/config/database.yaml <<EOF
neo4j:
  uri: "bolt://localhost:7687"
  username: "neo4j"
  password: "\${NEO4J_PASSWORD}"
  database: "neo4j"

execution:
  cache_dir: ".mcp-kg-skills/cache"
  env_dir: ".mcp-kg-skills/envs"
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
EOF
    fi

    print_info "Development environment setup complete!"
    print_info "Run './dev.sh start' to start services"
}

# Format code
format_code() {
    print_info "Formatting code with ruff..."
    uv run ruff format .
    print_info "Code formatted"
}

# Lint code
lint_code() {
    print_info "Linting code with ruff..."
    uv run ruff check .
}

# Type check
type_check() {
    print_info "Type checking with mypy..."
    uv run mypy src/
}

# Show logs
show_logs() {
    docker compose logs -f "$@"
}

# Show usage
usage() {
    cat <<EOF
MCP Knowledge Graph Skills - Development Helper

Usage: ./dev.sh <command> [options]

Commands:
  setup         Setup development environment
  start         Start Neo4j services
  stop          Stop all services
  test          Run tests
  test-cov      Run tests with coverage
  clean         Stop services and clean data
  format        Format code with ruff
  lint          Lint code with ruff
  typecheck     Run type checking with mypy
  logs          Show service logs
  help          Show this help

Examples:
  ./dev.sh setup              # Setup development environment
  ./dev.sh start              # Start Neo4j
  ./dev.sh test               # Run all tests
  ./dev.sh test tests/unit/   # Run unit tests only
  ./dev.sh test-cov           # Run tests with coverage
  ./dev.sh logs neo4j         # Show Neo4j logs
  ./dev.sh clean              # Clean everything

EOF
}

# Main command dispatcher
case "${1:-help}" in
    setup)
        check_docker
        setup_dev
        ;;
    start)
        check_docker
        start_services
        ;;
    stop)
        check_docker
        stop_services
        ;;
    test)
        check_docker
        shift
        run_tests "$@"
        ;;
    test-cov)
        check_docker
        shift
        run_tests_coverage "$@"
        ;;
    clean)
        check_docker
        clean
        ;;
    format)
        format_code
        ;;
    lint)
        lint_code
        ;;
    typecheck)
        type_check
        ;;
    logs)
        check_docker
        shift
        show_logs "$@"
        ;;
    help)
        usage
        ;;
    *)
        print_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac
