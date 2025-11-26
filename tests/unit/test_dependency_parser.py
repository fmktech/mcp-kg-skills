"""Unit tests for PEP 723 dependency parser."""

import pytest

from mcp_kg_skills.exceptions import DependencyParseError
from mcp_kg_skills.execution.dependency import PEP723Parser


class TestPEP723Parser:
    """Tests for PEP 723 parser."""

    def test_has_metadata_true(self):
        """Test detection of PEP 723 metadata block."""
        script = """# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

def hello():
    print("Hello")
"""
        assert PEP723Parser.has_metadata(script)

    def test_has_metadata_false(self):
        """Test detection when no metadata block exists."""
        script = """
def hello():
    print("Hello")
"""
        assert not PEP723Parser.has_metadata(script)

    def test_parse_metadata(self):
        """Test parsing valid metadata block."""
        script = """# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "requests>=2.31.0",
#   "pandas>=2.0.0",
# ]
# ///

import requests
"""
        metadata = PEP723Parser.parse_metadata(script)

        assert metadata is not None
        assert metadata["requires-python"] == ">=3.12"
        assert "requests>=2.31.0" in metadata["dependencies"]
        assert "pandas>=2.0.0" in metadata["dependencies"]

    def test_parse_metadata_none_when_missing(self):
        """Test that parse_metadata returns None when no block exists."""
        script = "def hello(): pass"
        assert PEP723Parser.parse_metadata(script) is None

    def test_parse_metadata_invalid_toml(self):
        """Test error handling for invalid TOML."""
        script = """# /// script
# invalid toml [[[
# ///
"""
        with pytest.raises(DependencyParseError):
            PEP723Parser.parse_metadata(script)

    def test_extract_dependencies(self):
        """Test extracting dependency list."""
        script = """# /// script
# dependencies = [
#   "requests>=2.31.0",
#   "pandas",
# ]
# ///
"""
        deps = PEP723Parser.extract_dependencies(script)

        assert len(deps) == 2
        assert "requests>=2.31.0" in deps
        assert "pandas" in deps

    def test_extract_dependencies_empty(self):
        """Test extracting dependencies when none exist."""
        script = """# /// script
# requires-python = ">=3.12"
# ///
"""
        deps = PEP723Parser.extract_dependencies(script)
        assert deps == []

    def test_extract_dependencies_no_metadata(self):
        """Test extracting dependencies when no metadata block."""
        script = "def hello(): pass"
        deps = PEP723Parser.extract_dependencies(script)
        assert deps == []

    def test_extract_python_version(self):
        """Test extracting Python version requirement."""
        script = """# /// script
# requires-python = ">=3.12"
# ///
"""
        version = PEP723Parser.extract_python_version(script)
        assert version == ">=3.12"

    def test_extract_python_version_none(self):
        """Test extracting Python version when not specified."""
        script = """# /// script
# dependencies = []
# ///
"""
        version = PEP723Parser.extract_python_version(script)
        assert version is None

    def test_merge_dependencies(self):
        """Test merging dependencies from multiple scripts."""
        script1 = """# /// script
# dependencies = ["requests>=2.31.0", "pandas"]
# ///
"""
        script2 = """# /// script
# dependencies = ["requests>=2.31.0", "numpy"]
# ///
"""
        script3 = "def hello(): pass"  # No deps

        merged = PEP723Parser.merge_dependencies(script1, script2, script3)

        # Should be deduplicated and sorted
        assert len(merged) == 3
        assert "requests>=2.31.0" in merged
        assert "pandas" in merged
        assert "numpy" in merged
        # Check sorted
        assert merged == sorted(merged)

    def test_generate_metadata_block(self):
        """Test generating PEP 723 metadata block."""
        block = PEP723Parser.generate_metadata_block(
            dependencies=["requests>=2.31.0", "pandas"],
            python_version=">=3.12",
        )

        assert "# /// script" in block
        assert '# requires-python = ">=3.12"' in block
        assert '#   "requests>=2.31.0",' in block
        assert '#   "pandas",' in block
        assert "# ///" in block

    def test_generate_metadata_block_minimal(self):
        """Test generating minimal metadata block."""
        block = PEP723Parser.generate_metadata_block()

        assert "# /// script" in block
        assert "# ///" in block

    def test_add_metadata_to_script(self):
        """Test adding metadata to a script."""
        script = """def hello():
    print("Hello")
"""
        result = PEP723Parser.add_metadata_to_script(
            script,
            dependencies=["requests"],
            python_version=">=3.12",
        )

        assert "# /// script" in result
        assert "# ///" in result
        assert "def hello():" in result
        # Original script should be after metadata
        assert result.index("# ///") < result.index("def hello()")

    def test_add_metadata_replaces_existing(self):
        """Test that adding metadata replaces existing block."""
        script = """# /// script
# dependencies = ["old"]
# ///

def hello():
    pass
"""
        result = PEP723Parser.add_metadata_to_script(
            script,
            dependencies=["new"],
        )

        assert '#   "new",' in result
        assert "old" not in result

    def test_remove_metadata_block(self):
        """Test removing metadata block from script."""
        script = """# /// script
# dependencies = []
# ///

def hello():
    print("Hello")
"""
        result = PEP723Parser._remove_metadata_block(script)

        assert "# /// script" not in result
        assert "# ///" not in result
        assert "def hello():" in result

    def test_parse_multiline_dependencies(self):
        """Test parsing dependencies with different formatting."""
        script = """# /// script
# dependencies = [
#   "requests>=2.31.0",
#   "pandas>=2.0.0",
#   "numpy",
# ]
# ///
"""
        deps = PEP723Parser.extract_dependencies(script)

        assert len(deps) == 3
        assert all(dep in deps for dep in ["requests>=2.31.0", "pandas>=2.0.0", "numpy"])

    def test_parse_with_comments(self):
        """Test parsing metadata with empty comment lines."""
        script = """# /// script
#
# requires-python = ">=3.12"
#
# dependencies = ["requests"]
#
# ///

import requests
"""
        metadata = PEP723Parser.parse_metadata(script)

        assert metadata is not None
        assert metadata["requires-python"] == ">=3.12"
        assert "requests" in metadata["dependencies"]

    def test_invalid_dependencies_type(self):
        """Test error when dependencies is not a list."""
        script = """# /// script
# dependencies = "not-a-list"
# ///
"""
        with pytest.raises(DependencyParseError, match="must be a list"):
            PEP723Parser.extract_dependencies(script)

    def test_metadata_extraction_preserves_order(self):
        """Test that dependency order is preserved before sorting."""
        script = """# /// script
# dependencies = ["z-package", "a-package", "m-package"]
# ///
"""
        merged = PEP723Parser.merge_dependencies(script)

        # Merged dependencies should be sorted
        assert merged == ["a-package", "m-package", "z-package"]


class TestRealWorldScripts:
    """Test with realistic script examples."""

    def test_simple_requests_script(self):
        """Test parsing a simple requests-based script."""
        script = """# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "requests>=2.31.0",
# ]
# ///

import requests

def fetch_data(url: str) -> dict:
    response = requests.get(url)
    response.raise_for_status()
    return response.json()
"""
        deps = PEP723Parser.extract_dependencies(script)
        version = PEP723Parser.extract_python_version(script)

        assert deps == ["requests>=2.31.0"]
        assert version == ">=3.12"

    def test_data_processing_script(self):
        """Test parsing a data processing script with multiple deps."""
        script = """# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pandas>=2.0.0",
#   "numpy>=1.24.0",
#   "matplotlib>=3.7.0",
# ]
# ///

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def process_data(data: list) -> pd.DataFrame:
    df = pd.DataFrame(data)
    return df.describe()
"""
        deps = PEP723Parser.extract_dependencies(script)

        assert len(deps) == 3
        assert all(dep in deps for dep in ["pandas>=2.0.0", "numpy>=1.24.0", "matplotlib>=3.7.0"])
