"""Script cleaning utilities for removing __main__ blocks."""

import ast
import logging
import re

logger = logging.getLogger(__name__)


class ScriptCleaner:
    """Utilities for cleaning script bodies before composition.

    SCRIPT nodes should NOT include `if __name__ == '__main__':` blocks.
    These blocks are automatically stripped during execution composition
    to prevent unintended side effects.

    Best Practices for SCRIPT nodes:
    - Export functions/classes that should be callable from user code
    - Keep example/test code in separate functions, not in __main__ blocks
    - Use PEP 723 metadata for dependencies
    """

    @staticmethod
    def has_main_block(script_body: str) -> bool:
        """Quick check if script likely contains __main__ block.

        Args:
            script_body: Python script source code

        Returns:
            True if script likely has __main__ block, False otherwise
        """
        return "__main__" in script_body and "if" in script_body

    @staticmethod
    def remove_main_block(script_body: str, script_name: str | None = None) -> str:
        """Remove if __name__ == '__main__': blocks using AST parsing.

        Args:
            script_body: Python script source code
            script_name: Optional name for logging purposes

        Returns:
            Script with __main__ blocks removed
        """
        try:
            return ScriptCleaner._remove_main_block_ast(script_body, script_name)
        except SyntaxError as e:
            logger.warning(f"AST parsing failed for '{script_name}': {e}. Using regex fallback.")
            return ScriptCleaner._remove_main_block_regex(script_body)

    @staticmethod
    def _remove_main_block_ast(script_body: str, script_name: str | None) -> str:
        """AST-based removal of __main__ blocks.

        Args:
            script_body: Python script source code
            script_name: Optional name for logging purposes

        Returns:
            Script with __main__ blocks removed
        """
        tree = ast.parse(script_body)
        lines_to_remove: set[int] = set()

        for node in ast.walk(tree):
            if ScriptCleaner._is_main_block(node):
                if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    lines_to_remove.update(range(node.lineno, node.end_lineno + 1))
                    logger.info(
                        f"Stripping __main__ block from script '{script_name}' "
                        f"(lines {node.lineno}-{node.end_lineno}). "
                        "SCRIPT nodes should not include __main__ blocks."
                    )

        if not lines_to_remove:
            return script_body

        lines = script_body.split("\n")
        result_lines = [line for i, line in enumerate(lines, start=1) if i not in lines_to_remove]

        # Clean trailing whitespace
        while result_lines and not result_lines[-1].strip():
            result_lines.pop()

        return "\n".join(result_lines)

    @staticmethod
    def _is_main_block(node: ast.AST) -> bool:
        """Check if AST node is 'if __name__ == "__main__":'.

        Handles both quote styles and comparison order:
        - if __name__ == '__main__':
        - if __name__ == "__main__":
        - if '__main__' == __name__:
        - if "__main__" == __name__:

        Args:
            node: AST node to check

        Returns:
            True if node is a __main__ check, False otherwise
        """
        if not isinstance(node, ast.If):
            return False

        test = node.test
        if not isinstance(test, ast.Compare):
            return False
        if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
            return False
        if len(test.comparators) != 1:
            return False

        left, right = test.left, test.comparators[0]

        # Check: __name__ == '__main__'
        if (
            isinstance(left, ast.Name)
            and left.id == "__name__"
            and isinstance(right, ast.Constant)
            and right.value == "__main__"
        ):
            return True

        # Check: '__main__' == __name__
        if (
            isinstance(left, ast.Constant)
            and left.value == "__main__"
            and isinstance(right, ast.Name)
            and right.id == "__name__"
        ):
            return True

        return False

    @staticmethod
    def _remove_main_block_regex(script_body: str) -> str:
        """Regex fallback for scripts with syntax errors.

        Less reliable than AST parsing but handles edge cases where
        scripts have syntax errors.

        Args:
            script_body: Python script source code

        Returns:
            Script with __main__ blocks removed (best effort)
        """
        # Match: if __name__ == '__main__': followed by indented block
        # until next non-indented line or end of string
        pattern = r"\nif\s+__name__\s*==\s*[\"']__main__[\"']\s*:.*?(?=\n[^\s\n]|\Z)"
        return re.sub(pattern, "", script_body, flags=re.DOTALL)
