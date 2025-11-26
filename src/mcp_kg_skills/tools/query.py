"""Cypher query execution MCP tool."""

import logging
from typing import Any

from ..database.abstract import DatabaseInterface
from ..exceptions import InvalidQueryError, ValidationError
from ..security.secrets import SecretDetector

logger = logging.getLogger(__name__)


class QueryTool:
    """Handles read-only Cypher query execution."""

    def __init__(self, db: DatabaseInterface, secret_detector: SecretDetector):
        """Initialize query tool.

        Args:
            db: Database interface
            secret_detector: Secret detector for sanitizing results
        """
        self.db = db
        self.secret_detector = secret_detector

    async def handle(
        self,
        cypher: str,
        parameters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Execute a read-only Cypher query.

        Args:
            cypher: Cypher query string
            parameters: Query parameters
            limit: Maximum number of results

        Returns:
            Query results (sanitized)

        Raises:
            ValidationError: If parameters are invalid
            InvalidQueryError: If query is not read-only or is malformed
        """
        # Validate query
        if not cypher or not cypher.strip():
            raise ValidationError("cypher query cannot be empty")

        # Validate limit
        if limit < 1:
            raise ValidationError("limit must be at least 1")
        if limit > 1000:
            raise ValidationError("limit cannot exceed 1000")

        # Validate query is read-only
        is_readonly, violation = self._is_readonly_query(cypher)
        if not is_readonly:
            raise InvalidQueryError(
                f"Query contains write operation '{violation}' which is not allowed. "
                "Only read-only operations are permitted: MATCH, RETURN, WITH, WHERE, "
                "ORDER BY, SKIP, LIMIT. Use the nodes/relationships tools to modify data."
            )

        try:
            logger.info(f"Executing Cypher query (limit: {limit})")
            logger.debug(f"Query: {cypher}")

            # Execute query
            results = await self.db.execute_query(
                cypher=cypher,
                parameters=parameters or {},
                limit=limit,
            )

            # Sanitize results (remove any secrets that might appear)
            # Note: In practice, secrets shouldn't appear in query results,
            # but we sanitize as a safety measure
            sanitized_results = self._sanitize_results(results)

            logger.info(f"Query returned {len(sanitized_results)} results")

            return {
                "success": True,
                "results": sanitized_results,
                "count": len(sanitized_results),
                "limit": limit,
            }

        except InvalidQueryError:
            raise
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise InvalidQueryError(f"Query execution failed: {e}")

    def _is_readonly_query(self, cypher: str) -> tuple[bool, str | None]:
        """Check if a Cypher query is read-only.

        Args:
            cypher: Cypher query string

        Returns:
            Tuple of (is_readonly, violation_keyword):
            - is_readonly: True if query is read-only, False otherwise
            - violation_keyword: The write keyword found, or None if read-only
        """
        cypher_upper = cypher.upper()

        # List of write operations that are not allowed
        write_keywords = [
            "CREATE ",
            "DELETE ",
            "REMOVE ",
            "SET ",
            "MERGE ",
            "DETACH ",
            "DROP ",
        ]

        for keyword in write_keywords:
            if keyword in cypher_upper:
                logger.warning(f"Query contains write keyword: {keyword.strip()}")
                return False, keyword.strip()

        return True, None

    def _sanitize_results(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sanitize query results to remove any potential secrets.

        Args:
            results: Raw query results

        Returns:
            Sanitized results
        """
        # For ENV nodes, sanitize the variables field
        sanitized = []

        for result in results:
            sanitized_result = {}

            for key, value in result.items():
                if isinstance(value, dict):
                    # Check if this looks like an ENV node
                    if "variables" in value and "secret_keys" in value:
                        sanitized_value = dict(value)
                        sanitized_value["variables"] = (
                            self.secret_detector.sanitize_env_response(
                                value.get("variables", {}),
                                value.get("secret_keys", []),
                            )
                        )
                        sanitized_result[key] = sanitized_value
                    else:
                        sanitized_result[key] = value
                else:
                    sanitized_result[key] = value

            sanitized.append(sanitized_result)

        return sanitized
