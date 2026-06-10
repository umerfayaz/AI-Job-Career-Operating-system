from backend.core.event_bus import get_event_bus
from backend.narration.narrator import NarrationEngine
import structlog

logger = structlog.get_logger()

class AgentEmitter:
    def __init__(self, agent_name, event_bus):
        self.agent_name = agent_name
        self.event_bus = event_bus or get_event_bus()
        self.narrator = NarrationEngine() 

        logger.info(f"🎯 AgentEmitter created for {agent_name}")
        logger.debug(f"EventBus object: {id(self.event_bus)}, connections: {len(self.event_bus.connections)}")

    async def _emit_with_narration(self, event):
        """Emit event immediately, narrate in parallel"""
        event["agent_name"] = (
            event.get("agent_name") or
            self.agent_name or
            "SYSTEM"
        )
     
        await self.event_bus.emit(event)
        logger.debug(f"📤 Emitted event: {event.get('stage')} from {self.agent_name}")
        await self.narrator.narrate(event)

    async def start(self, run_id, message):
        await self._emit_with_narration({
            "run_id": run_id,
            "agent_name": self.agent_name,
            "level": "info",
            "stage": "started",
            "message": message
        })

    async def progress(self, run_id, message, meta=None):
        await self._emit_with_narration({
            "run_id": run_id,
            "agent_name": self.agent_name,
            "level": "info",
            "stage": "progress",
            "message": message,
            "meta": meta or {}
        })

    async def done(self, run_id, message, meta=None):
        await self._emit_with_narration({
            "run_id": run_id,
            "agent_name": self.agent_name,
            "level": "success",
            "stage": "completed",
            "message": message,
            "meta": meta or {}
        })

    async def error(self, run_id, message):
        await self._emit_with_narration({
            "run_id": run_id,
            "agent_name": self.agent_name,
            "level": "error",
            "stage": "failed",
            "message": message
        })
    
