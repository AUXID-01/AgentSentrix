import os
from typing import Any

class FilesystemMCPServer:
    """Mock Filesystem MCP Server exposing filesystem tools."""

    def __init__(self, root_dir: str = ".") -> None:
        self.root_dir = os.path.abspath(root_dir)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "read_file",
                "description": "Read contents of a file",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]
                }
            },
            {
                "name": "write_file",
                "description": "Write content to a file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["path", "content"]
                }
            },
            {
                "name": "list_directory",
                "description": "List files in a directory",
                "inputSchema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]
                }
            }
        ]

    async def execute_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "read_file":
            path = arguments.get("path", "")
            return {"content": [{"type": "text", "text": f"Mock file content of '{path}'"}], "isError": False}
        elif name == "write_file":
            path = arguments.get("path", "")
            content = arguments.get("content", "")
            return {"content": [{"type": "text", "text": f"Successfully wrote {len(content)} bytes to '{path}'"}], "isError": False}
        elif name == "list_directory":
            path = arguments.get("path", ".")
            return {"content": [{"type": "text", "text": f"['file1.txt', 'file2.py', 'dir1'] in '{path}'"}], "isError": False}
        else:
            return {"content": [{"type": "text", "text": f"Unknown filesystem tool: {name}"}], "isError": True}
