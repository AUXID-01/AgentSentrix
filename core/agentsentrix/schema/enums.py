# schema/enums.py
from enum import Enum

class SchemaVersion(str, Enum):
    V1 = "1.0"

class Sensor(str, Enum):
    MCP_PROXY = "mcp_proxy"
    SHELL_SHIM = "shell_shim"
    SDK_MIDDLEWARE = "sdk_middleware"
    REPLAY = "replay"

class ActionType(str, Enum):
    TOOL_CALL = "tool_call"
    SHELL_EXEC = "shell_exec"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    NET_EGRESS = "net_egress"
    PACKAGE_INSTALL = "package_install"
    GIT_OP = "git_op"
    MCP_HANDSHAKE = "mcp_handshake"

class NodeKind(str, Enum):
    AGENT = "agent"
    FILE = "file"
    SHELL = "shell"
    REMOTE = "remote"
    MCP_SERVER = "mcp_server"
    SECRET = "secret"

class Verdict(str, Enum):
    ALLOWED = "allowed"
    QUARANTINED = "quarantined"   # blocking, awaiting human
    BLOCKED = "blocked"
    PENDING = "pending"           # in flight