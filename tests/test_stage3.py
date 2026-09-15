import os
import json
import asyncio
import pytest
from unittest.mock import AsyncMock

from core.agentsentrix.schema.enums import Verdict, ActionType
from core.agentsentrix.schema.events import AgentEvent, RiskAssessment, BlastRadius
from core.agentsentrix.bus.bus import EventBus
from core.agentsentrix.bus.cache import StateCache
from core.agentsentrix.engine.evaluator import MultiTierEvaluator
from core.agentsentrix.proxy.quarantine import QuarantineManager
from core.agentsentrix.proxy.mcp_proxy import MCPProxy
from core.agentsentrix.mcp.servers.filesystem_server import FilesystemMCPServer
from core.agentsentrix.mcp.servers.terminal_server import TerminalMCPServer
from core.agentsentrix.mcp.servers.git_server import GitMCPServer

@pytest.fixture
def stage3_setup():
    bus = EventBus(maxlen=1000)
    cache = StateCache(host="localhost", port=6379)
    evaluator = MultiTierEvaluator(cache=cache)
    quarantine_mgr = QuarantineManager(cache=cache)

    fs_server = FilesystemMCPServer()
    term_server = TerminalMCPServer()
    git_server = GitMCPServer()

    proxy = MCPProxy(
        bus=bus,
        evaluator=evaluator,
        quarantine_mgr=quarantine_mgr,
        filesystem_server=fs_server,
        terminal_server=term_server,
        git_server=git_server
    )

    return {
        "bus": bus,
        "cache": cache,
        "evaluator": evaluator,
        "quarantine_mgr": quarantine_mgr,
        "proxy": proxy
    }

@pytest.mark.asyncio
async def test_mock_mcp_servers():
    fs_server = FilesystemMCPServer()
    term_server = TerminalMCPServer()
    git_server = GitMCPServer()

    # Verify tool listing
    fs_tools = fs_server.list_tools()
    term_tools = term_server.list_tools()
    git_tools = git_server.list_tools()

    assert len(fs_tools) == 3
    assert len(term_tools) == 1
    assert len(git_tools) == 2

    # Direct execution checks
    res_fs = await fs_server.execute_tool("read_file", {"path": "README.md"})
    assert res_fs["isError"] is False

    res_term = await term_server.execute_tool("run_command", {"command": "ls -l"})
    assert res_term["isError"] is False

    res_git = await git_server.execute_tool("commit", {"message": "initial commit"})
    assert res_git["isError"] is False

@pytest.mark.asyncio
async def test_proxy_allowed_flow(stage3_setup):
    proxy: MCPProxy = stage3_setup["proxy"]
    bus: EventBus = stage3_setup["bus"]

    events_captured = []

    async def event_listener(evt):
        events_captured.append(evt)

    bus.subscribe(event_listener)

    # Safe tool call
    res = await proxy.call_tool("read_file", {"path": "README.md"})
    assert res["isError"] is False
    assert "Mock file content of 'README.md'" in res["content"][0]["text"]

    # Verify event dispatched to bus
    assert len(events_captured) == 1
    captured_evt = events_captured[0]
    assert captured_evt.risk.verdict == Verdict.ALLOWED
    assert captured_evt.action_type == ActionType.FILE_READ

@pytest.mark.asyncio
async def test_proxy_blocked_flow(stage3_setup):
    proxy: MCPProxy = stage3_setup["proxy"]
    bus: EventBus = stage3_setup["bus"]

    events_captured = []

    async def event_listener(evt):
        events_captured.append(evt)

    bus.subscribe(event_listener)

    # Dangerous command call
    res = await proxy.call_tool("run_command", {"command": "rm -rf /"})
    assert res["isError"] is True
    assert "Policy Denial" in res["content"][0]["text"]

    # Verify event dispatched to bus
    assert len(events_captured) == 1
    captured_evt = events_captured[0]
    assert captured_evt.risk.verdict == Verdict.BLOCKED
    assert captured_evt.risk.score == 100

@pytest.mark.asyncio
async def test_proxy_quarantine_resolution_allowed(stage3_setup):
    proxy: MCPProxy = stage3_setup["proxy"]
    bus: EventBus = stage3_setup["bus"]
    evaluator: MultiTierEvaluator = stage3_setup["evaluator"]
    quarantine_mgr: QuarantineManager = stage3_setup["quarantine_mgr"]

    # Mock evaluator to return QUARANTINED verdict
    quarantine_assessment = RiskAssessment(
        score=60,
        verdict=Verdict.QUARANTINED,
        rationale="Ambiguous operation requiring human confirmation"
    )
    quarantine_blast = BlastRadius(score=30)
    evaluator.assess = AsyncMock(return_value=(quarantine_assessment, quarantine_blast))

    events_captured = []

    async def event_listener(evt):
        events_captured.append(evt)

    bus.subscribe(event_listener)

    # Task to trigger call_tool which will freeze on quarantine
    async def invoke_quarantined_tool():
        return await proxy.call_tool("push_code", {"remote": "origin", "branch": "main", "force": True})

    task = asyncio.create_task(invoke_quarantined_tool())
    await asyncio.sleep(0.1)

    assert len(events_captured) == 1
    event_id = events_captured[0].id
    assert event_id in quarantine_mgr.pending_futures

    # Resolve quarantine with ALLOWED
    resolved = quarantine_mgr.resolve_quarantine(event_id, Verdict.ALLOWED, note="Approved by security officer")
    assert resolved is True

    res = await task
    assert res["isError"] is False
    assert "Successfully pushed code" in res["content"][0]["text"]

@pytest.mark.asyncio
async def test_proxy_quarantine_resolution_rejected(stage3_setup):
    proxy: MCPProxy = stage3_setup["proxy"]
    bus: EventBus = stage3_setup["bus"]
    evaluator: MultiTierEvaluator = stage3_setup["evaluator"]
    quarantine_mgr: QuarantineManager = stage3_setup["quarantine_mgr"]

    # Mock evaluator to return QUARANTINED verdict
    quarantine_assessment = RiskAssessment(
        score=65,
        verdict=Verdict.QUARANTINED,
        rationale="Ambiguous git push operation requiring review"
    )
    quarantine_blast = BlastRadius(score=35)
    evaluator.assess = AsyncMock(return_value=(quarantine_assessment, quarantine_blast))

    events_captured = []

    async def event_listener(evt):
        events_captured.append(evt)

    bus.subscribe(event_listener)

    # Task to trigger call_tool which will freeze on quarantine
    async def invoke_quarantined_tool():
        return await proxy.call_tool("push_code", {"remote": "origin", "branch": "main", "force": True})

    task = asyncio.create_task(invoke_quarantined_tool())
    await asyncio.sleep(0.1)

    assert len(events_captured) == 1
    event_id = events_captured[0].id
    assert event_id in quarantine_mgr.pending_futures

    # Resolve quarantine with BLOCKED
    resolved = quarantine_mgr.resolve_quarantine(event_id, Verdict.BLOCKED, note="Denied due to force push restriction")
    assert resolved is True

    res = await task
    assert res["isError"] is True
    assert "Quarantine Rejection" in res["content"][0]["text"]

@pytest.mark.asyncio
async def test_jsonrpc_stdio_transport(stage3_setup):
    proxy: MCPProxy = stage3_setup["proxy"]

    # 1. Test tools/list JSON-RPC request
    req_list = json.dumps({"jsonrpc": "2.0", "id": 101, "method": "tools/list"})
    res_list_str = await proxy.handle_jsonrpc_request(req_list)
    res_list = json.loads(res_list_str)

    assert res_list["jsonrpc"] == "2.0"
    assert res_list["id"] == 101
    assert "tools" in res_list["result"]
    assert len(res_list["result"]["tools"]) == 6

    # 2. Test tools/call ALLOWED JSON-RPC request
    req_call_safe = json.dumps({
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tools/call",
        "params": {
            "name": "read_file",
            "arguments": {"path": "README.md"}
        }
    })
    res_safe_str = await proxy.handle_jsonrpc_request(req_call_safe)
    res_safe = json.loads(res_safe_str)

    assert res_safe["jsonrpc"] == "2.0"
    assert res_safe["id"] == 102
    assert res_safe["result"]["isError"] is False

    # 3. Test tools/call BLOCKED JSON-RPC request
    req_call_blocked = json.dumps({
        "jsonrpc": "2.0",
        "id": 103,
        "method": "tools/call",
        "params": {
            "name": "run_command",
            "arguments": {"command": "rm -rf /"}
        }
    })
    res_blocked_str = await proxy.handle_jsonrpc_request(req_call_blocked)
    res_blocked = json.loads(res_blocked_str)

    assert res_blocked["jsonrpc"] == "2.0"
    assert res_blocked["id"] == 103
    assert res_blocked["result"]["isError"] is True
    assert "Policy Denial" in res_blocked["result"]["content"][0]["text"]

    # 4. Test malformed JSON-RPC payload error handling
    res_err1_str = await proxy.handle_jsonrpc_request("invalid json payload")
    res_err1 = json.loads(res_err1_str)
    assert res_err1["error"]["code"] == -32700

    # 5. Test unknown method error handling
    req_unknown = json.dumps({"jsonrpc": "2.0", "id": 105, "method": "unknown/method"})
    res_err2_str = await proxy.handle_jsonrpc_request(req_unknown)
    res_err2 = json.loads(res_err2_str)
    assert res_err2["error"]["code"] == -32601

@pytest.mark.asyncio
async def test_quarantine_state_sync_with_redis(stage3_setup):
    quarantine_mgr: QuarantineManager = stage3_setup["quarantine_mgr"]
    cache: StateCache = stage3_setup["cache"]

    event_id = "evt_sync_test_999"
    event_data = {"tool_name": "push_code", "risk_score": 60}

    # 1. Create quarantine future & verify state is synced to Redis
    fut = quarantine_mgr.create_quarantine_future(event_id, event_data=event_data)
    assert event_id in quarantine_mgr.pending_futures

    cached_state = cache.get_quarantine(event_id)
    assert cached_state is not None
    assert cached_state["status"] == "quarantined"
    assert cached_state["tool_name"] == "push_code"
    assert cached_state["risk_score"] == 60

    # 2. Resolve quarantine & verify resolved state is synced to Redis
    resolved = quarantine_mgr.resolve_quarantine(event_id, Verdict.ALLOWED, note="Operator approved")
    assert resolved is True
    assert fut.done()

    cached_resolved = cache.get_quarantine(event_id)
    assert cached_resolved is not None
    assert cached_resolved["status"] == "resolved"
    assert cached_resolved["verdict"] == "allowed"
    assert cached_resolved["note"] == "Operator approved"
