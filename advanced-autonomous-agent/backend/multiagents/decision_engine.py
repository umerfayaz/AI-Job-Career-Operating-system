"""Decision Engine decides which agent to trigger based on events"""

import structlog
from typing import List, Dict
from enum import Enum

logger = structlog.get_logger()


class EventType(Enum):
    NEW_RESUME = "new_resume"
    NEW_JOBS = "new_jobs"
    NEW_MATCHES = "new_matches"
    SCHEDULED = "scheduled"
    USER_ACTION = "user_action"
    SYSTEM_MAINTENANCE = "system_maintenance" 
    AUTONOMOUS_GOAL = "autonomous_goal" 


class DecisionEngine:
    """Central Brain: Decides which agent to activate"""

    def __init__(self):
        # Define rules for agents
        self.rules = {
            EventType.NEW_RESUME: [
                "JobScraperAgent",
                "ResumeMatcherAgent",
                "ReportGeneratorAgent",
            ],
            EventType.NEW_JOBS: [
                "ResumeMatcherAgent",
                "ReportGeneratorAgent",
            ],
            EventType.NEW_MATCHES: [
                "ReportGeneratorAgent",
                "NotificationAgent",
            ],
            EventType.SCHEDULED: [
                "JobScraperAgent",
                "MemoryMaintenanceAgent",
            ],
            EventType.SYSTEM_MAINTENANCE: [  
                "MemoryMaintenanceAgent"
            ],
        }

    def decide(self, event: Dict) -> List[str]:
        """Given an event, decide which agents to activate"""

        event_type = EventType(event.get("type"))

        # Get agents for this event type
        agents_to_activate = self.rules.get(event_type, [])

        # Event-specific handling
        if event_type == EventType.NEW_RESUME:
            logger.info(
                f"New Resume Detected — Activating: {agents_to_activate}"
            )

        elif event_type == EventType.SCHEDULED:
            from datetime import datetime

            hour = datetime.now().hour

            # Scrape during low-traffic hours
            if 2 <= hour <= 6:
                agents_to_activate = [
                    "JobScraperAgent",
                    "MemoryMaintenanceAgent",
                ]
            else:
                agents_to_activate = [
                    "ResumeMatcherAgent",
                    "ReportGeneratorAgent",
                ]

        logger.info(
            f"Decision Activated: {agents_to_activate} | Event: {event_type.value}"
        )
        return agents_to_activate

        



