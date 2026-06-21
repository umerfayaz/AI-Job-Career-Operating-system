import time
import json
import structlog
from groq import AsyncGroq
from backend.config.settings import Settings
from backend.LLMGateway.fallbackmodels import Models
from backend.postgreSQL.database import PostgresDatabase
from backend.observability.tracer import tracer
from opentelemetry.trace import Status, StatusCode
from backend.core.event_bus import get_event_bus


event_bus = get_event_bus()
logger = structlog.get_logger()


class FollowupAgent:
    def __init__(self, shared_conext, event_bus, outcome_database=PostgresDatabase):
        self.settings = Settings()
        self.shared_context = shared_conext
        self.outcome_database = outcome_database
        self.client = AsyncGroq(api_key=self.settings.GROQ_API_KEY)
        self.models = Models(self.client)
        self.event_bus = event_bus
        
     
    async def run(self, user_id, run_id):

        try:
            logger.warning(f"Starting Follow up Agent for {run_id}")

            with tracer.start_as_current_span("FollowupAgent.run") as parent_span:
                agent_start = time.time()
                parent_span.set_attribute("agent", "followup")

                plan = await self.shared_context.read(f"stretegic_agent_plan_{run_id}")
                if not plan:
                    logger.warning("No plan found for followup agennt")
                    return


                task = plan.get("act", {}).get("recommended_sub_agents", [])
                followup_tasks = [ t for t in task if t.get("agent") == "FollowupAgent"]
                if not followup_tasks:
                    logger.warning("No followup tasks for followup agent")
                    return


                jobs = await self.outcome_database.get_jobs_by_user(user_id, limit=1000)
                
                eligible_jobs = [
                    job for job in jobs
                    if job.get("status") == "no_response"
                    and job.get("followup_count", 0) < 1 
                ]

                followup_decision = await self.reason_followup_with_llm(
                    stretegic_plan=plan,
                    followup_tasks=followup_tasks,
                    eligible_jobs=eligible_jobs
                )

                if not followup_decision.get("should_follow_up"):
                    logger.warning(f" FollowupAgent decided not to followup", reason=followup_decision.get("reason"))
                    return

                with tracer.start_as_current_span("EmitFollowup") as event_span:
                    event_time = time.time()

                    for item in followup_decision.get("selected_jobs", []):
                        await self.event_bus.emit({
                            "type": "FOLLOWUP_JOB_REQUEST",
                            "payload": {
                                "user_id": user_id,
                                "run_id": run_id,
                                "job_id": item["job_id"],
                                "priority": item.get("priority", "medium"),
                                "email_subject": item.get("email_subject"),
                                "email_body": item.get("email_body"),
                                "followup_angle": item.get("followup_angle"),
                                "reason": item.get("reason")
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

    
    async def reason_followup_with_llm(self, 
        stretegic_plan:dict, 
        followup_tasks: list, 
        eligible_jobs: list
    ):

        with tracer.start_as_current_span("followup.reason_followup") as llm_span:
            llm_time = time.time()

            compact_jobs = [
                {
                    "job_id": job.get("job_id"),
                    "job": job.get("job") or job.get("title") or job.get("job_title"),
                    "company": job.get("company"),
                    "status": job.get("status"),
                    "applied_at": str(job.get("applied_at")),
                    "outcome_at": str(job.get("outcome_at")),
                    "followup_count": job.get("followup_count"),
                    "last_followup_at": job.get("last_followup_at")
                }
                for job in eligible_jobs[:10]
            ]

            prompt = f"""
        You are FollowupAgent, a specialized career communication execution agent.

        Identity:
        - You do NOT decide the user's overall job-search strategy.
        - StrategicAgent has already made the strategic decision.
        - Your job is to decide whether follow-up communication is appropriate.
        - You reason over timing, professionalism, duplicate risk, and user benefit.
        - You generate follow-up recommendations and email drafts only when safe.

        StrategicAgent assigned task:
        {json.dumps(followup_tasks, default=str)}

        Strategic diagnosis:
        {json.dumps(stretegic_plan.get("diagnosis", {}), default=str)}

        Strategic plan:
        {json.dumps(stretegic_plan.get("plan", {}), default=str)}

        Strategic action policy:
        {json.dumps(stretegic_plan.get("actions", {}), default=str)}

        User/context signals:
        {json.dumps(stretegic_plan.get("observe", {}), default=str)}

        Eligible no-response jobs:
        {json.dumps(compact_jobs, default=str)}

        Decision rules:
        - Do not recommend follow-up if there are no eligible jobs.
        - Do not follow up on rejected, interview, pending, or already-followed-up jobs.
        - Prefer polite, concise, professional messages.
        - Do not sound desperate or pushy.
        - If data is early-stage or weak, use lower priority.
        - If the StrategicAgent says follow-up_strategy is "none", return should_follow_up false unless the assigned FollowupAgent task explicitly says otherwise.
        - One follow-up per job maximum.
        - Email body should be addressed to the hiring team, not a specific person unless available.
        - Never invent recruiter names.
        - Never claim qualifications not present in context.

        Return JSON ONLY.

        Schema:
        {{
        "should_follow_up": true,
        "reason": "short explanation",
        "selected_jobs": [
            {{
            "job_id": "string",
            "priority": "low|medium|high",
            "followup_angle": "string",
            "email_subject": "string",
            "email_body": "string"
            }}
        ],
        "skipped_jobs": [
            {{
            "job_id": "string",
            "reason": "string"
            }}
        ],
        "confidence": 0.0
        }}

        Rules:
        - No markdown.
        - No extra text outside JSON.
        - Only include job_ids from eligible jobs.
        - Keep email body under 160 words.
        - Keep tone professional, calm, and respectful.
        """ 
            try:
                llm_result = await self.models.json_completion(
                    task_type="cheap_json",
                    messages=[{
                        "role": "system",
                        "content": "You are a FollowupAgent. output valid JSON object only"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                    ],
                    temperature=0.2
                )
                if not llm_result.get("ok"):
                    logger.warning(
                        "FollowupAgent LLM Gateway failed",
                        error=llm_result.get("error"),
                    )

                    return {
                        "should_follow_up": False,
                        "reason": "LLM Gateway Failed",
                        "selected_jobs": [],
                        "skipped_jobs": [],
                        "confidence": 0.0
                    }

                content = llm_result.get("content", "").strip()
                parsed = json.loads(content)

                usage = llm_result.get("usage")
                MODEL_NAME = llm_result.get("model", "unknown")

                if not isinstance(parsed, dict):
                    raise ValueError("Followup agent LLM response was not a JSON object")
                
                selected_jobs = parsed.get("selected_jobs", list)
                if not isinstance(selected_jobs, []):
                    parsed["selected_jobs"] = []
                
                logger.warning(
                    "FollowupAgent reasoning completed",
                    should_follow_up=parsed.get("should_follow_up"),
                    selected_jobs=parsed.get("selected_jobs", []),
                    confidence=parsed.get("confidence", 0.0),
                    reason=parsed.get("reason")
                )

                # Opentelemetry Observability
                if usage:
                    llm_span.set_attribute("FollowupAgent.model", MODEL_NAME)
                    llm_span.set_attribute("FollowupAgent.prompt", prompt[:500])
                    llm_span.set_attribute("FollowupAgent.prompt_tokens", getattr(usage, "prompt_tokens", 0))
                    llm_span.set_attribute("Followup_agent.completion_tokens", getattr(usage, "completion_tokens", 0))
                    llm_span.set_attribute("FollowupAgent.total_tokens", getattr(usage, "total_tokens", 0))

                    total_tokens = getattr(usage, "total_tokens", 0)
                    model_cost = {
                        MODEL_NAME: 0.0001
                    }

                    cost = (total_tokens / 1000) * model_cost.get(MODEL_NAME, 0)

                    llm_span.set_attribute("FollowupAgent.total_estimated_cost_isd", cost)

                return parsed
            
            except Exception as e:
                logger.warning("FollowupAgen reasoning Failed")
                llm_span.record_exception(e)
                llm_span.set_status(Status(StatusCode.ERROR, str(e)))

                return {
                    "should_follow_up": False,
                    "reason": f"Reasoning Failed:{str(e)}",
                    "selected_jobs": [],
                    "skipped_jobs": [],
                    "confidence": 0.0
                }
            finally:
                llm_span.set_attribute("followup_reaosning.latency_seconds", time.time() - llm_time)








    


