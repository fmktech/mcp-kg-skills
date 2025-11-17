"""Script execution runner with uv integration."""

import asyncio
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from ..database.abstract import DatabaseInterface
from ..exceptions import NodeNotFoundError, ScriptExecutionError
from ..security.secrets import SecretDetector
from ..utils.env_file import EnvFileManager
from .dependency import PEP723Parser

logger = logging.getLogger(__name__)


class ScriptRunner:
    """Executes Python scripts with dynamic imports and dependency management."""

    def __init__(
        self,
        db: DatabaseInterface,
        cache_dir: Path | str,
        env_dir: Path | str,
        secret_detector: SecretDetector | None = None,
    ):
        """Initialize script runner.

        Args:
            db: Database interface for loading scripts and ENVs
            cache_dir: Directory for caching execution artifacts
            env_dir: Directory where ENV files are stored
            secret_detector: Secret detector for sanitizing output (optional)
        """
        self.db = db
        self.cache_dir = Path(cache_dir)
        self.env_dir = Path(env_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.env_manager = EnvFileManager(env_dir)
        self.secret_detector = secret_detector or SecretDetector()

    async def execute(
        self,
        code: str,
        imports: list[str] | None = None,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """Execute Python code with imported scripts.

        Execution flow:
        1. Load SCRIPT nodes by name
        2. For each script, find connected ENV nodes
        3. Parse PEP 723 dependencies from all scripts
        4. Generate composite script with all imports
        5. Create temporary .env file with merged environment
        6. Execute with 'uv run --script <file>'
        7. Sanitize output (remove secrets)
        8. Return results

        Args:
            code: Python code to execute
            imports: List of SCRIPT node names to import
            timeout: Execution timeout in seconds

        Returns:
            Dictionary with execution results:
            {
                'success': bool,
                'stdout': str (sanitized),
                'stderr': str (sanitized),
                'return_code': int,
                'execution_time': float
            }

        Raises:
            NodeNotFoundError: If any imported script doesn't exist
            ScriptExecutionError: If execution fails
        """
        imports = imports or []
        start_time = time.time()

        try:
            # Load all requested scripts
            scripts = await self._load_scripts(imports)

            # Load and merge environment variables
            env_vars, secret_values = await self._load_environments(scripts)

            # Merge dependencies from all scripts
            merged_deps = self._merge_dependencies(scripts)

            # Generate composite script
            composite_script = self._generate_composite_script(
                scripts, code, merged_deps
            )

            # Create temporary script file
            script_file = self._create_temp_script_file(composite_script)

            # Create temporary .env file if we have env vars
            env_file = None
            if env_vars:
                env_file = self.env_manager.create_temp_env_file(env_vars, prefix="exec")

            try:
                # Execute with uv
                result = await self._execute_with_uv(
                    script_file, env_file, timeout
                )

                execution_time = time.time() - start_time

                # Sanitize output to remove secrets
                sanitized_result = self._sanitize_result(result, secret_values)
                sanitized_result["execution_time"] = execution_time

                logger.info(
                    f"Script execution completed in {execution_time:.2f}s "
                    f"(return code: {result['return_code']})"
                )

                return sanitized_result

            finally:
                # Cleanup temporary files
                script_file.unlink(missing_ok=True)
                if env_file:
                    env_file.unlink(missing_ok=True)

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Script execution failed after {execution_time:.2f}s: {e}")

            if isinstance(e, (NodeNotFoundError, ScriptExecutionError)):
                raise

            raise ScriptExecutionError(f"Execution failed: {e}")

    async def _load_scripts(self, script_names: list[str]) -> list[dict[str, Any]]:
        """Load SCRIPT nodes by name.

        Args:
            script_names: List of script names to load

        Returns:
            List of script node dictionaries

        Raises:
            NodeNotFoundError: If any script doesn't exist
        """
        scripts = []

        for name in script_names:
            script = await self.db.read_node_by_name("SCRIPT", name)
            if not script:
                raise NodeNotFoundError(name, "SCRIPT")
            scripts.append(script)

        logger.debug(f"Loaded {len(scripts)} scripts: {script_names}")
        return scripts

    async def _load_environments(
        self, scripts: list[dict[str, Any]]
    ) -> tuple[dict[str, str], list[str]]:
        """Load and merge environment variables from connected ENV nodes.

        Args:
            scripts: List of script node dictionaries

        Returns:
            Tuple of (all_variables, secret_values):
            - all_variables: Merged environment variables
            - secret_values: List of secret values for sanitization
        """
        all_variables: dict[str, str] = {}
        secret_values: list[str] = []

        for script in scripts:
            script_id = script["id"]

            # Find connected ENV nodes via CONTAINS relationship
            env_nodes = await self.db.get_connected_nodes(
                script_id, rel_type="CONTAINS", direction="outgoing"
            )

            for env_node in env_nodes:
                # Check if this is an ENV node
                if "variables" not in env_node:
                    continue

                env_id = env_node["id"]

                # Load full env vars from .env file
                if self.env_manager.env_file_exists(env_id):
                    env_file_vars = self.env_manager.read_env_file(env_id)
                    all_variables.update(env_file_vars)

                    # Collect secret values for sanitization
                    secret_keys = env_node.get("secret_keys", [])
                    for key in secret_keys:
                        if key in env_file_vars:
                            secret_values.append(env_file_vars[key])

        logger.debug(
            f"Loaded {len(all_variables)} environment variables "
            f"({len(secret_values)} secrets)"
        )

        return all_variables, secret_values

    def _merge_dependencies(self, scripts: list[dict[str, Any]]) -> list[str]:
        """Merge dependencies from all scripts.

        Args:
            scripts: List of script node dictionaries

        Returns:
            Deduplicated list of all dependencies
        """
        all_deps: set[str] = set()

        for script in scripts:
            body = script.get("body", "")
            deps = PEP723Parser.extract_dependencies(body, script.get("name"))
            all_deps.update(deps)

        merged = sorted(list(all_deps))
        logger.debug(f"Merged {len(merged)} unique dependencies")
        return merged

    def _generate_composite_script(
        self,
        scripts: list[dict[str, Any]],
        user_code: str,
        merged_deps: list[str],
    ) -> str:
        """Generate executable Python script with all imports.

        Args:
            scripts: List of script node dictionaries
            user_code: User's code to execute
            merged_deps: Merged list of dependencies

        Returns:
            Complete executable Python script
        """
        lines = []

        # Add PEP 723 metadata block with merged dependencies
        if merged_deps:
            metadata_block = PEP723Parser.generate_metadata_block(
                dependencies=merged_deps,
                python_version=">=3.12",
            )
            lines.append(metadata_block)
            lines.append("")

        # Add each imported script
        for script in scripts:
            script_name = script.get("name", "unknown")
            body = script.get("body", "")

            # Remove PEP 723 metadata from individual scripts
            if PEP723Parser.has_metadata(body):
                body = PEP723Parser._remove_metadata_block(body)

            lines.append(f"# Script: {script_name}")
            lines.append(body.strip())
            lines.append("")

        # Add user's code
        lines.append("# User Code")
        lines.append(user_code.strip())
        lines.append("")

        composite = "\n".join(lines)
        logger.debug(f"Generated composite script ({len(lines)} lines)")
        return composite

    def _create_temp_script_file(self, script_content: str) -> Path:
        """Create temporary script file.

        Args:
            script_content: Python script content

        Returns:
            Path to temporary script file
        """
        import uuid

        script_id = uuid.uuid4().hex[:8]
        script_path = self.cache_dir / f"exec_{script_id}.py"

        with open(script_path, "w") as f:
            f.write(script_content)

        logger.debug(f"Created temporary script: {script_path}")
        return script_path

    async def _execute_with_uv(
        self,
        script_file: Path,
        env_file: Path | None,
        timeout: int,
    ) -> dict[str, Any]:
        """Execute script with uv run.

        Args:
            script_file: Path to script file
            env_file: Optional path to .env file
            timeout: Execution timeout in seconds

        Returns:
            Execution result dictionary

        Raises:
            ScriptExecutionError: If execution fails or times out
        """
        # Build uv command
        cmd = ["uv", "run", str(script_file)]

        # Set up environment - start with parent process env
        import os
        env = dict(os.environ)

        if env_file:
            # Load .env file and merge into environment
            env_vars = self.env_manager.load_env_to_dict(env_file)
            env.update(env_vars)

        try:
            logger.info(f"Executing script with uv: {script_file}")

            # Run the command with inherited + custom environment
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise ScriptExecutionError(
                    f"Script execution timed out after {timeout}s"
                )

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            return_code = process.returncode or 0

            success = return_code == 0

            return {
                "success": success,
                "stdout": stdout,
                "stderr": stderr,
                "return_code": return_code,
            }

        except FileNotFoundError:
            raise ScriptExecutionError(
                "uv not found. Please install uv: https://docs.astral.sh/uv/"
            )
        except Exception as e:
            raise ScriptExecutionError(f"Failed to execute script: {e}")

    def _sanitize_result(
        self, result: dict[str, Any], secret_values: list[str]
    ) -> dict[str, Any]:
        """Sanitize execution result to remove secrets.

        Args:
            result: Execution result dictionary
            secret_values: List of secret values to remove

        Returns:
            Sanitized result dictionary
        """
        sanitized = dict(result)

        if secret_values:
            sanitized["stdout"] = self.secret_detector.sanitize_output(
                result["stdout"], secret_values
            )
            sanitized["stderr"] = self.secret_detector.sanitize_output(
                result["stderr"], secret_values
            )

        return sanitized
