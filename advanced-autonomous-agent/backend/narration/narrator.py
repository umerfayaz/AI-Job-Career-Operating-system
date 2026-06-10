import json
from datetime import datetime
from .prompt import NARRATOR_PROMPT
import structlog
from langchain_groq import ChatGroq
from backend.core.event_bus import get_event_bus

logger = structlog.get_logger()

class NarrationEngine:
    def __init__(self):
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            temperature=0.4,
            max_tokens=100,
            timeout=2.0,
            streaming =False,
            request_timeout=2.0
        )

        self.event_bus = get_event_bus()   

    async def narrate(self, event: dict) -> dict:
        """Converting structured agent event into human readable output"""
        
        try:
            agent_name = event.get("agent_name") or event.get("source")
            stage = event.get("stage", "processing")
            message = event.get("message", "")
            meta = event.get("meta", {})


            logger.info(f"🎙️ Narrating: {agent_name}, {stage}, {message[:50]}...")

            # Create contextual prompt based on stage
            context = f"""EVENT TO NARRATE:
Agent: {agent_name}
Stage: {stage}
Message: {message}
Additional Info: {json.dumps(meta)}

Convert this into a friendly, conversational message for the user.
Keep it under 50 words and use emojis appropriately."""

            response = await self.llm.ainvoke([
                {"role": "system", "content": NARRATOR_PROMPT},
                {"role": "user", "content": context},
            ])

            full_text = response.content.strip()

            await self.event_bus.emit({
                "type": "narration_stream",
                "run_id": event["run_id"],
                "content":  full_text,
                "agent": agent_name,
                "stage": stage,
                "timestamp": datetime.now().isoformat()
            })
            
            await self.event_bus.emit({
                "type": "narration_done",
                "run_id": event["run_id"],
                "content": full_text,
                "agent": agent_name,
                "stage": stage
            })

        except Exception as e:
            logger.error(f"LLM Narrate Failed {e}")





