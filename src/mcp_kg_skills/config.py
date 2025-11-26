"""Configuration management for MCP Knowledge Graph Skills."""

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseSettings):
    """Neo4j database configuration."""

    uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j connection URI",
    )
    username: str = Field(default="neo4j", description="Database username")
    password: str = Field(..., description="Database password")
    database: str = Field(default="neo4j", description="Database name")

    model_config = SettingsConfigDict(
        env_prefix="NEO4J_",
        case_sensitive=False,
    )


class ExecutionConfig(BaseSettings):
    """Script execution configuration."""

    cache_dir: Path = Field(
        default="~/.mcp-kg-skills/cache",
        description="Directory for execution cache",
    )
    env_dir: Path = Field(
        default="~/.mcp-kg-skills/envs",
        description="Directory for ENV files",
    )
    default_timeout: int = Field(
        default=300,
        ge=1,
        le=3600,
        description="Default execution timeout in seconds",
    )
    max_timeout: int = Field(
        default=600,
        ge=1,
        le=3600,
        description="Maximum allowed execution timeout",
    )

    @field_validator("cache_dir", "env_dir", mode="before")
    @classmethod
    def expand_path(cls, v: Any) -> Path:
        """Expand and resolve path."""
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        return v

    model_config = SettingsConfigDict(
        env_prefix="EXECUTION_",
        case_sensitive=False,
    )


class SecurityConfig(BaseSettings):
    """Security configuration."""

    secret_patterns: list[str] = Field(
        default=[
            "SECRET_*",
            "*_SECRET",
            "*_KEY",
            "*_PASSWORD",
            "*_TOKEN",
            "*_API_KEY",
            "*_PRIVATE_KEY",
            "^API_KEY",
            "^PRIVATE_KEY",
        ],
        description="Patterns for detecting secret variable names",
    )

    model_config = SettingsConfigDict(
        env_prefix="SECURITY_",
        case_sensitive=False,
    )


class LoggingConfig(BaseSettings):
    """Logging configuration."""

    level: str = Field(
        default="INFO",
        description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v_upper

    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        case_sensitive=False,
    )


class AppConfig(BaseSettings):
    """Main application configuration."""

    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig,
        description="Database configuration",
    )
    execution: ExecutionConfig = Field(
        default_factory=ExecutionConfig,
        description="Execution configuration",
    )
    security: SecurityConfig = Field(
        default_factory=SecurityConfig,
        description="Security configuration",
    )
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig,
        description="Logging configuration",
    )

    model_config = SettingsConfigDict(
        case_sensitive=False,
    )

    @classmethod
    def load_from_file(cls, config_path: Path | str) -> "AppConfig":
        """Load configuration from YAML file.

        Supports environment variable substitution in the format ${VAR_NAME}.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            AppConfig instance

        Raises:
            ConfigurationError: If file doesn't exist or is invalid
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path) as f:
                raw_content = f.read()

            # Substitute environment variables
            content = cls._substitute_env_vars(raw_content)

            # Parse YAML
            data = yaml.safe_load(content)

            if not data:
                raise ConfigurationError("Configuration file is empty")

            # Create config from dict
            return cls(**data)

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in config file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")

    @classmethod
    def load_from_file_or_defaults(cls, config_path: Path | str | None = None) -> "AppConfig":
        """Load configuration from file if it exists, otherwise use defaults.

        Args:
            config_path: Optional path to YAML configuration file

        Returns:
            AppConfig instance
        """
        if config_path:
            config_path = Path(config_path)
            if config_path.exists():
                logger.info(f"Loading configuration from {config_path}")
                return cls.load_from_file(config_path)
            else:
                logger.warning(f"Configuration file not found: {config_path}. Using defaults.")

        logger.info("Using default configuration")
        return cls()

    @staticmethod
    def _substitute_env_vars(content: str) -> str:
        """Substitute environment variables in configuration content.

        Replaces ${VAR_NAME} or $VAR_NAME with environment variable values.

        Args:
            content: Raw configuration content

        Returns:
            Content with environment variables substituted
        """
        # Pattern for ${VAR_NAME} or $VAR_NAME
        pattern = r"\$\{([^}]+)\}|\$([A-Z_][A-Z0-9_]*)"

        def replace_var(match: re.Match) -> str:
            var_name = match.group(1) or match.group(2)
            value = os.environ.get(var_name)

            if value is None:
                logger.warning(f"Environment variable '{var_name}' not found, leaving placeholder")
                return match.group(0)

            return value

        return re.sub(pattern, replace_var, content)

    def setup_logging(self) -> None:
        """Configure Python logging based on settings."""
        logging.basicConfig(
            level=getattr(logging, self.logging.level),
            format=self.logging.format,
        )
        logger.info(f"Logging configured at {self.logging.level} level")

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.execution.cache_dir.mkdir(parents=True, exist_ok=True)
        self.execution.env_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured all required directories exist")


def get_default_config_path() -> Path:
    """Get the default configuration file path.

    Returns:
        Path to ~/.mcp-kg-skills/config/database.yaml
    """
    return Path("~/.mcp-kg-skills/config/database.yaml").expanduser()


def load_config(config_path: Path | str | None = None) -> AppConfig:
    """Load application configuration.

    Args:
        config_path: Optional path to configuration file.
                    If None, uses default path.

    Returns:
        AppConfig instance
    """
    if config_path is None:
        config_path = get_default_config_path()

    return AppConfig.load_from_file_or_defaults(config_path)
