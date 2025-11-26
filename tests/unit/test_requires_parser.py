"""Tests for RequiresParser utility."""

import pytest

from mcp_kg_skills.utils.requires_parser import RequiresParser


class TestExtractRequires:
    """Tests for extract_requires method."""

    def test_no_docstring(self):
        """Code without docstring returns empty list."""
        code = """
def hello():
    print("Hello")
"""
        result = RequiresParser.extract_requires(code)
        assert result == []

    def test_docstring_without_requires(self):
        """Docstring without Requires returns empty list."""
        code = '''"""This is a simple script."""

def hello():
    print("Hello")
'''
        result = RequiresParser.extract_requires(code)
        assert result == []

    def test_single_requires(self):
        """Single Requires directive is extracted."""
        code = '''"""My consumer script.

Requires: vrya-jira-client
"""

def do_work():
    jira = VryaJira()
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["vrya-jira-client"]

    def test_multiple_requires_separate_lines(self):
        """Multiple Requires on separate lines are extracted."""
        code = '''"""Consumer script with multiple dependencies.

Requires: dependency-a
Requires: dependency-b
Requires: dependency-c
"""

def process():
    pass
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["dependency-a", "dependency-b", "dependency-c"]

    def test_comma_separated_requires(self):
        """Comma-separated Requires on one line are extracted."""
        code = '''"""Script with comma-separated requires.

Requires: script-a, script-b, script-c
"""

def work():
    pass
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["script-a", "script-b", "script-c"]

    def test_mixed_requires_formats(self):
        """Mixed formats (separate lines and commas) work together."""
        code = '''"""Script with mixed requires formats.

Requires: base-lib
Requires: helper-a, helper-b
Requires: another-dep
"""

class MyClass:
    pass
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["base-lib", "helper-a", "helper-b", "another-dep"]

    def test_case_insensitive(self):
        """Requires is case-insensitive."""
        code = '''"""Script with varied case.

requires: lowercase-dep
REQUIRES: uppercase-dep
Requires: mixedcase-dep
"""
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["lowercase-dep", "uppercase-dep", "mixedcase-dep"]

    def test_require_singular(self):
        """Require (singular) without 's' is also supported."""
        code = '''"""Script using singular form.

Require: singular-dep
"""
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["singular-dep"]

    def test_extra_whitespace(self):
        """Extra whitespace is handled correctly."""
        code = '''"""Script with extra whitespace.

Requires:    spaced-dep
Requires:  dep-a  ,  dep-b  ,  dep-c
"""
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["spaced-dep", "dep-a", "dep-b", "dep-c"]

    def test_quoted_names(self):
        """Quoted names have quotes stripped."""
        code = '''"""Script with quoted names.

Requires: "quoted-dep"
Requires: 'single-quoted'
"""
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["quoted-dep", "single-quoted"]

    def test_deduplication(self):
        """Duplicate requires are deduplicated."""
        code = '''"""Script with duplicates.

Requires: common-dep
Requires: unique-dep
Requires: common-dep
"""
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["common-dep", "unique-dep"]

    def test_order_preserved(self):
        """Order of first occurrence is preserved."""
        code = '''"""Script with order test.

Requires: third
Requires: first
Requires: second
Requires: first
"""
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["third", "first", "second"]

    def test_empty_values_ignored(self):
        """Empty values in comma-separated list are ignored."""
        code = '''"""Script with empty values.

Requires: dep-a, , dep-b, ,
"""
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["dep-a", "dep-b"]

    def test_requires_with_description(self):
        """Requires mixed with other docstring content."""
        code = '''"""My awesome consumer script.

This script does amazing things with Jira tickets.
It processes data and generates reports.

Requires: vrya-jira-client
Requires: data-processor

Args:
    None

Returns:
    Nothing special
"""

def main():
    pass
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["vrya-jira-client", "data-processor"]

    def test_triple_quoted_single(self):
        """Single-quoted triple docstring works."""
        code = """'''Script with single quotes.

Requires: my-dependency
'''

def work():
    pass
"""
        result = RequiresParser.extract_requires(code)
        assert result == ["my-dependency"]

    def test_syntax_error_returns_empty(self):
        """Syntax error in code returns empty list."""
        code = """def broken(
    # Missing closing paren
"""
        result = RequiresParser.extract_requires(code)
        assert result == []


class TestHasRequires:
    """Tests for has_requires method."""

    def test_no_docstring(self):
        """No docstring returns False."""
        code = "x = 1"
        assert RequiresParser.has_requires(code) is False

    def test_docstring_without_requires(self):
        """Docstring without Requires returns False."""
        code = '"""Simple doc."""'
        assert RequiresParser.has_requires(code) is False

    def test_has_requires_true(self):
        """Docstring with Requires returns True."""
        code = '''"""Doc.

Requires: my-dep
"""
'''
        assert RequiresParser.has_requires(code) is True


class TestExtractModuleDocstring:
    """Tests for _extract_module_docstring method."""

    def test_simple_docstring(self):
        """Simple module docstring is extracted."""
        code = '"""This is the docstring."""'
        result = RequiresParser._extract_module_docstring(code)
        assert result == "This is the docstring."

    def test_multiline_docstring(self):
        """Multiline docstring is extracted."""
        code = '''"""First line.

Second line.
Third line.
"""

def func():
    pass
'''
        result = RequiresParser._extract_module_docstring(code)
        assert "First line" in result
        assert "Second line" in result

    def test_no_docstring_returns_none(self):
        """No docstring returns None."""
        code = """
import os

def func():
    pass
"""
        result = RequiresParser._extract_module_docstring(code)
        assert result is None

    def test_function_docstring_not_extracted(self):
        """Function docstring is not extracted as module docstring."""
        code = '''
def func():
    """This is a function docstring."""
    pass
'''
        result = RequiresParser._extract_module_docstring(code)
        assert result is None


class TestRealWorldScenarios:
    """Tests simulating real-world script patterns."""

    def test_vrya_jira_consumer(self):
        """Simulates a consumer of vrya-jira-client."""
        code = '''"""Jira ticket processor.

This script processes Jira tickets and generates reports.
It uses the VryaJira client for API access.

Requires: vrya-jira-client
"""
# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas>=2.0"]
# ///

import pandas as pd


def process_tickets():
    """Process all tickets."""
    # VryaJira is available from the required script
    jira = VryaJira()
    tickets = jira.get_tickets()
    df = pd.DataFrame(tickets)
    return df


if __name__ == "__main__":
    result = process_tickets()
    print(result)
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["vrya-jira-client"]

    def test_multi_dependency_etl(self):
        """Simulates an ETL script with multiple dependencies."""
        code = '''"""ETL Pipeline for sales data.

Extracts data from multiple sources, transforms it,
and loads into the data warehouse.

Requires: salesconnect-client
Requires: data-transformer
Requires: warehouse-loader
"""

def run_etl():
    # All classes from required scripts are available
    client = SalesConnectClient()
    transformer = DataTransformer()
    loader = WarehouseLoader()

    data = client.fetch_sales()
    transformed = transformer.transform(data)
    loader.load(transformed)
'''
        result = RequiresParser.extract_requires(code)
        assert result == ["salesconnect-client", "data-transformer", "warehouse-loader"]
