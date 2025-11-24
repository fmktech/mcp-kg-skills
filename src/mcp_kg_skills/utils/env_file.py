"""Environment file management utilities."""

import logging
import os
from pathlib import Path
from typing import Any

from ..exceptions import EnvFileError

logger = logging.getLogger(__name__)


class EnvFileManager:
    """Manages .env files for ENV nodes."""

    def __init__(self, env_dir: Path | str):
        """Initialize environment file manager.

        Args:
            env_dir: Directory to store .env files (e.g., ~/.mcp-kg-skills/envs/)
        """
        self.env_dir = Path(env_dir)
        self.env_dir.mkdir(parents=True, exist_ok=True)

    def get_env_path(self, env_id: str) -> Path:
        """Get path to .env file for a given ENV node ID.

        Args:
            env_id: ENV node identifier

        Returns:
            Path to the .env file
        """
        return self.env_dir / f"{env_id}.env"

    def write_env_file(
        self,
        env_id: str,
        variables: dict[str, str],
        secret_variables: dict[str, str] | None = None,
    ) -> Path:
        """Write environment variables to .env file.

        Args:
            env_id: ENV node identifier
            variables: Public environment variables
            secret_variables: Secret environment variables (optional)

        Returns:
            Path to created .env file

        Raises:
            EnvFileError: If file write fails
        """
        env_path = self.get_env_path(env_id)

        try:
            # Combine public and secret variables
            all_vars = {**variables}
            if secret_variables:
                all_vars.update(secret_variables)

            # Write to file
            with open(env_path, "w") as f:
                for key, value in sorted(all_vars.items()):
                    # Escape values with quotes if they contain spaces or special chars
                    escaped_value = self._escape_env_value(value)
                    f.write(f"{key}={escaped_value}\n")

            # Set file permissions to 0600 (read/write for owner only) for security
            os.chmod(env_path, 0o600)

            logger.info(f"Created .env file: {env_path}")
            return env_path

        except Exception as e:
            raise EnvFileError(f"Failed to write .env file: {e}", env_id)

    def read_env_file(self, env_id: str) -> dict[str, str]:
        """Read environment variables from .env file.

        Args:
            env_id: ENV node identifier

        Returns:
            Dictionary of environment variables

        Raises:
            EnvFileError: If file read fails or doesn't exist
        """
        env_path = self.get_env_path(env_id)

        if not env_path.exists():
            raise EnvFileError(f".env file not found at {env_path}", env_id)

        try:
            variables = {}
            with open(env_path, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue

                    # Parse KEY=VALUE
                    if "=" not in line:
                        logger.warning(
                            f"Invalid line {line_num} in {env_path}: missing '='"
                        )
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = self._unescape_env_value(value.strip())

                    variables[key] = value

            logger.debug(f"Read {len(variables)} variables from {env_path}")
            return variables

        except Exception as e:
            raise EnvFileError(f"Failed to read .env file: {e}", env_id)

    def delete_env_file(self, env_id: str) -> bool:
        """Delete .env file for an ENV node.

        Args:
            env_id: ENV node identifier

        Returns:
            True if file was deleted, False if it didn't exist

        Raises:
            EnvFileError: If deletion fails
        """
        env_path = self.get_env_path(env_id)

        if not env_path.exists():
            return False

        try:
            env_path.unlink()
            logger.info(f"Deleted .env file: {env_path}")
            return True
        except Exception as e:
            raise EnvFileError(f"Failed to delete .env file: {e}", env_id)

    def env_file_exists(self, env_id: str) -> bool:
        """Check if .env file exists for an ENV node.

        Args:
            env_id: ENV node identifier

        Returns:
            True if file exists, False otherwise
        """
        return self.get_env_path(env_id).exists()

    def load_env_to_dict(self, env_path: Path | str) -> dict[str, str]:
        """Load .env file from arbitrary path.

        Args:
            env_path: Path to .env file

        Returns:
            Dictionary of environment variables

        Raises:
            EnvFileError: If file read fails
        """
        env_path = Path(env_path)

        if not env_path.exists():
            raise EnvFileError(f".env file not found at {env_path}")

        try:
            variables = {}
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if "=" in line:
                        key, value = line.split("=", 1)
                        variables[key.strip()] = self._unescape_env_value(value.strip())

            return variables

        except Exception as e:
            raise EnvFileError(f"Failed to load .env file: {e}")

    def merge_env_files(self, *env_ids: str) -> dict[str, str]:
        """Merge multiple .env files into a single dictionary.

        Later files override earlier ones for duplicate keys.

        Args:
            *env_ids: Variable number of ENV node IDs

        Returns:
            Merged dictionary of environment variables

        Raises:
            EnvFileError: If any file read fails
        """
        merged = {}

        for env_id in env_ids:
            variables = self.read_env_file(env_id)
            merged.update(variables)

        return merged

    @staticmethod
    def _escape_env_value(value: str) -> str:
        """Escape environment variable value for .env file.

        Args:
            value: Raw value

        Returns:
            Escaped value with quotes if needed
        """
        # If value contains spaces, special chars, or is empty, quote it
        if not value or any(c in value for c in [" ", "\n", "\t", "#", "$"]):
            # Escape quotes and backslashes
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return value

    @staticmethod
    def _unescape_env_value(value: str) -> str:
        """Unescape environment variable value from .env file.

        Args:
            value: Value from .env file (potentially quoted)

        Returns:
            Unescaped value
        """
        # Remove surrounding quotes if present
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
            # Unescape backslashes and quotes
            value = value.replace('\\"', '"').replace("\\\\", "\\")
        elif len(value) >= 2 and value[0] == "'" and value[-1] == "'":
            value = value[1:-1]

        return value

    def create_temp_env_file(
        self, variables: dict[str, str], prefix: str = "temp"
    ) -> Path:
        """Create a temporary .env file.

        Args:
            variables: Environment variables to write
            prefix: Prefix for temp file name

        Returns:
            Path to created temp file

        Raises:
            EnvFileError: If file creation fails
        """
        import tempfile
        import uuid

        temp_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
        temp_path = self.env_dir / f"{temp_id}.env"

        try:
            with open(temp_path, "w") as f:
                for key, value in sorted(variables.items()):
                    escaped_value = self._escape_env_value(value)
                    f.write(f"{key}={escaped_value}\n")

            os.chmod(temp_path, 0o600)
            logger.debug(f"Created temporary .env file: {temp_path}")
            return temp_path

        except Exception as e:
            raise EnvFileError(f"Failed to create temp .env file: {e}")
