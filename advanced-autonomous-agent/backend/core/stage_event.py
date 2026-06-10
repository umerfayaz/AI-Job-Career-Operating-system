from datetime import datetime
from backend.core.event_bus import get_event_bus



class EmitStage:
    def __init__(self):
        self.event_bus = get_event_bus()

    async def emit_staging_start(self, run_id: str, stage: str, message: str, agent: str = "agent"):
        await self.event_bus.emit({
            "type": "thinking_agent",
            "run_id": run_id,
            "agent": agent,
            "stage": stage,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })

    
    async def emit_staging_done(self, run_id: str, stage: str, agent: str = "agent"):
        await self.event_bus.emit({
            "type": "thinking_done",
            "run_id": run_id,
            "stage": stage,
            "agent": agent,
            "timestamp": datetime.now().isoformat()
        })
