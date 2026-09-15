from typing import Any

class TerminalMCPServer:
    """Mock Terminal Runner MCP Server exposing shell command execution tool."""

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "run_command",
                "description": "Execute a shell command",
                "inputSchema": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"]
                }
            }
        ]

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "run_command":
            command = arguments.get("command", "")
            return {"content": [{"type": "text", "text": f"Executed command '{command}' successfully. Exit code: 0"}], "isError": False}
        else:
            return {"content": [{"type": "text", "text": f"Unknown terminal tool: {name}"}], "isError": True}
