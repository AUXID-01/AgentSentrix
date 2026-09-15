from typing import Any

class GitMCPServer:
    """Mock Git/Repo MCP Server exposing git operation tools."""

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "push_code",
                "description": "Push code to remote git repository",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "remote": {"type": "string"},
                        "branch": {"type": "string"},
                        "force": {"type": "boolean"}
                    },
                    "required": ["remote", "branch"]
                }
            },
            {
                "name": "commit",
                "description": "Commit changes to git history",
                "inputSchema": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"]
                }
            }
        ]

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "push_code":
            remote = arguments.get("remote", "origin")
            branch = arguments.get("branch", "main")
            force = arguments.get("force", False)
            force_str = " (forced)" if force else ""
            return {"content": [{"type": "text", "text": f"Successfully pushed code to {remote}/{branch}{force_str}"}], "isError": False}
        elif name == "commit":
            message = arguments.get("message", "")
            return {"content": [{"type": "text", "text": f"Committed changes with message: '{message}'"}], "isError": False}
        else:
            return {"content": [{"type": "text", "text": f"Unknown git tool: {name}"}], "isError": True}
