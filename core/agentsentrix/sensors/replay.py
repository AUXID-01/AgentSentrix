import asyncio
import os
import logging
from typing import Optional
from .base import Sensor
from ..schema.events import AgentEvent
from ..bus.bus import EventBus

logger = logging.getLogger("agentsentrix.sensors.replay")

class ReplaySensor(Sensor):
    """
    Sensor that replays historical session events from a .jsonl log file
    onto the EventBus matching original relative timestamp offsets.
    """

    def __init__(
        self,
        jsonl_path: str,
        bus: Optional[EventBus] = None,
        speed_factor: float = 1.0
    ) -> None:
        super().__init__(bus=bus)
        self.jsonl_path = jsonl_path
        self.speed_factor = max(speed_factor, 0.001)
        self._running = False
        self._replay_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start async replay loop."""
        if not os.path.exists(self.jsonl_path):
            logger.warning(f"Replay file missing: {self.jsonl_path}")
            return
        self._running = True
        self._replay_task = asyncio.create_task(self._run_replay())

    async def stop(self) -> None:
        """Stop replay loop."""
        self._running = False
        if self._replay_task and not self._replay_task.done():
            self._replay_task.cancel()
            try:
                await self._replay_task
            except asyncio.CancelledError:
                pass

    async def _run_replay(self) -> None:
        try:
            with open(self.jsonl_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]

            prev_ts: Optional[float] = None
            for line in lines:
                if not self._running:
                    break

                try:
                    event = AgentEvent.model_validate_json(line)
                    current_ts = event.ts.timestamp()

                    if prev_ts is not None and current_ts > prev_ts:
                        delay = (current_ts - prev_ts) / self.speed_factor
                        if delay > 0:
                            await asyncio.sleep(min(delay, 5.0)) # clamp delay to max 5s

                    prev_ts = current_ts
                    await self.emit_event(event)
                except Exception as exc:
                    logger.warning(f"Error parsing replay line: {exc}")

            logger.info(f"Replay completed for {self.jsonl_path}")
        except Exception as exc:
            logger.error(f"Failed to execute replay from {self.jsonl_path}: {exc}", exc_info=True)
        finally:
            self._running = False
