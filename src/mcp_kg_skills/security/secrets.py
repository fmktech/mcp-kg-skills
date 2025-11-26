"""Secret detection and sanitization for MCP Knowledge Graph Skills."""

import re
from typing import Any


class SecretDetector:
    """Detects and manages secret environment variables."""

    # Default patterns for detecting secret variable names
    DEFAULT_SECRET_PATTERNS = [
        r"^SECRET_",
        r"_SECRET$",
        r"^.*_KEY$",
        r"^.*_PASSWORD$",
        r"^.*_TOKEN$",
        r"^.*_API_KEY$",
        r"^.*_PRIVATE_KEY$",
        r"^API_KEY",
        r"^PRIVATE_KEY",
        r"^PASSWORD",
        r"^TOKEN",
    ]

    def __init__(self, secret_patterns: list[str] | None = None):
        """Initialize secret detector.

        Args:
            secret_patterns: List of regex patterns to match secret variable names.
                           If None, uses DEFAULT_SECRET_PATTERNS.
        """
        patterns = secret_patterns or self.DEFAULT_SECRET_PATTERNS
        self.secret_regex = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    def is_secret(self, key: str) -> bool:
        """Check if a variable name matches secret patterns.

        Args:
            key: Variable name to check

        Returns:
            True if the key matches any secret pattern, False otherwise

        Examples:
            >>> detector = SecretDetector()
            >>> detector.is_secret("DATABASE_PASSWORD")
            True
            >>> detector.is_secret("DATABASE_HOST")
            False
            >>> detector.is_secret("SECRET_KEY")
            True
            >>> detector.is_secret("MY_API_KEY")
            True
        """
        for regex in self.secret_regex:
            if regex.search(key):
                return True
        return False

    def extract_secrets(
        self, variables: dict[str, str]
    ) -> tuple[dict[str, str], list[str], dict[str, str]]:
        """Separate public variables, secret keys, and secret values.

        Args:
            variables: Dictionary of environment variables

        Returns:
            Tuple of (public_vars, secret_keys, secret_values):
            - public_vars: Variables that are not secrets
            - secret_keys: List of secret variable names
            - secret_values: Dictionary of secret key-value pairs

        Examples:
            >>> detector = SecretDetector()
            >>> vars = {
            ...     "DATABASE_HOST": "localhost",
            ...     "DATABASE_PASSWORD": "secret123",
            ...     "API_KEY": "abc123"
            ... }
            >>> public, keys, values = detector.extract_secrets(vars)
            >>> public
            {'DATABASE_HOST': 'localhost'}
            >>> keys
            ['DATABASE_PASSWORD', 'API_KEY']
            >>> values
            {'DATABASE_PASSWORD': 'secret123', 'API_KEY': 'abc123'}
        """
        public_vars: dict[str, str] = {}
        secret_keys: list[str] = []
        secret_values: dict[str, str] = {}

        for key, value in variables.items():
            if self.is_secret(key):
                secret_keys.append(key)
                secret_values[key] = value
            else:
                public_vars[key] = value

        return public_vars, secret_keys, secret_values

    def sanitize_env_response(
        self, variables: dict[str, str], secret_keys: list[str]
    ) -> dict[str, str]:
        """Replace secret values with placeholder for LLM responses.

        Args:
            variables: Dictionary of all variables
            secret_keys: List of keys that are secrets

        Returns:
            Dictionary with secret values replaced by "<SECRET>"

        Examples:
            >>> detector = SecretDetector()
            >>> vars = {
            ...     "DATABASE_HOST": "localhost",
            ...     "DATABASE_PASSWORD": "secret123"
            ... }
            >>> sanitized = detector.sanitize_env_response(vars, ["DATABASE_PASSWORD"])
            >>> sanitized
            {'DATABASE_HOST': 'localhost', 'DATABASE_PASSWORD': '<SECRET>'}
        """
        result = dict(variables)
        for key in secret_keys:
            if key in result:
                result[key] = "<SECRET>"
        return result

    def sanitize_output(self, text: str, secrets: list[str]) -> str:
        """Remove secret values from execution output.

        Args:
            text: Output text to sanitize
            secrets: List of secret values to remove

        Returns:
            Text with all secret values replaced by "<REDACTED>"

        Examples:
            >>> detector = SecretDetector()
            >>> output = "Connected to DB with password: secret123"
            >>> sanitized = detector.sanitize_output(output, ["secret123"])
            >>> sanitized
            'Connected to DB with password: <REDACTED>'
        """
        sanitized = text
        for secret in secrets:
            if secret and len(secret) > 0:
                # Replace all occurrences of the secret value
                sanitized = sanitized.replace(secret, "<REDACTED>")
        return sanitized

    def sanitize_dict(self, data: dict[str, Any], secrets: list[str]) -> dict[str, Any]:
        """Recursively sanitize dictionaries containing potential secrets.

        Args:
            data: Dictionary to sanitize
            secrets: List of secret values to remove

        Returns:
            Sanitized dictionary with secrets replaced

        Examples:
            >>> detector = SecretDetector()
            >>> data = {
            ...     "config": {
            ...         "password": "secret123",
            ...         "host": "localhost"
            ...     },
            ...     "output": "Password is secret123"
            ... }
            >>> sanitized = detector.sanitize_dict(data, ["secret123"])
            >>> sanitized['output']
            'Password is <REDACTED>'
        """
        if not isinstance(data, dict):
            return data

        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.sanitize_output(value, secrets)
            elif isinstance(value, dict):
                result[key] = self.sanitize_dict(value, secrets)
            elif isinstance(value, list):
                result[key] = [
                    self.sanitize_output(item, secrets) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value

        return result

    def merge_env_vars(
        self,
        *env_dicts: dict[str, Any],
    ) -> tuple[dict[str, str], list[str]]:
        """Merge multiple environment variable dictionaries.

        Args:
            *env_dicts: Variable number of ENV node dictionaries

        Returns:
            Tuple of (all_variables, all_secret_values):
            - all_variables: Merged dictionary of all variables
            - all_secret_values: List of all secret values for sanitization

        Examples:
            >>> detector = SecretDetector()
            >>> env1 = {
            ...     "variables": {"HOST": "localhost"},
            ...     "secret_keys": []
            ... }
            >>> env2 = {
            ...     "variables": {"PORT": "5432"},
            ...     "secret_keys": ["PASSWORD"]
            ... }
            >>> # Note: actual secret values would be in a separate secure storage
        """
        all_variables: dict[str, str] = {}
        all_secret_values: list[str] = []

        for env_dict in env_dicts:
            # Merge public variables
            variables = env_dict.get("variables", {})
            all_variables.update(variables)

            # Collect secret keys (actual values would come from .env files)
            env_dict.get("secret_keys", [])

            # In practice, secret values would be loaded from .env files
            # For now, we just track that these keys exist
            # The actual values will be loaded by the env file manager

        return all_variables, all_secret_values


# Global instance for convenience
_default_detector: SecretDetector | None = None


def get_default_detector() -> SecretDetector:
    """Get the default global secret detector instance."""
    global _default_detector
    if _default_detector is None:
        _default_detector = SecretDetector()
    return _default_detector


def is_secret(key: str) -> bool:
    """Check if a variable name is a secret (convenience function)."""
    return get_default_detector().is_secret(key)


def sanitize_output(text: str, secrets: list[str]) -> str:
    """Sanitize output text (convenience function)."""
    return get_default_detector().sanitize_output(text, secrets)


def extract_secrets(variables: dict[str, str]) -> tuple[dict[str, str], list[str], dict[str, str]]:
    """Extract secrets from variables (convenience function)."""
    return get_default_detector().extract_secrets(variables)
