"""Parser for Requires: directives in Python script docstrings.

This module extracts script dependencies declared in docstrings using
the "Requires:" pattern, enabling automatic loading of dependent scripts.
"""

import ast
import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Pattern to match "Requires:" lines in docstrings
# Supports:
#   Requires: script-name
#   Requires: script1, script2, script3
#   requires: script-name (case insensitive)
#   REQUIRES: script-name (all caps)
REQUIRES_PATTERN = re.compile(
    r"^\s*requires?\s*:\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)


class RequiresParser:
    """Parser for extracting script dependencies from docstrings."""

    @staticmethod
    def extract_requires(code: str) -> list[str]:
        """Extract required script names from code's docstring.

        Parses the module-level docstring for "Requires:" directives.

        Supported formats:
            '''
            My script description.

            Requires: dependency-script
            Requires: another-dependency
            '''

            '''
            Requires: script1, script2, script3
            '''

        Args:
            code: Python source code

        Returns:
            List of required script names (deduplicated, order preserved)
        """
        docstring = RequiresParser._extract_module_docstring(code)
        if not docstring:
            return []

        return RequiresParser._parse_requires_from_docstring(docstring)

    @staticmethod
    def _extract_module_docstring(code: str) -> str | None:
        """Extract the module-level docstring from Python code.

        Args:
            code: Python source code

        Returns:
            Module docstring or None if not found
        """
        try:
            tree = ast.parse(code)
            return ast.get_docstring(tree)
        except SyntaxError as e:
            logger.warning(f"Failed to parse code for docstring extraction: {e}")
            return None

    @staticmethod
    def _parse_requires_from_docstring(docstring: str) -> list[str]:
        """Parse Requires: directives from a docstring.

        Args:
            docstring: Module docstring

        Returns:
            List of required script names
        """
        required: list[str] = []
        seen: set[str] = set()

        for match in REQUIRES_PATTERN.finditer(docstring):
            # Get the value after "Requires:"
            value = match.group(1).strip()

            # Split by comma for multiple dependencies on one line
            names = [name.strip() for name in value.split(",")]

            for name in names:
                # Clean up the name - remove quotes if present
                name = name.strip("\"'").strip()

                # Skip empty names
                if not name:
                    continue

                # Deduplicate while preserving order
                if name not in seen:
                    seen.add(name)
                    required.append(name)

        if required:
            logger.debug(f"Found Requires directives: {required}")

        return required

    @staticmethod
    def has_requires(code: str) -> bool:
        """Check if code has any Requires: directives.

        Args:
            code: Python source code

        Returns:
            True if code contains Requires: directives
        """
        docstring = RequiresParser._extract_module_docstring(code)
        if not docstring:
            return False

        return bool(REQUIRES_PATTERN.search(docstring))
