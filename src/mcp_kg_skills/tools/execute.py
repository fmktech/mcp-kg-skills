"""Script execution MCP tool."""

import logging
from typing import Any

from ..exceptions import ScriptExecutionError, ValidationError
from ..execution.runner import ScriptRunner

logger = logging.getLogger(__name__)


class ExecuteTool:
    """Handles Python script execution with dynamic imports."""

    def __init__(self, runner: ScriptRunner):
        """Initialize execute tool.

        Args:
            runner: Script runner instance
        """
        self.runner = runner

    async def handle(
        self,
        code: str,
        imports: list[str] | None = None,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """Execute Python code with imported scripts.

        Args:
            code: Python code to execute
            imports: List of SCRIPT node names to import
            timeout: Execution timeout in seconds

        Returns:
            Execution result with sanitized output

        Raises:
            ValidationError: If parameters are invalid
            ScriptExecutionError: If execution fails
        """
        # Validate code
        if not code or not code.strip():
            raise ValidationError("code cannot be empty")

        # Validate timeout
        if timeout < 1:
            raise ValidationError("timeout must be at least 1 second")
        if timeout > 600:
            raise ValidationError("timeout cannot exceed 600 seconds")

        # Validate imports
        imports = imports or []
        if not isinstance(imports, list):
            raise ValidationError("imports must be a list of script names")

        try:
            logger.info(
                f"Executing code with {len(imports)} imports (timeout: {timeout}s)"
            )

            # Execute with runner
            result = await self.runner.execute(
                code=code,
                imports=imports,
                timeout=timeout,
            )

            # Add execution metadata
            result["imports"] = imports
            result["timeout"] = timeout

            # Log result
            if result["success"]:
                logger.info(
                    f"Execution completed successfully in {result['execution_time']:.2f}s"
                )
            else:
                logger.warning(
                    f"Execution failed with return code {result['return_code']}"
                )

            return result

        except ScriptExecutionError:
            raise
        except Exception as e:
            logger.error(f"Execution error: {e}")
            raise ScriptExecutionError(f"Execution failed: {e}")
