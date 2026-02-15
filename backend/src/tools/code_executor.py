"""Sandboxed code execution tool using RestrictedPython."""

import asyncio
import resource
import sys
import traceback
from io import StringIO
from typing import Any

# Import RestrictedPython for proper sandboxing
try:
    from RestrictedPython import compile_restricted
    from RestrictedPython.Guards import (
        guarded_iter_unpack_sequence,
        guarded_setattr,
        safer_getattr,
    )
    from RestrictedPython.PrintCollector import PrintCollector
    RESTRICTED_PYTHON_AVAILABLE = True
except ImportError:
    RESTRICTED_PYTHON_AVAILABLE = False
    PrintCollector = None  # type: ignore

from src.core.logging import get_logger

logger = get_logger(__name__)


# Safe built-ins that are allowed in the sandbox
SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bin": bin,
    "bool": bool,
    "bytes": bytes,
    "chr": chr,
    "complex": complex,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    # Type checking
    "type": type,
}


class RestrictedPythonExecutor:
    """Secure code executor using RestrictedPython."""

    def __init__(self, timeout: int = 10, memory_limit_mb: int = 100):
        self.timeout = timeout
        self.memory_limit_mb = memory_limit_mb

        if not RESTRICTED_PYTHON_AVAILABLE:
            logger.warning(
                "code_executor_restricted_python_not_available",
                message="RestrictedPython not installed, falling back to basic safety checks",
            )

    def _create_safe_globals(self) -> dict[str, Any]:
        """Create a restricted globals dict for code execution."""
        safe_globals = {
            "__builtins__": {
                **SAFE_BUILTINS,
                "_getiter_": iter,
                "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
                "_write_": lambda x: x,  # Safe write guard
                "_getattr_": safer_getattr,  # Safe attribute access
                "_setattr_": guarded_setattr,  # Safe attribute setting
                "_print_": PrintCollector,  # Safe print that collects output
            },
            "__name__": "__main__",
        }
        return safe_globals

    def _set_resource_limits(self):
        """Set resource limits for the execution."""
        # Set memory limit (in bytes)
        memory_limit = self.memory_limit_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
        except (ValueError, OSError):
            # RLIMIT_AS might not be available on all platforms
            logger.debug("code_executor_memory_limit_not_set")

        # Set CPU time limit (slightly more than timeout to catch runaway processes)
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (self.timeout + 1, self.timeout + 1))
        except (ValueError, OSError):
            logger.debug("code_executor_cpu_limit_not_set")

    async def execute(self, code: str) -> dict[str, Any]:
        """Execute Python code in a restricted environment.

        Args:
            code: Python code to execute

        Returns:
            Dict with success, stdout, stderr
        """
        logger.info("code_executor_starting", code_length=len(code))

        # Capture stderr
        stderr_buffer = StringIO()

        # Redirect stderr
        old_stderr = sys.stderr

        try:
            sys.stderr = stderr_buffer

            if RESTRICTED_PYTHON_AVAILABLE:
                result = await self._execute_restricted(code)
            else:
                result = await self._execute_basic(code)

            # Add captured stderr to result
            result["stderr"] = stderr_buffer.getvalue() + result.get("stderr", "")

            logger.info(
                "code_executor_completed",
                success=result["success"],
            )
            return result

        finally:
            # Restore stderr
            sys.stderr = old_stderr

    async def _execute_restricted(self, code: str) -> dict[str, Any]:
        """Execute code using RestrictedPython compilation."""
        try:
            # Step 1: Compile with restrictions
            # compile_restricted returns a code object or raises an exception with error details
            bytecode = compile_restricted(code, "<user_code>", "exec")

            # Step 2: Prepare safe execution environment
            safe_globals = self._create_safe_globals()
            safe_locals: dict[str, Any] = {}

            # Step 3: Execute with timeout and resource limits
            def run_code() -> None:
                self._set_resource_limits()
                exec(bytecode, safe_globals, safe_locals)

            # Run with timeout
            await asyncio.wait_for(asyncio.to_thread(run_code), timeout=self.timeout)

            # Collect printed output from PrintCollector
            printed_output = ""
            print_collector = safe_locals.get("_print")
            if print_collector and isinstance(print_collector, PrintCollector):
                # PrintCollector stores output in .txt attribute
                printed_output = "".join(str(x) for x in print_collector.txt)

            return {
                "success": True,
                "stdout": printed_output,
                "stderr": "",
            }

        except (SyntaxError, TypeError) as e:
            # These errors come from RestrictedPython when it detects unsafe code
            error_msg = str(e)
            if "Line" in error_msg and "is an invalid variable name" in error_msg:
                # This is a RestrictedPython security violation
                logger.warning(
                    "code_executor_blocked",
                    reason="RestrictedPython blocked unsafe code",
                )
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Security: Code contains unsafe operations that are not allowed",
                }
            # Regular syntax error
            logger.warning("code_executor_syntax_error", error=str(e))
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Syntax error: {str(e)}",
            }
        except TimeoutError:
            logger.warning("code_executor_timeout", timeout=self.timeout)
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout} seconds",
            }
        except MemoryError:
            logger.warning("code_executor_memory_limit_exceeded")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Memory limit exceeded ({self.memory_limit_mb}MB)",
            }
        except Exception as e:
            logger.error("code_executor_error", error=str(e), traceback=traceback.format_exc())
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
            }

    async def _execute_basic(self, code: str) -> dict[str, Any]:
        """Fallback execution with basic safety checks (when RestrictedPython unavailable)."""
        # Capture stdout for basic mode
        stdout_buffer = StringIO()
        old_stdout = sys.stdout

        # More comprehensive AST-based checks
        try:
            import ast

            tree = ast.parse(code)

            # Check for dangerous operations (Import, ImportFrom, Exec, Eval, Call)

            for node in ast.walk(tree):
                # Block imports
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module_names = []
                    if isinstance(node, ast.Import):
                        module_names = [alias.name for alias in node.names]
                    else:
                        module_names = [node.module or ""]

                    for module in module_names:
                        module_base = module.split(".")[0]
                        dangerous_modules = [
                            "os", "sys", "subprocess", "shutil", "socket",
                            "http", "urllib", "requests", "ftplib", "telnetlib",
                            "pickle", "shelve", "marshal", "importlib",
                            "ctypes", "multiprocessing", "threading",
                            "eval", "exec", "compile", "open", "__import__",
                        ]
                        if module_base in dangerous_modules:
                            logger.warning(
                                "code_executor_blocked",
                                reason=f"Dangerous module: {module}",
                            )
                            return {
                                "success": False,
                                "stdout": "",
                                "stderr": f"Security: Module '{module}' is not allowed",
                            }

                # Block attribute access on dangerous types
                if isinstance(node, ast.Call):
                    # Check for __import__, eval, exec calls
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ("__import__", "eval", "exec", "compile"):
                            logger.warning(
                                "code_executor_blocked",
                                reason=f"Dangerous function: {node.func.id}",
                            )
                            return {
                                "success": False,
                                "stdout": "",
                                "stderr": f"Security: Function '{node.func.id}' is not allowed",
                            }

            # Execute with restrictions
            safe_globals = {"__builtins__": SAFE_BUILTINS, "__name__": "__main__"}
            safe_locals: dict[str, Any] = {}

            try:
                sys.stdout = stdout_buffer

                def run_code() -> None:
                    self._set_resource_limits()
                    exec(code, safe_globals, safe_locals)

                await asyncio.wait_for(asyncio.to_thread(run_code), timeout=self.timeout)

                return {
                    "success": True,
                    "stdout": stdout_buffer.getvalue(),
                    "stderr": "",
                }
            finally:
                sys.stdout = old_stdout

        except SyntaxError as e:
            logger.warning("code_executor_syntax_error", error=str(e))
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Syntax error: {str(e)}",
            }
        except TimeoutError:
            logger.warning("code_executor_timeout", timeout=self.timeout)
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution timed out after {self.timeout} seconds",
            }
        except Exception as e:
            logger.error("code_executor_error", error=str(e))
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
            }


class CodeExecutorTool:
    """Sandboxed Python code executor with timeout and memory limits."""

    name = "code_executor"
    description = "Execute Python code in a sandboxed environment with RestrictedPython"

    def __init__(self, timeout: int = 10, memory_limit_mb: int = 100):
        """Initialize the code executor.

        Args:
            timeout: Maximum execution time in seconds
            memory_limit_mb: Maximum memory usage in megabytes
        """
        self.timeout = timeout
        self.memory_limit_mb = memory_limit_mb
        self._executor = RestrictedPythonExecutor(
            timeout=timeout,
            memory_limit_mb=memory_limit_mb,
        )

    async def execute(self, code: str) -> dict[str, Any]:
        """Execute Python code with proper sandboxing.

        This method uses RestrictedPython to compile and execute code in a
        restricted environment that blocks:
        - Dangerous imports (os, sys, subprocess, etc.)
        - Direct access to unsafe built-ins
        - Unauthorized attribute access

        Args:
            code: Python code to execute

        Returns:
            Dict with:
                - success: bool - Whether execution succeeded
                - stdout: str - Standard output
                - stderr: str - Standard error output
        """
        logger.info(
            "code_executor_execute",
            code_length=len(code),
            timeout=self.timeout,
            memory_limit_mb=self.memory_limit_mb,
        )

        result = await self._executor.execute(code)

        logger.info(
            "code_executor_result",
            success=result["success"],
            has_stdout=bool(result.get("stdout")),
            has_stderr=bool(result.get("stderr")),
        )

        return result
