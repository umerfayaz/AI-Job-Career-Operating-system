### Multi Agents With Episodic Memory

import os
import asyncio
import structlog
import numpy as np 
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dateutil import parser
from sentence_transformers import SentenceTransformer
import json

from ..core.memory_system import MemoryRAGSystem
from ..core.email_sender import EmailSender


def get_agent_app():
    from backend.application import AgentApplication
    return AgentApplication()

logger = structlog.get_logger()


class EpisodicMemory:
    def __init__(self, memory: MemoryRAGSystem):
        self.memory=memory
        self.experiences = []
        self.max_experiences =  1000


    def record_experiences(self, agent_name:str, action:str, result: Dict, context:Dict):
        """Record Agent Experience"""

        experience = {
            "agent": agent_name,
            "action": action,
            "result": result,
            "context": context,
            "timestamp": datetime.now().isoformat(),
            "success": result.get("status") == "success"
        }

        self.experiences.append(experience)


        if len(self.experiences) > self.max_experiences:
            self.experiences = self.experiences[-self.max_experiences:]
        
        logger.info(f"{agent_name} recorded experiences:{action}")
    

    def get_similar_experiences(self, agent_name:str, action:str, limit: int =5) ->List[Dict]:
        """Retrieve similar Past Experiences"""
        relevant =[
            exp for exp in self.experiences
            if exp["agent"] == agent_name and exp["action"] == action
        ]
        return relevant[-limit:]

    def get_success_rate(self, agent_name:str, action:str) ->float:
        """Calculate Success rate for an agent's action"""
        relevant = self.get_similar_experiences(self, agent_name, action, limit=20)
        if not relevant:
            return 0.5
        
        success = sum(1 for exp in relevant if exp["success"])
        return success / len(relevant)

    def learn_from_failures(self, agent_name:str) ->Dict:
        """Analyze failures and extract learnings"""
        failures =[
            exp for exp in self.experiences
            if exp["agent"] == agent_name and not exp["success"]
        ]

        if not failures:
            return {"learning": "No failures recorded"}
    
        ## Extract from failures
        common_errors = {}

        for failure in failures[-10:]:
            error = failure["result"].get("error", "unknown")
            common_errors[error] = common_errors.get(error, 0) + 1

        return {
            "total_failures": len(failures),
            "recent_failures": len(failures[-10:]),
            "common_errors": common_errors,
            "recommendations": self._generate_recommendations(common_errors)
        } 


    def _generate_recommendations(self, errors: Dict, ) ->List[str]:
        """Generate Reccomendations Based ont error Patterns"""

        recommendations = []

        for error, count in errors.items():
            if "timeout" in error.lower():
                recommendations.append("Consider increasing error limits")
            
            elif "not found" in error.lower():
                recommendations.append("Vlidate data experiences before processing")
            
            elif "empty" in error.lower():
                recommendations.append("Add data validation checks")
        
        return recommendations
    
class shared_context:
    """Shared memory speces for inter-agent Commounications"""

    def __init__(self):
        self.context = {
            "goals": [],
            "active_tasks": {},
            "completed_tasks": {},
            "agent_states": {},
            "global_metruics":{
                "jobs_scraped_today": 0,
                "matches_created_today": 0,
                "reports_generated_today": 0
            },
            "last_reset": datetime.now()
        }
        self.lock =asyncio.lock
    
    async def write(self, key: str, value: Any, agent_name:str):
        """write a shared context"""
        async with self.lock:
            self.context[key] == value
            logger.info(f"{agent_name} updated{key}")
    
    async def read(self, key:str) ->Any:
        """Read shared context"""
        async with self.lock:
            return self.context.get(key)

    async def update_metrics(self, metric:str, increment: int =1):
        """Update global metrics"""
        async with self.lock:
          if metric in self.context["global_metrics"]:
            self.context["global_metrics"][metric] += increment
    
    async def get_agent_state(self, agent_name:str) ->Dict:
        """Get Agent current state"""
        async with self.lock:
            return self.context["agent_states"].get(agent_name, {})
    
    async def add_task(self, task_id: str, task:Dict, agent_name:str):
        """Add a new task to the queue"""
        async with self.lock:
            self.context["active_tasks"][task_id] ={
                **task,
                "created_by": agent_name,
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }

            logger.info(f" {task_id} by {agent_name}")
    
    async def complete_task(self):
        """Reset daily metrics"""
        async with self.lock:
            now = datetime.now()
            last_reset=self.context["last_reset"]

            if isinstance(last_reset, str):
                last_reset = parser.parse(last_reset)
            
            ## Reset if its a new day
            if now.date() > last_reset.date():
                self.context["global_metrics"] ={
                    "jobs_scraped_today": 0,
                    "matches_jobs_today": 0,
                    "reports_generated_today": 0
                }
                self.context["last_reset"] = now
                logger.info("Daily metrics reset")
    


    












        



            










        





































        






    
