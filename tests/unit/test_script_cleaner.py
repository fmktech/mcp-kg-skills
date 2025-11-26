"""Unit tests for script cleaner utility."""

from mcp_kg_skills.utils.script_cleaner import ScriptCleaner


class TestHasMainBlock:
    """Tests for has_main_block detection."""

    def test_detects_single_quoted_main_block(self):
        """Test detection of __main__ with single quotes."""
        script = """def hello():
    print("Hello")

if __name__ == '__main__':
    hello()
"""
        assert ScriptCleaner.has_main_block(script)

    def test_detects_double_quoted_main_block(self):
        """Test detection of __main__ with double quotes."""
        script = """def hello():
    print("Hello")

if __name__ == "__main__":
    hello()
"""
        assert ScriptCleaner.has_main_block(script)

    def test_no_main_block(self):
        """Test detection when no __main__ block exists."""
        script = """def hello():
    print("Hello")

def main():
    hello()
"""
        assert not ScriptCleaner.has_main_block(script)

    def test_main_in_string_but_no_if(self):
        """Test detection when __main__ appears but not in if statement."""
        script = """def hello():
    print("Use __main__ for entry point")
"""
        assert not ScriptCleaner.has_main_block(script)


class TestRemoveMainBlock:
    """Tests for remove_main_block functionality."""

    def test_removes_single_quoted_main_block(self):
        """Test removal of __main__ with single quotes."""
        script = """def hello():
    print("Hello")

if __name__ == '__main__':
    hello()
"""
        result = ScriptCleaner.remove_main_block(script)

        assert "if __name__" not in result
        assert "def hello():" in result
        assert 'print("Hello")' in result
        # Main block call removed, but function def preserved
        lines = [line.strip() for line in result.split("\n")]
        assert "hello()" not in lines  # Standalone call removed

    def test_removes_double_quoted_main_block(self):
        """Test removal of __main__ with double quotes."""
        script = """def hello():
    print("Hello")

if __name__ == "__main__":
    hello()
"""
        result = ScriptCleaner.remove_main_block(script)

        assert "if __name__" not in result
        assert "def hello():" in result

    def test_removes_reversed_comparison(self):
        """Test removal of reversed comparison: '__main__' == __name__."""
        script = """def hello():
    print("Hello")

if '__main__' == __name__:
    hello()
"""
        result = ScriptCleaner.remove_main_block(script)

        assert "if '__main__'" not in result
        assert "def hello():" in result

    def test_removes_reversed_double_quoted_comparison(self):
        """Test removal of reversed comparison with double quotes."""
        script = """def hello():
    print("Hello")

if "__main__" == __name__:
    hello()
"""
        result = ScriptCleaner.remove_main_block(script)

        assert 'if "__main__"' not in result
        assert "def hello():" in result

    def test_preserves_script_without_main_block(self):
        """Test that scripts without __main__ are unchanged."""
        script = """def hello():
    print("Hello")

def main():
    hello()
"""
        result = ScriptCleaner.remove_main_block(script)
        assert result == script

    def test_removes_multiline_main_block(self):
        """Test removal of multi-line __main__ block."""
        script = """def hello():
    print("Hello")

def setup():
    pass

if __name__ == '__main__':
    setup()
    hello()
    print("Done")
    import sys
    sys.exit(0)
"""
        result = ScriptCleaner.remove_main_block(script)

        assert "if __name__" not in result
        assert "sys.exit(0)" not in result
        assert "def hello():" in result
        assert "def setup():" in result

    def test_removes_main_block_with_complex_logic(self):
        """Test removal of __main__ block with complex logic."""
        script = """def process(data):
    return data.upper()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    args = parser.parse_args()

    with open(args.input) as f:
        data = f.read()

    result = process(data)
    print(result)
"""
        result = ScriptCleaner.remove_main_block(script)

        assert "if __name__" not in result
        assert "argparse" not in result
        assert "def process(data):" in result

    def test_preserves_unrelated_if_statements(self):
        """Test that unrelated if statements are preserved."""
        script = """def hello():
    if True:
        print("Hello")

if __name__ == '__main__':
    hello()
"""
        result = ScriptCleaner.remove_main_block(script)

        assert "if True:" in result
        assert "if __name__" not in result

    def test_handles_main_block_at_end_of_file_no_newline(self):
        """Test removal when __main__ block is at end without trailing newline."""
        script = """def hello():
    print("Hello")

if __name__ == '__main__':
    hello()"""
        result = ScriptCleaner.remove_main_block(script)

        assert "if __name__" not in result
        assert "def hello():" in result

    def test_handles_nested_if_in_main_block(self):
        """Test removal of __main__ block containing nested if."""
        script = """def process(x):
    return x * 2

if __name__ == '__main__':
    x = 5
    if x > 0:
        result = process(x)
        print(result)
    else:
        print("Invalid")
"""
        result = ScriptCleaner.remove_main_block(script)

        assert "if __name__" not in result
        assert "if x > 0:" not in result
        assert "def process(x):" in result


class TestRegexFallback:
    """Tests for regex fallback on syntax errors."""

    def test_regex_removes_basic_main_block(self):
        """Test regex removes basic __main__ block."""
        script = """
def hello():
    print("Hello")

if __name__ == '__main__':
    hello()
"""
        result = ScriptCleaner._remove_main_block_regex(script)

        assert "if __name__" not in result
        assert "def hello():" in result

    def test_regex_handles_double_quotes(self):
        """Test regex handles double quotes."""
        script = """
def hello():
    print("Hello")

if __name__ == "__main__":
    hello()
"""
        result = ScriptCleaner._remove_main_block_regex(script)

        assert "if __name__" not in result


class TestIsMainBlock:
    """Tests for _is_main_block AST detection."""

    def test_detects_standard_main_block(self):
        """Test detection of standard __main__ check."""
        import ast

        code = "if __name__ == '__main__': pass"
        tree = ast.parse(code)
        node = tree.body[0]

        assert ScriptCleaner._is_main_block(node)

    def test_detects_double_quoted_main_block(self):
        """Test detection with double quotes."""
        import ast

        code = 'if __name__ == "__main__": pass'
        tree = ast.parse(code)
        node = tree.body[0]

        assert ScriptCleaner._is_main_block(node)

    def test_detects_reversed_comparison(self):
        """Test detection of reversed comparison."""
        import ast

        code = "if '__main__' == __name__: pass"
        tree = ast.parse(code)
        node = tree.body[0]

        assert ScriptCleaner._is_main_block(node)

    def test_rejects_non_if_node(self):
        """Test that non-If nodes are rejected."""
        import ast

        code = "x = 1"
        tree = ast.parse(code)
        node = tree.body[0]

        assert not ScriptCleaner._is_main_block(node)

    def test_rejects_different_variable(self):
        """Test that different variable names are rejected."""
        import ast

        code = "if __file__ == '__main__': pass"
        tree = ast.parse(code)
        node = tree.body[0]

        assert not ScriptCleaner._is_main_block(node)

    def test_rejects_different_value(self):
        """Test that different values are rejected."""
        import ast

        code = "if __name__ == '__test__': pass"
        tree = ast.parse(code)
        node = tree.body[0]

        assert not ScriptCleaner._is_main_block(node)

    def test_rejects_not_equals(self):
        """Test that != comparison is rejected."""
        import ast

        code = "if __name__ != '__main__': pass"
        tree = ast.parse(code)
        node = tree.body[0]

        assert not ScriptCleaner._is_main_block(node)


class TestRealWorldScripts:
    """Test with realistic script examples."""

    def test_data_fetcher_script(self):
        """Test with a realistic data fetching script."""
        script = """# /// script
# requires-python = ">=3.12"
# dependencies = ["requests>=2.31.0"]
# ///

import requests

def fetch_data(url: str) -> dict:
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python script.py <url>")
        sys.exit(1)
    data = fetch_data(sys.argv[1])
    print(data)
"""
        result = ScriptCleaner.remove_main_block(script)

        assert "def fetch_data(url: str)" in result
        assert "# /// script" in result
        assert "if __name__" not in result
        assert "sys.exit(1)" not in result

    def test_data_processing_script(self):
        """Test with a data processing script."""
        script = """import pandas as pd

def process_csv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    return df.describe()

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    return df.dropna()

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Process CSV files')
    parser.add_argument('input', help='Input CSV file')
    parser.add_argument('--output', '-o', help='Output file')
    args = parser.parse_args()

    df = process_csv(args.input)
    df = clean_data(df)

    if args.output:
        df.to_csv(args.output)
    else:
        print(df)
"""
        result = ScriptCleaner.remove_main_block(script)

        assert "def process_csv" in result
        assert "def clean_data" in result
        assert "if __name__" not in result
        assert "argparse" not in result

    def test_script_with_class_and_main(self):
        """Test script with class definition and __main__ block."""
        script = """class DataProcessor:
    def __init__(self, config: dict):
        self.config = config

    def process(self, data: list) -> list:
        return [x * 2 for x in data]

    def validate(self, data: list) -> bool:
        return all(isinstance(x, (int, float)) for x in data)

if __name__ == '__main__':
    processor = DataProcessor({'multiplier': 2})
    test_data = [1, 2, 3, 4, 5]

    if processor.validate(test_data):
        result = processor.process(test_data)
        print(f"Result: {result}")
    else:
        print("Invalid data")
"""
        result = ScriptCleaner.remove_main_block(script)

        assert "class DataProcessor:" in result
        assert "def __init__" in result
        assert "def process" in result
        assert "def validate" in result
        assert "if __name__" not in result
        assert "processor = DataProcessor" not in result
