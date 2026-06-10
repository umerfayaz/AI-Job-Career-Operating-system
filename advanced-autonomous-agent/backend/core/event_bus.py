import asyncio
from datetime import datetime
from typing import Dict, Set, List, Any, Optional
import structlog

logger = structlog.get_logger()

class EventBus:
    def __init__(self):
        self.connections: Set[asyncio.Queue] = set()
        self.history: List[Dict[str, Any]] = []  
        self.subscribers: Dict[str, List[Any]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self):
        """Register a new listener queue"""
        queue = asyncio.Queue(maxsize=1000) 
        async with self._lock:
            self.connections.add(queue)
        return queue

    async def disconnect(self, queue):  
        """Unregister a listener queue"""
        async with self._lock:
            self.connections.discard(queue)
    
    def subscribers_topic(self, event_type: str, handler):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.info(f"Subscribed handler to {event_type}")


    async def subscribe(self):
        queue =  await self.connect()
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            await self.disconnect(queue)

    
    async def emit(self, event: Dict):
        """Broadcast event to all connected listeners"""
        logger.info(f"📡 Emitting event: {event.get('type')} - {event.get('source')}")

        event_type = event.get('type')

        handlers = self.subscribers.get(event_type, [])
        for handler in handlers:
            try:
                asyncio.create_task(handler(event))
            except Exception as e:
                logger.error(f"Handler failed {e}")

        
        if not self.connections:
            logger.warning(f"❌ No connections to emit to!")
            return
        
        if "timestamp" not in event:
            event["timestamp"] = datetime.now().isoformat()
        self.history.append(event)
        
        if len(self.history) > 2000:
            self.history = self.history[-1000:]
        
        async with self._lock:
            connections_copy = list(self.connections)
        
        logger.info(f"📡 Broadcasting to {len(connections_copy)} connections")
        
        for queue in connections_copy:
            try:  
                queue.put_nowait(event)
                logger.debug(f"✅ Event queued successfully")
            except asyncio.QueueFull:
                logger.warning(f"⚠️ Queue full, dropping oldest")
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except:
                    pass
            except Exception as e:
                logger.error(f"❌ Failed to emit: {e}")
                async with self._lock:
                    self.connections.discard(queue)

    async def emit_error(self,
        source: str,
        issue: str,
        error: Exception, 
        severity: str = "warning", 
        payload: Optional[Dict[str, Any]] =None,
        ):

        await self.emit({
            "type": "SYSTEM_ERROR",
            "source": source,
            "issue": issue,
            "level": severity,
            "message": str(error),
            "payload": payload or {}
        })
    
    async def get_recent(self, event_type: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Reading last events from History"""
        events = [e for e in self.history if e.get("type") == event_type]
        return events[-limit:]

_instance =None
def get_event_bus() -> EventBus:
    global _instance
    if _instance is None:
        
      _instance = EventBus()
      logger.info(f" Singleton instance is created")
    
    return _instance
    



