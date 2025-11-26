"""PEP 723 inline script metadata parser."""

import logging
import tomllib
from typing import Any

from ..exceptions import DependencyParseError

logger = logging.getLogger(__name__)


class PEP723Parser:
    """Parser for PEP 723 inline script metadata.

    PEP 723 defines a standard way to embed metadata in Python scripts
    using a TOML block delimited by `# /// script` and `# ///`.

    Example:
        # /// script
        # requires-python = ">=3.12"
        # dependencies = [
        #   "requests>=2.31.0",
        #   "pandas>=2.0.0",
        # ]
        # ///

        import requests
        import pandas as pd
        ...
    """

    @staticmethod
    def has_metadata(script_body: str) -> bool:
        """Check if script contains PEP 723 metadata block.

        Args:
            script_body: Python script source code

        Returns:
            True if metadata block exists, False otherwise
        """
        return "# /// script" in script_body and "# ///" in script_body

    @staticmethod
    def parse_metadata(script_body: str, script_name: str | None = None) -> dict[str, Any] | None:
        """Extract and parse PEP 723 metadata block from script.

        Args:
            script_body: Python script source code
            script_name: Optional script name for error messages

        Returns:
            Parsed metadata dictionary or None if no metadata block found

        Raises:
            DependencyParseError: If metadata block is malformed
        """
        if not PEP723Parser.has_metadata(script_body):
            return None

        try:
            # Extract the metadata block
            metadata_block = PEP723Parser._extract_metadata_block(script_body)

            if not metadata_block:
                return None

            # Parse as TOML
            metadata = tomllib.loads(metadata_block)

            logger.debug(f"Parsed PEP 723 metadata: {metadata}")
            return metadata

        except tomllib.TOMLDecodeError as e:
            raise DependencyParseError(
                f"Invalid TOML in metadata block: {e}",
                script_name,
            )
        except Exception as e:
            raise DependencyParseError(
                f"Failed to parse metadata: {e}",
                script_name,
            )

    @staticmethod
    def _extract_metadata_block(script_body: str) -> str | None:
        """Extract the raw metadata block content.

        Args:
            script_body: Python script source code

        Returns:
            Raw TOML content from metadata block or None
        """
        lines = script_body.split("\n")
        in_block = False
        metadata_lines = []

        for line in lines:
            stripped = line.strip()

            if stripped == "# /// script":
                in_block = True
                continue

            if in_block:
                if stripped == "# ///":
                    # End of block
                    break

                # Remove leading '# ' from metadata lines
                if stripped.startswith("# "):
                    metadata_lines.append(stripped[2:])
                elif stripped == "#":
                    metadata_lines.append("")
                else:
                    # Line doesn't follow expected format
                    logger.warning(f"Unexpected line in metadata block: {line}")

        if not metadata_lines:
            return None

        return "\n".join(metadata_lines)

    @staticmethod
    def extract_dependencies(script_body: str, script_name: str | None = None) -> list[str]:
        """Extract dependency list from script metadata.

        Args:
            script_body: Python script source code
            script_name: Optional script name for error messages

        Returns:
            List of dependency specifications (e.g., ["requests>=2.31.0"])

        Examples:
            >>> script = '''
            ... # /// script
            ... # dependencies = ["requests>=2.31.0", "pandas"]
            ... # ///
            ... '''
            >>> PEP723Parser.extract_dependencies(script)
            ['requests>=2.31.0', 'pandas']
        """
        metadata = PEP723Parser.parse_metadata(script_body, script_name)

        if not metadata:
            return []

        dependencies = metadata.get("dependencies", [])

        if not isinstance(dependencies, list):
            raise DependencyParseError(
                "'dependencies' must be a list",
                script_name,
            )

        return dependencies

    @staticmethod
    def extract_python_version(script_body: str, script_name: str | None = None) -> str | None:
        """Extract Python version requirement from script metadata.

        Args:
            script_body: Python script source code
            script_name: Optional script name for error messages

        Returns:
            Python version requirement string or None

        Examples:
            >>> script = '''
            ... # /// script
            ... # requires-python = ">=3.12"
            ... # ///
            ... '''
            >>> PEP723Parser.extract_python_version(script)
            '>=3.12'
        """
        metadata = PEP723Parser.parse_metadata(script_body, script_name)

        if not metadata:
            return None

        return metadata.get("requires-python")

    @staticmethod
    def merge_dependencies(*scripts_bodies: str) -> list[str]:
        """Merge dependencies from multiple scripts, removing duplicates.

        Args:
            *scripts_bodies: Variable number of script source codes

        Returns:
            Deduplicated list of all dependencies

        Examples:
            >>> script1 = '''
            ... # /// script
            ... # dependencies = ["requests>=2.31.0"]
            ... # ///
            ... '''
            >>> script2 = '''
            ... # /// script
            ... # dependencies = ["requests>=2.31.0", "pandas"]
            ... # ///
            ... '''
            >>> PEP723Parser.merge_dependencies(script1, script2)
            ['requests>=2.31.0', 'pandas']
        """
        all_deps: set[str] = set()

        for script_body in scripts_bodies:
            deps = PEP723Parser.extract_dependencies(script_body)
            all_deps.update(deps)

        return sorted(all_deps)

    @staticmethod
    def generate_metadata_block(
        dependencies: list[str] | None = None,
        python_version: str | None = None,
    ) -> str:
        """Generate a PEP 723 metadata block.

        Args:
            dependencies: List of dependency specifications
            python_version: Python version requirement

        Returns:
            Formatted metadata block string

        Examples:
            >>> block = PEP723Parser.generate_metadata_block(
            ...     dependencies=["requests>=2.31.0"],
            ...     python_version=">=3.12"
            ... )
            >>> print(block)
            # /// script
            # requires-python = ">=3.12"
            # dependencies = [
            #   "requests>=2.31.0",
            # ]
            # ///
        """
        lines = ["# /// script"]

        if python_version:
            lines.append(f'# requires-python = "{python_version}"')

        if dependencies:
            lines.append("# dependencies = [")
            for dep in dependencies:
                lines.append(f'#   "{dep}",')
            lines.append("# ]")

        lines.append("# ///")

        return "\n".join(lines)

    @staticmethod
    def add_metadata_to_script(
        script_body: str,
        dependencies: list[str] | None = None,
        python_version: str | None = None,
    ) -> str:
        """Add or update PEP 723 metadata in a script.

        If metadata already exists, it will be replaced.

        Args:
            script_body: Python script source code
            dependencies: List of dependency specifications
            python_version: Python version requirement

        Returns:
            Script with metadata block prepended
        """
        # Remove existing metadata if present
        if PEP723Parser.has_metadata(script_body):
            script_body = PEP723Parser._remove_metadata_block(script_body)

        # Generate new metadata block
        metadata_block = PEP723Parser.generate_metadata_block(
            dependencies=dependencies,
            python_version=python_version,
        )

        # Prepend to script
        return f"{metadata_block}\n\n{script_body}"

    @staticmethod
    def _remove_metadata_block(script_body: str) -> str:
        """Remove PEP 723 metadata block from script.

        Args:
            script_body: Python script source code

        Returns:
            Script without metadata block
        """
        lines = script_body.split("\n")
        result_lines = []
        in_block = False

        for line in lines:
            stripped = line.strip()

            if stripped == "# /// script":
                in_block = True
                continue

            if in_block and stripped == "# ///":
                in_block = False
                continue

            if not in_block:
                result_lines.append(line)

        # Remove leading empty lines after block removal
        while result_lines and not result_lines[0].strip():
            result_lines.pop(0)

        return "\n".join(result_lines)
