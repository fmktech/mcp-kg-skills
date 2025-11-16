"""Unit tests for security module."""

import pytest

from mcp_kg_skills.security.secrets import SecretDetector, extract_secrets, is_secret


class TestSecretDetector:
    """Tests for SecretDetector class."""

    def test_default_patterns(self):
        """Test secret detection with default patterns."""
        detector = SecretDetector()

        # Should be detected as secrets
        assert detector.is_secret("SECRET_KEY")
        assert detector.is_secret("MY_SECRET")
        assert detector.is_secret("DATABASE_PASSWORD")
        assert detector.is_secret("API_KEY")
        assert detector.is_secret("PRIVATE_KEY")
        assert detector.is_secret("AUTH_TOKEN")
        assert detector.is_secret("AWS_SECRET_ACCESS_KEY")

        # Should NOT be detected as secrets
        assert not detector.is_secret("DATABASE_HOST")
        assert not detector.is_secret("DATABASE_PORT")
        assert not detector.is_secret("LOG_LEVEL")
        assert not detector.is_secret("APP_NAME")

    def test_custom_patterns(self):
        """Test secret detection with custom patterns."""
        detector = SecretDetector(secret_patterns=[r"^CUSTOM_", r"_PRIVATE$"])

        assert detector.is_secret("CUSTOM_VALUE")
        assert detector.is_secret("MY_PRIVATE")
        assert not detector.is_secret("NORMAL_VALUE")

    def test_extract_secrets(self):
        """Test separating public and secret variables."""
        detector = SecretDetector()

        variables = {
            "DATABASE_HOST": "localhost",
            "DATABASE_PORT": "5432",
            "DATABASE_PASSWORD": "secret123",
            "API_KEY": "abc123",
            "LOG_LEVEL": "INFO",
        }

        public_vars, secret_keys, secret_values = detector.extract_secrets(variables)

        assert public_vars == {
            "DATABASE_HOST": "localhost",
            "DATABASE_PORT": "5432",
            "LOG_LEVEL": "INFO",
        }
        assert set(secret_keys) == {"DATABASE_PASSWORD", "API_KEY"}
        assert secret_values == {
            "DATABASE_PASSWORD": "secret123",
            "API_KEY": "abc123",
        }

    def test_sanitize_env_response(self):
        """Test sanitizing environment variables for API responses."""
        detector = SecretDetector()

        variables = {
            "DATABASE_HOST": "localhost",
            "DATABASE_PASSWORD": "secret123",
            "API_KEY": "abc123",
        }
        secret_keys = ["DATABASE_PASSWORD", "API_KEY"]

        sanitized = detector.sanitize_env_response(variables, secret_keys)

        assert sanitized == {
            "DATABASE_HOST": "localhost",
            "DATABASE_PASSWORD": "<SECRET>",
            "API_KEY": "<SECRET>",
        }

    def test_sanitize_output(self):
        """Test sanitizing execution output."""
        detector = SecretDetector()

        output = "Connecting with password: secret123 and API key: abc123"
        secrets = ["secret123", "abc123"]

        sanitized = detector.sanitize_output(output, secrets)

        assert sanitized == "Connecting with password: <REDACTED> and API key: <REDACTED>"

    def test_sanitize_output_empty_secrets(self):
        """Test sanitizing output with empty secret list."""
        detector = SecretDetector()

        output = "Normal output without secrets"
        sanitized = detector.sanitize_output(output, [])

        assert sanitized == output

    def test_sanitize_output_empty_string_secrets(self):
        """Test sanitizing output handles empty string secrets."""
        detector = SecretDetector()

        output = "Some output"
        secrets = ["", "actual_secret"]

        sanitized = detector.sanitize_output(output.replace("output", "actual_secret"), secrets)
        assert "<REDACTED>" in sanitized

    def test_sanitize_dict(self):
        """Test recursively sanitizing dictionaries."""
        detector = SecretDetector()

        data = {
            "config": {
                "password": "secret123",
                "host": "localhost",
            },
            "output": "Password is secret123",
            "nested": {
                "deep": {
                    "value": "The secret is secret123",
                }
            },
        }
        secrets = ["secret123"]

        sanitized = detector.sanitize_dict(data, secrets)

        assert sanitized["config"]["password"] == "<REDACTED>"
        assert sanitized["config"]["host"] == "localhost"
        assert sanitized["output"] == "Password is <REDACTED>"
        assert sanitized["nested"]["deep"]["value"] == "The secret is <REDACTED>"

    def test_sanitize_dict_with_lists(self):
        """Test sanitizing dictionaries containing lists."""
        detector = SecretDetector()

        data = {
            "items": ["value1", "secret123", "value2"],
            "config": {"key": "secret123"},
        }
        secrets = ["secret123"]

        sanitized = detector.sanitize_dict(data, secrets)

        assert sanitized["items"] == ["value1", "<REDACTED>", "value2"]
        assert sanitized["config"]["key"] == "<REDACTED>"

    def test_case_insensitive_detection(self):
        """Test that secret detection is case-insensitive."""
        detector = SecretDetector()

        assert detector.is_secret("api_key")
        assert detector.is_secret("API_KEY")
        assert detector.is_secret("Api_Key")
        assert detector.is_secret("database_password")
        assert detector.is_secret("DATABASE_PASSWORD")

    def test_convenience_functions(self):
        """Test convenience functions."""
        assert is_secret("API_KEY")
        assert not is_secret("DATABASE_HOST")

        variables = {
            "HOST": "localhost",
            "PASSWORD": "secret",
        }
        public, keys, values = extract_secrets(variables)

        assert "HOST" in public
        assert "PASSWORD" in keys


class TestSecretPatterns:
    """Test various secret naming patterns."""

    @pytest.mark.parametrize(
        "var_name,should_be_secret",
        [
            ("SECRET_KEY", True),
            ("MY_SECRET", True),
            ("APP_SECRET", True),
            ("DATABASE_PASSWORD", True),
            ("USER_PASSWORD", True),
            ("API_KEY", True),
            ("AWS_ACCESS_KEY", True),
            ("PRIVATE_KEY", True),
            ("RSA_PRIVATE_KEY", True),
            ("AUTH_TOKEN", True),
            ("ACCESS_TOKEN", True),
            ("REFRESH_TOKEN", True),
            ("JWT_TOKEN", True),
            ("API_SECRET", True),
            ("CLIENT_SECRET", True),
            # Non-secrets
            ("DATABASE_HOST", False),
            ("DATABASE_PORT", False),
            ("DATABASE_NAME", False),
            ("API_URL", False),
            ("API_ENDPOINT", False),
            ("LOG_LEVEL", False),
            ("DEBUG_MODE", False),
            ("APP_NAME", False),
            ("ENVIRONMENT", False),
        ],
    )
    def test_secret_pattern_detection(self, var_name, should_be_secret):
        """Test comprehensive secret pattern detection."""
        detector = SecretDetector()
        assert detector.is_secret(var_name) == should_be_secret
