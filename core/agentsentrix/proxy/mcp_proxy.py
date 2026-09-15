import os
import sys
import uuid
import json
import logging
import asyncio
from typing import Any, Optional

from ..schema.enums import Sensor, ActionType, NodeKind, Verdict
from ..schema.events import AgentEvent, AgentRef, Target, RiskAssessment, BlastRadius
from ..bus.bus import EventBus
from ..engine.evaluator import MultiTierEvaluator
from .quarantine import QuarantineManager
from ..mcp.servers.filesystem_server import FilesystemMCPServer
from ..mcp.servers.terminal_server import TerminalMCPServer
from ..mcp.servers.git_server import GitMCPServer

logger = logging.getLogger("agentsentrix.proxy.mcp_proxy")

class MCPProxy:
    """
    Transparent inline MCP Proxy server.
    Supports both programmatic Python invocation (call_tool) and newline-delimited JSON-RPC 2.0 stdio protocol (handle_jsonrpc_request / run_stdio_loop).
    Intercepts MCP tool calls, converts them into AgentEvents, evaluates risk & blast radius via MultiTierEvaluator,
    and dispatches telemetry onto the EventBus before forwarding, blocking, or quarantining.
    """

    def __init__(
        self,
        bus: EventBus,
        evaluator: MultiTierEvaluator,
        quarantine_mgr: QuarantineManager,
        filesystem_server: Optional[FilesystemMCPServer] = None,
        terminal_server: Optional[TerminalMCPServer] = None,
        git_server: Optional[GitMCPServer] = None
    ) -> None:
        self.bus = bus
        self.evaluator = evaluator
        self.quarantine_mgr = quarantine_mgr

        # Sync QuarantineManager with Evaluator cache if available
        if hasattr(self.evaluator, "cache") and self.evaluator.cache and not self.quarantine_mgr.cache:
            self.quarantine_mgr.cache = self.evaluator.cache

        self.fs_server = filesystem_server or FilesystemMCPServer()
        self.term_server = terminal_server or TerminalMCPServer()
        self.git_server = git_server or GitMCPServer()

    def list_tools(self) -> list[dict[str, Any]]:
        """Aggregate and list all tools available from backend target MCP servers."""
        tools = []
        tools.extend(self.fs_server.list_tools())
        tools.extend(self.term_server.list_tools())
        tools.extend(self.git_server.list_tools())
        return tools

    def _find_target_server(self, tool_name: str) -> Optional[Any]:
        fs_tool_names = {t["name"] for t in self.fs_server.list_tools()}
        if tool_name in fs_tool_names:
            return self.fs_server

        term_tool_names = {t["name"] for t in self.term_server.list_tools()}
        if tool_name in term_tool_names:
            return self.term_server

        git_tool_names = {t["name"] for t in self.git_server.list_tools()}
        if tool_name in git_tool_names:
            return self.git_server

        return None

    def _map_to_event(self, tool_name: str, arguments: dict[str, Any], session_id: str, agent_id: str) -> AgentEvent:
        """Map incoming MCP tool call into a structured AgentEvent."""
        if tool_name in ("read_file", "write_file", "list_directory"):
            path = arguments.get("path", "")
            action_type = ActionType.FILE_READ if tool_name in ("read_file", "list_directory") else ActionType.FILE_WRITE
            target = Target(kind=NodeKind.FILE, label=os.path.basename(path) or path, path=path)
            raw_payload = f"cat {path}" if tool_name == "read_file" else f"write {path}"

        elif tool_name == "run_command":
            cmd = arguments.get("command", "")
            action_type = ActionType.SHELL_EXEC
            target = Target(kind=NodeKind.SHELL, label=cmd[:30], path=cmd)
            raw_payload = cmd

        elif tool_name == "push_code":
            action_type = ActionType.GIT_OP
            remote = arguments.get("remote", "origin")
            branch = arguments.get("branch", "main")
            force_flag = "--force" if arguments.get("force") else ""
            target = Target(kind=NodeKind.REMOTE, label="git_push", host=remote)
            raw_payload = f"git push {remote} {branch} {force_flag}".strip()

        elif tool_name == "commit":
            action_type = ActionType.GIT_OP
            msg = arguments.get("message", "")
            target = Target(kind=NodeKind.AGENT, label="git_commit")
            raw_payload = f"git commit -m '{msg}'"

        else:
            action_type = ActionType.TOOL_CALL
            target = Target(kind=NodeKind.AGENT, label=tool_name)
            raw_payload = f"{tool_name}({arguments})"

        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        return AgentEvent(
            id=event_id,
            session_id=session_id,
            sensor=Sensor.MCP_PROXY,
            agent=AgentRef(id=agent_id, name="MCP Agent"),
            action_type=action_type,
            target=target,
            raw_payload=raw_payload,
            risk=RiskAssessment(score=0, verdict=Verdict.PENDING)
        )

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str = "default_session",
        agent_id: str = "agent_01"
    ) -> dict[str, Any]:
        """
        Intercepts tool call, performs risk assessment, dispatches to bus, and enforces verdict.
        """
        target_server = self._find_target_server(tool_name)
        if not target_server:
            return {"content": [{"type": "text", "text": f"Tool '{tool_name}' not found on any mounted MCP server."}], "isError": True}

        # 1. Map invocation to AgentEvent
        event = self._map_to_event(tool_name, arguments, session_id, agent_id)

        # 2. Evaluate risk & blast radius
        risk, blast = await self.evaluator.assess(event)
        event.risk = risk
        event.blast_radius = blast

        # 3. Publish event to EventBus
        await self.bus.publish(event)

        # 4. Enforce verdict
        if risk.verdict == Verdict.ALLOWED:
            logger.info(f"FORWARDING tool call '{tool_name}' (Score: {risk.score})")
            return await target_server.execute_tool(tool_name, arguments)

        elif risk.verdict == Verdict.BLOCKED:
            logger.warning(f"BLOCKING tool call '{tool_name}' (Score: {risk.score}) - {risk.rationale}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Policy Denial (Score {risk.score}/100): {risk.rationale or 'Blocked by AgentSentrix security policy.'}"
                    }
                ],
                "isError": True
            }

        elif risk.verdict == Verdict.QUARANTINED:
            logger.info(f"QUARANTINING tool call '{tool_name}' (Score: {risk.score}) - awaiting human approval")

            # Freeze execution on QuarantineManager future & sync state with Redis
            event_data = {
                "event_id": event.id,
                "tool_name": tool_name,
                "arguments": arguments,
                "risk_score": risk.score,
                "rationale": risk.rationale
            }
            future = self.quarantine_mgr.create_quarantine_future(event.id, event_data=event_data)
            resolution = await future

            resolved_verdict = resolution.get("verdict", Verdict.BLOCKED)
            note = resolution.get("note", "")

            if resolved_verdict == Verdict.ALLOWED:
                logger.info(f"QUARANTINE PASSED for '{tool_name}' (Event {event.id}). Forwarding to target server.")
                return await target_server.execute_tool(tool_name, arguments)
            else:
                logger.warning(f"QUARANTINE REJECTED for '{tool_name}' (Event {event.id}).")
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Quarantine Rejection: Action was denied by human operator. Note: {note}"
                        }
                    ],
                    "isError": True
                }

        else:
            return await target_server.execute_tool(tool_name, arguments)

    # ------------------------------------------------------------------
    # JSON-RPC 2.0 Transport Interface (Stdio / Wire Framing)
    # ------------------------------------------------------------------

    async def handle_jsonrpc_request(self, request_str: str) -> str:
        """
        Parse and process a newline-delimited JSON-RPC 2.0 request string.
        Supports standard MCP protocol methods 'tools/list' and 'tools/call'.
        """
        try:
            payload = json.loads(request_str)
        except Exception:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error: Invalid JSON payload."}
            })

        if not isinstance(payload, dict):
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: Payload must be a JSON object."}
            })

        req_id = payload.get("id")
        method = payload.get("method", "")
        params = payload.get("params", {}) or {}

        if method == "tools/list":
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.list_tools()}
            })

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {}) or {}
            session_id = params.get("session_id", "default_session")
            agent_id = params.get("agent_id", "agent_01")

            tool_result = await self.call_tool(tool_name, arguments, session_id=session_id, agent_id=agent_id)
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": tool_result
            })

        else:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method '{method}' not found."}
            })

    async def run_stdio_loop(self) -> None:
        """
        Asynchronously read JSON-RPC requests from standard input (sys.stdin)
        and write JSON-RPC responses to standard output (sys.stdout).
        """
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            line_bytes = await reader.readline()
            if not line_bytes:
                break
            line_str = line_bytes.decode("utf-8").strip()
            if not line_str:
                continue

            response_json = await self.handle_jsonrpc_request(line_str)
            sys.stdout.write(response_json + "\n")
            sys.stdout.flush()
