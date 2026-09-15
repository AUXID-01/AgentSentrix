import functools
import logging
import uuid
import warnings
from typing import Callable, Any, Optional

import httpx

from .schema.enums import Verdict, ActionType, Sensor, NodeKind
from .schema.events import AgentEvent, AgentRef, Target, RiskAssessment

logger = logging.getLogger("agentsentrix.sdk")

class SecurityBlockError(Exception):
    """Raised when an action is BLOCKED by AgentSentrix policy."""
    pass

class QuarantineTimeoutError(Exception):
    """Raised when a QUARANTINED action times out waiting for human approval."""
    pass

class AgentSentrixSDK:
    """
    Developer Python SDK for AgentSentrix security interception.
    - Zero-config local connection to AgentSentrix security gateway (http://localhost:8000).
    - Decorator `@sentrix.intercept_tool()` wraps any agent tool/function.
    - Suspends execution during QUARANTINE awaiting human dashboard decision.
    - Fail-safe resilience: if server is down and `fail_safe=True`, logs warning and proceeds cleanly.
    """

    def __init__(
        self,
        server_url: str = "http://localhost:8000",
        agent_id: str = "default-agent",
        agent_name: str = "Developer Agent",
        fail_safe: bool = True,
        timeout: float = 5.0
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.fail_safe = fail_safe
        self.timeout = timeout

    def intercept_tool(
        self,
        agent_id: Optional[str] = None,
        action_type: str = "tool_call",
        target_kind: str = "shell"
    ) -> Callable:
        """
        Decorator for wrapping agent tools/functions with AgentSentrix security evaluation.
        Supports both async and synchronous functions.
        """
        def decorator(func: Callable) -> Callable:
            if functools.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs) -> Any:
                    target_str = str(kwargs) if kwargs else (str(args[0]) if args else func.__name__)
                    payload_str = f"{func.__name__}(args={args}, kwargs={kwargs})"
                    active_agent_id = agent_id or self.agent_id

                    verdict = await self._evaluate_async(
                        agent_id=active_agent_id,
                        action_type=action_type,
                        target_kind=target_kind,
                        target_label=target_str[:128],
                        raw_payload=payload_str
                    )

                    if verdict == Verdict.BLOCKED:
                        raise SecurityBlockError(f"Action '{func.__name__}' BLOCKED by AgentSentrix security policy.")
                    
                    return await func(*args, **kwargs)
                return async_wrapper
            else:
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs) -> Any:
                    target_str = str(kwargs) if kwargs else (str(args[0]) if args else func.__name__)
                    payload_str = f"{func.__name__}(args={args}, kwargs={kwargs})"
                    active_agent_id = agent_id or self.agent_id

                    verdict = self._evaluate_sync(
                        agent_id=active_agent_id,
                        action_type=action_type,
                        target_kind=target_kind,
                        target_label=target_str[:128],
                        raw_payload=payload_str
                    )

                    if verdict == Verdict.BLOCKED:
                        raise SecurityBlockError(f"Action '{func.__name__}' BLOCKED by AgentSentrix security policy.")

                    return func(*args, **kwargs)
                return sync_wrapper
        return decorator

    async def _evaluate_async(
        self,
        agent_id: str,
        action_type: str,
        target_kind: str,
        target_label: str,
        raw_payload: str
    ) -> Verdict:
        """Send event payload to AgentSentrix server asynchronously."""
        evt_id = f"evt_{uuid.uuid4().hex[:12]}"
        
        # Map string enum values
        try:
            act_enum = ActionType(action_type)
        except ValueError:
            act_enum = ActionType.TOOL_CALL

        try:
            kind_enum = NodeKind(target_kind)
        except ValueError:
            kind_enum = NodeKind.SHELL

        event_payload = {
            "schema_version": "1.0",
            "id": evt_id,
            "session_id": "sdk_session",
            "sensor": Sensor.SDK_MIDDLEWARE.value,
            "agent": {
                "id": agent_id,
                "name": self.agent_name,
                "framework": "python_sdk"
            },
            "action_type": act_enum.value,
            "target": {
                "kind": kind_enum.value,
                "label": target_label,
                "path": target_label if "/" in target_label or "\\" in target_label else None
            },
            "raw_payload": raw_payload,
            "risk": {
                "score": 0,
                "verdict": Verdict.PENDING.value
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.server_url}/events/ingest", json=event_payload)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    if status == "ingested":
                        return Verdict.ALLOWED
        except Exception as exc:
            if self.fail_safe:
                warnings.warn(
                    f"AgentSentrix server ({self.server_url}) unreachable: {exc}. Fail-safe mode allowing action.",
                    UserWarning
                )
                return Verdict.ALLOWED
            raise exc

        return Verdict.ALLOWED

    def _evaluate_sync(
        self,
        agent_id: str,
        action_type: str,
        target_kind: str,
        target_label: str,
        raw_payload: str
    ) -> Verdict:
        """Send event payload to AgentSentrix server synchronously."""
        evt_id = f"evt_{uuid.uuid4().hex[:12]}"
        
        try:
            act_enum = ActionType(action_type)
        except ValueError:
            act_enum = ActionType.TOOL_CALL

        try:
            kind_enum = NodeKind(target_kind)
        except ValueError:
            kind_enum = NodeKind.SHELL

        event_payload = {
            "schema_version": "1.0",
            "id": evt_id,
            "session_id": "sdk_session",
            "sensor": Sensor.SDK_MIDDLEWARE.value,
            "agent": {
                "id": agent_id,
                "name": self.agent_name,
                "framework": "python_sdk"
            },
            "action_type": act_enum.value,
            "target": {
                "kind": kind_enum.value,
                "label": target_label,
                "path": target_label if "/" in target_label or "\\" in target_label else None
            },
            "raw_payload": raw_payload,
            "risk": {
                "score": 0,
                "verdict": Verdict.PENDING.value
            }
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.server_url}/events/ingest", json=event_payload)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status")
                    if status == "ingested":
                        return Verdict.ALLOWED
        except Exception as exc:
            if self.fail_safe:
                warnings.warn(
                    f"AgentSentrix server ({self.server_url}) unreachable: {exc}. Fail-safe mode allowing action.",
                    UserWarning
                )
                return Verdict.ALLOWED
            raise exc

        return Verdict.ALLOWED
