"""Load example data into MCP Knowledge Graph Skills.

This script demonstrates how to programmatically create a complete
knowledge graph with skills, scripts, knowledge, and environments.
"""

import asyncio
import os

from mcp_kg_skills.config import load_config
from mcp_kg_skills.database.neo4j import Neo4jDatabase
from mcp_kg_skills.security.secrets import SecretDetector
from mcp_kg_skills.tools.nodes import NodesTool
from mcp_kg_skills.tools.relationships import RelationshipsTool
from mcp_kg_skills.utils.env_file import EnvFileManager


async def load_example_data():
    """Load example data into the knowledge graph."""
    # Load configuration
    config = load_config()

    # Initialize database
    db = Neo4jDatabase(
        uri=config.database.uri,
        username=config.database.username,
        password=config.database.password,
        database=config.database.database,
    )

    await db.connect()
    await db.initialize_schema()

    # Initialize tools
    env_manager = EnvFileManager(config.execution.env_dir)
    secret_detector = SecretDetector(config.security.secret_patterns)
    nodes_tool = NodesTool(db, env_manager, secret_detector)
    relationships_tool = RelationshipsTool(db)

    print("🚀 Loading example data into MCP Knowledge Graph Skills...")

    # ==========================================================================
    # Example 1: Web Scraper Skill
    # ==========================================================================
    print("\n📦 Creating Web Scraper Skill...")

    web_scraper_skill = await nodes_tool.handle(
        operation="create",
        node_type="SKILL",
        data={
            "name": "web-scraper",
            "description": "Web scraping utilities with rate limiting and error handling",
            "body": """# Web Scraper Skill

This skill provides utilities for web scraping with built-in
rate limiting and error handling.

## Features
- HTTP request handling
- HTML parsing with BeautifulSoup
- Rate limiting
- Error handling

## Scripts
- `fetch_html`: Fetch HTML content from a URL
- `parse_links`: Extract all links from HTML
""",
        },
    )
    web_scraper_id = web_scraper_skill["node"]["id"]

    # Create fetch_html script
    fetch_html_script = await nodes_tool.handle(
        operation="create",
        node_type="SCRIPT",
        data={
            "name": "fetch_html",
            "description": "Fetch HTML content from a URL with error handling",
            "function_signature": "fetch_html(url: str, timeout: int = 30) -> str",
            "body": """# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "requests>=2.31.0",
# ]
# ///

import os
import requests
from time import sleep

def fetch_html(url: str, timeout: int = 30) -> str:
    \"\"\"Fetch HTML content from a URL.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds

    Returns:
        HTML content as string
    \"\"\"
    rate_limit = float(os.getenv('RATE_LIMIT_SECONDS', '1'))
    user_agent = os.getenv('USER_AGENT', 'MCP-KG-Skills/1.0')

    headers = {'User-Agent': user_agent}

    sleep(rate_limit)  # Rate limiting
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    return response.text
""",
        },
    )
    fetch_html_id = fetch_html_script["node"]["id"]

    # Create parse_links script
    parse_links_script = await nodes_tool.handle(
        operation="create",
        node_type="SCRIPT",
        data={
            "name": "parse_links",
            "description": "Extract all links from HTML content",
            "function_signature": "parse_links(html: str) -> list[str]",
            "body": """# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "beautifulsoup4>=4.12.0",
# ]
# ///

from bs4 import BeautifulSoup

def parse_links(html: str) -> list[str]:
    \"\"\"Extract all links from HTML.

    Args:
        html: HTML content

    Returns:
        List of URLs found in the HTML
    \"\"\"
    soup = BeautifulSoup(html, 'html.parser')
    links = []

    for link in soup.find_all('a', href=True):
        links.append(link['href'])

    return links
""",
        },
    )
    parse_links_id = parse_links_script["node"]["id"]

    # Create scraper environment
    scraper_env = await nodes_tool.handle(
        operation="create",
        node_type="ENV",
        data={
            "name": "scraper-config",
            "description": "Web scraper configuration",
            "variables": {
                "USER_AGENT": "MCP-KG-Skills/1.0",
                "RATE_LIMIT_SECONDS": "1",
                "TIMEOUT_SECONDS": "30",
            },
        },
    )
    scraper_env_id = scraper_env["node"]["id"]

    # Link scripts to skill
    await relationships_tool.handle(
        operation="create",
        relationship_type="CONTAINS",
        source_id=web_scraper_id,
        target_id=fetch_html_id,
    )
    await relationships_tool.handle(
        operation="create",
        relationship_type="CONTAINS",
        source_id=web_scraper_id,
        target_id=parse_links_id,
    )

    # Link environment to scripts
    await relationships_tool.handle(
        operation="create",
        relationship_type="CONTAINS",
        source_id=fetch_html_id,
        target_id=scraper_env_id,
    )

    print(f"✅ Created Web Scraper Skill (ID: {web_scraper_id})")

    # ==========================================================================
    # Example 2: Data Processing Skill
    # ==========================================================================
    print("\n📊 Creating Data Processing Skill...")

    data_skill = await nodes_tool.handle(
        operation="create",
        node_type="SKILL",
        data={
            "name": "data-processing",
            "description": "Data analysis and processing utilities",
            "body": """# Data Processing Skill

Utilities for data analysis, transformation, and visualization.

## Features
- CSV/JSON data loading
- Data transformation
- Statistical analysis
- Basic visualizations

## Scripts
- `load_csv`: Load CSV data
- `analyze_data`: Perform statistical analysis
""",
        },
    )
    data_skill_id = data_skill["node"]["id"]

    # Create load_csv script
    load_csv_script = await nodes_tool.handle(
        operation="create",
        node_type="SCRIPT",
        data={
            "name": "load_csv",
            "description": "Load CSV file into a pandas DataFrame",
            "function_signature": "load_csv(filepath: str) -> dict",
            "body": """# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pandas>=2.0.0",
# ]
# ///

import pandas as pd

def load_csv(filepath: str) -> dict:
    \"\"\"Load CSV file and return basic info.

    Args:
        filepath: Path to CSV file

    Returns:
        Dictionary with data info
    \"\"\"
    df = pd.read_csv(filepath)

    return {
        'rows': len(df),
        'columns': list(df.columns),
        'dtypes': df.dtypes.to_dict(),
        'head': df.head().to_dict(),
    }
""",
        },
    )
    load_csv_id = load_csv_script["node"]["id"]

    # Link script to skill
    await relationships_tool.handle(
        operation="create",
        relationship_type="CONTAINS",
        source_id=data_skill_id,
        target_id=load_csv_id,
    )

    print(f"✅ Created Data Processing Skill (ID: {data_skill_id})")

    # ==========================================================================
    # Example 3: API Client Skill
    # ==========================================================================
    print("\n🌐 Creating API Client Skill...")

    api_skill = await nodes_tool.handle(
        operation="create",
        node_type="SKILL",
        data={
            "name": "api-client",
            "description": "REST API client utilities with authentication",
            "body": """# API Client Skill

Generic REST API client with authentication support.

## Features
- GET/POST/PUT/DELETE requests
- Bearer token authentication
- Request/response logging
- Error handling

## Scripts
- `api_get`: Make GET request
- `api_post`: Make POST request
""",
        },
    )
    api_skill_id = api_skill["node"]["id"]

    # Create api_get script
    api_get_script = await nodes_tool.handle(
        operation="create",
        node_type="SCRIPT",
        data={
            "name": "api_get",
            "description": "Make authenticated GET request to API",
            "function_signature": "api_get(endpoint: str, params: dict = None) -> dict",
            "body": """# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "requests>=2.31.0",
# ]
# ///

import os
import requests

def api_get(endpoint: str, params: dict = None) -> dict:
    \"\"\"Make authenticated GET request.

    Args:
        endpoint: API endpoint URL
        params: Query parameters

    Returns:
        JSON response
    \"\"\"
    api_key = os.getenv('API_KEY')
    base_url = os.getenv('API_BASE_URL', '')

    headers = {}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    url = f"{base_url}{endpoint}" if base_url else endpoint
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()

    return response.json()
""",
        },
    )
    api_get_id = api_get_script["node"]["id"]

    # Create API environment (with secret)
    api_env = await nodes_tool.handle(
        operation="create",
        node_type="ENV",
        data={
            "name": "api-credentials",
            "description": "API authentication credentials",
            "variables": {
                "API_BASE_URL": "https://api.example.com",
                "API_KEY": "your-api-key-here",  # Will be marked as secret
            },
        },
    )
    api_env_id = api_env["node"]["id"]

    # Link everything
    await relationships_tool.handle(
        operation="create",
        relationship_type="CONTAINS",
        source_id=api_skill_id,
        target_id=api_get_id,
    )
    await relationships_tool.handle(
        operation="create",
        relationship_type="CONTAINS",
        source_id=api_get_id,
        target_id=api_env_id,
    )

    print(f"✅ Created API Client Skill (ID: {api_skill_id})")

    # ==========================================================================
    # Create Knowledge Documentation
    # ==========================================================================
    print("\n📚 Creating Knowledge Documentation...")

    best_practices = await nodes_tool.handle(
        operation="create",
        node_type="KNOWLEDGE",
        data={
            "name": "best-practices",
            "description": "Best practices for using MCP KG Skills",
            "body": """# Best Practices

## Organizing Skills

1. **Group Related Functionality**: Keep related scripts together in a skill
2. **Descriptive Names**: Use clear, descriptive names for skills and scripts
3. **Documentation**: Always include comprehensive descriptions

## Writing Scripts

1. **Single Responsibility**: Each script should do one thing well
2. **Type Hints**: Always include type hints in function signatures
3. **Error Handling**: Handle errors gracefully
4. **Dependencies**: Specify all dependencies in PEP 723 metadata

## Environment Variables

1. **Secret Detection**: Use standard naming patterns (API_KEY, PASSWORD, etc.)
2. **Defaults**: Provide sensible defaults where appropriate
3. **Documentation**: Document all required environment variables

## Testing

1. **Test Individually**: Test each script in isolation
2. **Test Composition**: Test scripts working together
3. **Error Cases**: Test error handling paths
""",
        },
    )

    await relationships_tool.handle(
        operation="create",
        relationship_type="CONTAINS",
        source_id=web_scraper_id,
        target_id=best_practices["node"]["id"],
    )

    print(f"✅ Created Knowledge Documentation")

    # ==========================================================================
    # Create Cross-Skill Relationships
    # ==========================================================================
    print("\n🔗 Creating Cross-Skill Relationships...")

    # Web scraper relates to data processing (scrape -> process data)
    await relationships_tool.handle(
        operation="create",
        relationship_type="RELATE_TO",
        source_id=web_scraper_id,
        target_id=data_skill_id,
        properties={"reason": "Web scraped data often needs processing"},
    )

    print("✅ Created cross-skill relationships")

    # ==========================================================================
    # Summary
    # ==========================================================================
    print("\n" + "=" * 60)
    print("✨ Example data loaded successfully!")
    print("=" * 60)
    print(f"\n📊 Summary:")
    print(f"  - Skills: 3")
    print(f"  - Scripts: 5")
    print(f"  - Environments: 2")
    print(f"  - Knowledge: 1")

    print(f"\n💡 Try these queries:")
    print(f"\n  # List all skills")
    print(f"  MATCH (s:SKILL) RETURN s.name, s.description")
    print(f"\n  # Find scripts in web-scraper skill")
    print(f"  MATCH (s:SKILL {{name: 'web-scraper'}})-[:CONTAINS]->(script:SCRIPT)")
    print(f"  RETURN script.name, script.description")
    print(f"\n  # Execute web scraping")
    print(f"  execute(")
    print(f"    imports=['fetch_html', 'parse_links'],")
    print(f"    code='''")
    print(f"html = fetch_html('https://example.com')")
    print(f"links = parse_links(html)")
    print(f"print(f'Found {{len(links)}} links')")
    print(f"'''")
    print(f"  )")

    await db.disconnect()
    print(f"\n🎉 Done!")


if __name__ == "__main__":
    asyncio.run(load_example_data())
