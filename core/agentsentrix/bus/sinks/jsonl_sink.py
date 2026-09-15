import os
from typing import Optional
from ...schema.events import AgentEvent

class JSONLSink:
    """JSONL append-only file sink that records event streams for replays."""

    def __init__(self, target_dir: str = "data/sessions", file_path: Optional[str] = None) -> None:
        self.target_dir = target_dir
        self.file_path = file_path
        if file_path:
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        else:
            os.makedirs(os.path.abspath(target_dir), exist_ok=True)

    def _get_target_file(self, event: AgentEvent) -> str:
        if self.file_path:
            return self.file_path
        session_id = event.session_id or "default"
        return os.path.join(self.target_dir, f"{session_id}.jsonl")

    async def consume(self, event: AgentEvent) -> None:
        """Serialize event to JSON and append to JSONL file."""
        target_file = self._get_target_file(event)
        os.makedirs(os.path.dirname(os.path.abspath(target_file)), exist_ok=True)
        line = event.model_dump_json() + "\n"
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
