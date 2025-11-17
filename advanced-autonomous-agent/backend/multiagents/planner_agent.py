
""" Planner-Agent - Orchestrates the workflow based on triggers """

from sqlite3.dbapi2 import Timestamp
from typing import List, Dict, Any
from enum import Enum



class Tasktype(Enum):
    RESUME_UPLOAD = "resume_upload"
    SCHEDULED_RUN = "schedule_run"
    MANUAL_TRIGGER = "manual_trigger"
    QUALITY_CHECK_FAILED ="quality_check_failed"


class PlannerAgent:
    def __init__(self):
        self.task_queue = []
    
    def analyze_trigger(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine Whats need to happen 
        """

        trigger_type = event.get("type")

        if trigger_type == "resume_upload":
            return {
                "tasks": [
                    {"agent": "scraper", "action": "fetch_jobs", "priority": 1},
                    {"agent": "retriver", "action": "match_resume", "priority": 2},
                    {"agent": "writer", "action": "generate_report", "priority":3},
                    {"agent": "reflector", "action": "quality_check", "priority":4},
                    {"agent": "email", "action": "send_report", "priority": 5},
                ],
                "context": {
                    "resume_id": event.get("resume_id"),
                    "user_id": event.get("user_id"),
                    "fresh_data_required": True
                }
            }

        elif trigger_type == "quality_check_failed":
            return {
                "tasks": [
                    {"agent": "retriver", "action": "rematch_with_filter", "priority": 1},
                    {"agent": "writer", "action": "regenerate_report", "priority":2},
                    {"agent": "reflector", "action": "check_quality", "priority":3},
                ],
                "context": {
                    "retry_count": event.get("retry_count", 0) +1,
                    "feedback": event.get("feedback")
                }
            }

        return {"tasks": [], "context": {}}

    def create_execution_plan(self, trigger_event: Dict[str, Any]) ->Dict[str, Any]:
        """Create Detailed Execution plan for the workflow"""

        plan = self.analyze_trigger(trigger_event)

        return {
            "plan_id": f"plan_{trigger_event.get('timestamp', 'unknown')}",
            "tasks": plan["tasks"],
            "context": plan["context"],
            "status": "pending",
            "created_at":  trigger_event.get("timestamp")

        }
    

