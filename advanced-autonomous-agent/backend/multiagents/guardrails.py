from datetime import datetime, timedelta
import structlog
import asyncio

logger = structlog.get_logger()


class JobReportGuardrails:
    "Guardrails for job fetching and report generating"


    # Configurable Limits
    MAX_API_CALLS_PER_HOUR = 100
    MAX_JOBS_PER_HOUR = 100
    MAX_REPORTS_PER_HOUR = 50
    MAX_KEYWORDS = 10
    MAX_REPORT_SIZE_MB =500 
    MAX_CONCURRENT_TASKS =5
    MAX_ACTION_DURATION = 600

    def __init__(self):
        self.api_call_count=0
        self.jobs_fetched = 0
        self.reports_generated = 0
        self.current_tasks =0
        self.last_reset = datetime.now()
        self.action_history = []

    async def check_can_proceed(self, action: str, context: dict) ->tuple[bool,str]:
        """Check if the action is allowed under Guardrails"""

        if datetime.now() - self.last_reset > timedelta(hours=1):
            self.api_call_count = 0
            self.jobs_fetched =0
            self.reports_generated = 0
            self.current_tasks = 0
            self.last_reset =  datetime.now()


        ## Rate Limit
        if self.api_call_count >= self.MAX_API_CALLS_PER_HOUR:
            return False, "Rate Limit Exceed"
        
        if self.current_tasks >= self.MAX_CONCURRENT_TASKS:
            return False, "Rate Limit Exceed"

        # JOb fetching COnstraints
        if action == "fetched_jobs":
            if context.get("keywords_count", 0) > self.MAX_KEYWORDS:
                return False, "To many keywords to fetch"
            
            if self.jobs_fetched >= self.MAX_JOBS_PER_HOUR:
                return False, "Exceed max jobs fetched per hour"
            return True, "OK"
            
        # Report Generation Constrints
        if action == "report_generation":
            if self.reports_generated >= self.MAX_REPORTS_PER_HOUR:
                return False, "Reports limits exceeed"
            
            if context.get("report_size_mb") >= self.MAX_REPORT_SIZE_MB:
                return False , "Max Report size Too large"
            
            return True, "OK"
        return  True,"OK"
    
    async def record_action(self, action:str):
        """Record a complete action"""

        self.api_call_count +=1
        if action == "fetched_jobs":
            self.jobs_fetched +=1
        
        if action == "generate_report":
            self.reports_generated +=1
        
        self.action_history.append({
            "action": action,
            "timestamp": datetime.now().isoformat()
        })

    async def acquire_task_slot(self) -> bool:
        if self.current_tasks >= self.MAX_CONCURRENT_TASKS:
            return False
        
        self.current_tasks +=1
        return True
    
    async def release_task(self):
        """Release the task slot"""
        if self.current_tasks > 0:
            self.current_tasks -=1

    






