import structlog
import time
from backend.postgreSQL.database import PostgresDatabase
from backend.observability.tracer import tracer
from opentelemetry.trace import Status, StatusCode
from backend.core.event_bus import get_event_bus


event_bus = get_event_bus()
logger = structlog.get_logger()


class FollowupAgent:
    def __init__(self, shared_conext, event_bus, outcome_database=PostgresDatabase):
        self.shared_context = shared_conext
        self.outcome_database = outcome_database
        self.event_bus = event_bus
        
     
    async def run(self, user_id, run_id):

        try:
            logger.warning(f"Starting Follow up Agent for {run_id}")

            with tracer.start_as_current_span("FollowupAgent.run") as parent_span:
                agent_start = time.time()
                parent_span.set_attribute("agent", "followup")

                stretegy = await self.shared_context.pop(f"apply_followup_stretegy_{run_id}")
                if not stretegy:
                    logger.warning("No stretegy found for Follow up agent")
                    return

                mode = stretegy.get("mode")

                jobs = await self.outcome_database.get_jobs_by_user(user_id, limit=1000)
                if not jobs:
                    logger.warning(f"Job not found for {user_id}")

                parent_span.set_attribute("jobs.total", len(jobs))

                for job in jobs:
                    if job["status"] != "no_response":
                        continue

                    followup_count =job.get("followup_count", 0)

                    if followup_count >= 1:
                        logger.warning(
                            f"Skipping already updated with followup: {job['job_id']}"
                        )
                        continue

                    if mode == "reminder":
                        with tracer.start_as_current_span("EmitFollowup") as event_span:
                            event_time = time.time()
                            await self.event_bus.emit({
                                "type": "FOLLOWUP_JOB_REQUEST",
                                "payload": {
                                    "user_id": user_id,
                                    "run_id": run_id,
                                    "job_id": job["job_id"],
                                    "priority": "medium"
                                }
                            })

                            event_span.set_attribute("event.latency_seconds", time.time() - event_time)

                            logger.warning("Follow up Agent Emitting Follow up job request")

                parent_span.set_attribute("agent.latency_seconds", time.time() - agent_start)
    
        except Exception as e:
            if "parent_span" in locals():
                logger.exception(f"Error in follow up Agent: {e}")
                parent_span.record_exception(e)
                parent_span.set_status(Status(StatusCode.ERROR, str(e)))




