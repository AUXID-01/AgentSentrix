import os
import sys
import stat
import logging
from typing import Optional

logger = logging.getLogger("agentsentrix.sensors.shim.manager")

SHIM_TARGETS = ["bash", "rm", "curl", "git", "aws"]

class ShimManager:
    """Manages installation, generation, and environment wiring for PATH binary shims."""

    def __init__(self, shim_dir: Optional[str] = None) -> None:
        if shim_dir is None:
            base_dir = os.path.dirname(__file__)
            shim_dir = os.path.join(base_dir, "bin")

        self.shim_dir = os.path.abspath(shim_dir)

    def install_shims(self, targets: Optional[list[str]] = None) -> str:
        """
        Generate cross-platform executable shim scripts (POSIX bash scripts and Windows .cmd files)
        for target binaries in the shim directory.
        """
        os.makedirs(self.shim_dir, exist_ok=True)
        tools = targets or SHIM_TARGETS
        python_exe = sys.executable

        for tool in tools:
            # 1. POSIX Executable Shell Script
            posix_path = os.path.join(self.shim_dir, tool)
            posix_content = (
                f"#!/bin/sh\n"
                f'exec "{python_exe}" -m core.agentsentrix.sensors.shim.runner {tool} "$@"\n'
            )
            with open(posix_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(posix_content)

            # Set POSIX executable bit (rwxr-xr-x)
            try:
                os.chmod(posix_path, os.stat(posix_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except Exception as exc:
                logger.warning(f"Could not set execute permissions on {posix_path}: {exc}")

            # 2. Windows CMD Batch Wrapper
            win_cmd_path = os.path.join(self.shim_dir, f"{tool}.cmd")
            win_cmd_content = (
                f"@echo off\n"
                f'"{python_exe}" -m core.agentsentrix.sensors.shim.runner {tool} %*\n'
            )
            with open(win_cmd_path, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(win_cmd_content)

            # Also create .bat alias for Windows CMD compatibility
            win_bat_path = os.path.join(self.shim_dir, f"{tool}.bat")
            with open(win_bat_path, "w", encoding="utf-8", newline="\r\n") as f:
                f.write(win_cmd_content)

        logger.info(f"Successfully installed {len(tools)} PATH binary shims to {self.shim_dir}")
        return self.shim_dir

    def get_env_with_shims(self, base_env: Optional[dict[str, str]] = None) -> dict[str, str]:
        """
        Return a copy of environment variables with the shim directory prepended to PATH.
        """
        env = (base_env or os.environ).copy()
        current_path = env.get("PATH", "")
        env["PATH"] = f"{self.shim_dir}{os.pathsep}{current_path}"
        return env
