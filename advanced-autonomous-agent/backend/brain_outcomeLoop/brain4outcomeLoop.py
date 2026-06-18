import asyncio
from dateutil import parser
from typing import Dict
import structlog
from backend.core.safeRunner import SafeRunner
from backend.brain_outcomeLoop.fingerprint_policy import fingerprint_policy
from backend.postgreSQL.database import PostgresDatabase
from backend.brain_outcomeLoop.stretegic_agent import stretegic_agent 
from backend.AgenticStretegies.apply_source import SourceAgent

from backend.observability.tracer import tracer
from opentelemetry.trace import Status, StatusCode
from backend.AgenticStretegies.apply_followup import FollowupAgent
from backend.AgenticStretegies.stretegy_executor import stretegyExecutor
from backend.brain_outcomeLoop.profile_resolver import ensure_active_search_profile
from backend.core.event_bus import get_event_bus
from datetime import datetime
import time

logger = structlog.get_logger()
event_bus = get_event_bus()


class OutComeLoop:
    def __init__(self, shared_context,event_bus, outcome_database, user_intelligence, re_fetch_event_emitter=None,):
        self.outcome_database = outcome_database
        self.shared_context = shared_context
        self.event_bus =event_bus
        self.user_intelligence = user_intelligence
        self.safe_runner = SafeRunner(self.event_bus)
        self.stretegic_agent = stretegic_agent(shared_context=self.shared_context, user_intelligence=self.user_intelligence)
        self.stretegy_execute = stretegyExecutor(self.shared_context, self.event_bus, self.outcome_database)
        self.follow_up_agent = FollowupAgent(self.shared_context, self.event_bus, self.outcome_database)
        self.source_agent =  SourceAgent(self.shared_context)
        self.refetch_listener = None
        self.is_running = False

        self.no_response_days = 3
        self.dead_application = 5
        self.reply_threshold = 0.2
        self.no_reply_threshold = 0.5
        self._shutdown_event = asyncio.Event()


    async def should_refetch(self, actions: Dict) ->bool:
        return (
            actions.get("trigger_workflow") is True and
            actions.get("apply_volume") in ("high", "normal")
        )

    async def run_loop(self, internal_seconds=60):
        logger.info("Initializing DB outcome")

        self.is_running = True
        logger.info("Brain4 loop is started")

        while self.is_running:
            span = None
            outcome_start = time.time()

            try:
                with tracer.start_as_current_span("brain4.process_outcome_loop") as span:
                    await self.process_outcome()
                
            except Exception as e:
                if span:
                    logger.exception(f"Outcome loop error {e}")
                    span.set_status(Status(StatusCode.ERROR, str(e)))
            
            finally:
                if span:
                    span.set_attribute("brain4_outcomeloop.latency_seconds", time.time() - outcome_start)
                
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=internal_seconds
                )
                break
            except asyncio.TimeoutError:
                continue
        logger.info("Brain4 LOOP stopped")

    async def process_outcome(self):

        offset = 0
        BATCHSIZE = 50

        await self.outcome_database.fetch_new_jobs_from_email()

        while True:

            applied_jobs = await self.outcome_database.get_applied_jobs(
                limit=BATCHSIZE,
                offset=offset
            )

            if not applied_jobs:
                break
            
            offset += BATCHSIZE
            now_time = datetime.now()

            for job in applied_jobs:
                applied_at = job.get("applied_at")
                status = job.get("status")
                outcome_at = job.get("outcome_at")

                applied_at = parser.parse(applied_at) if isinstance(applied_at, str) else None
                outcome_at = parser.parse(outcome_at) if isinstance(outcome_at, str) else None

                if not applied_at:
                    continue

                # no_response
                if (
                    status == "applied"
                    and (now_time - applied_at).days >= self.no_response_days
                    and not outcome_at
                ):
                    job["status"] = "no_response"
                    job["outcome_at"] = now_time.isoformat()
                    await self.outcome_database.update_job(job)

                    await self.event_bus.emit({
                        "type": "JOB_STATUS_CHANGED",
                        "job_id": job["job_id"],
                        "user_id": job["user_id"],
                        "old_status": "applied",
                        "new_status": "no_response",
                        "job_metadata": job,
                        "source": "brain4",
                        "timestamp": datetime.now().isoformat()
                    })

                # dead_application
                elif (
                    status == "no_response"
                    and (now_time - applied_at).days >= self.dead_application
                ):
                    job["status"] = "dead_application"
                    job["outcome_at"] = datetime.now().isoformat()
                    await self.outcome_database.update_job(job)

                    await self.event_bus.emit({
                        "type": "JOB_STATUS_CHANGED",
                        "job_id": job["job_id"],
                        "user_id": job["user_id"],
                        "old_status": "no_response",
                        "new_status": "dead_application",
                        "job_metadata": job,
                        "source": "brain4",
                        "timestamp": datetime.now().isoformat()
                    })

                # EMAIL CHECK (THIS MUST BE INSIDE LOOP)
                if job.get("status") in ("rejected", "interview", "no_response", "dead_application") or not job.get("message_id"):
                    logger.debug(f"Skipping already Processed job:{job['job_id']} with status {job.get('status')}")
                    continue

                reply_status = await self.outcome_database.check_email_reply(job)

                if reply_status != job.get("status"):
                    job["status"] = reply_status
                    job["outcome_at"] = datetime.now().isoformat()
                    await self.outcome_database.update_job(job)
                    logger.info(f"job {job['job_id']} updated from email reply {reply_status}")


            users = await self.outcome_database.get_active_user_ids()
            for user_id in users:
                user_jobs = await self.outcome_database.get_jobs_by_user(user_id, limit=1000)
                run_id = await self.shared_context.read(f"current_run_id_{user_id}")
                if not run_id:
                    run_id = f"run_brain4_{user_id}_{int(datetime.now().timestamp())}"
                skip_strategy = False
                wrote_new_proposal = False

                # metrics
                metrics = self.calculate_metrics(user_jobs)

                await self.shared_context.write(
                    key=f"outcome_metrics_{user_id}",
                    value={
                        **metrics,
                        "source": "brain4",
                        "last_updates": datetime.now().isoformat()
                    },
                    agent_name="brain4"
                )

                logger.info(f"Outcome loop metrics: {metrics}")
                actions = None

                state = await self.outcome_database.get_agent_state(user_id)
                last_metrics = state["last_metrics"] if state else None

                if last_metrics == metrics:
                    logger.info("Skipping stretgic agent workflow same metrics detected")
                else:
                    # Observability tracing with decisions
                    with tracer.start_as_current_span("brain4.stretegic_decision") as span:
                        stretegic_decision_start = time.time()

                        strategic_decision = await self.stretegic_agent.decide(metrics, {
                            "user_id": user_id,
                            "jobs": user_jobs,
                            "run_id": run_id
                        })
                        
                        logger.info(f"Stretgic agent policies recommending {strategic_decision}")
                        actions = strategic_decision.get("actions", {})

                        new_fingerprint_policy = fingerprint_policy(actions)

                        last_fingerprint_policy = state["last_fingerprint"] if state else None

                        if new_fingerprint_policy == last_fingerprint_policy:
                                logger.info("Strategic agent proposed identical policy - skipped")
                                skip_strategy = True

                        if not skip_strategy:
                            # Calling Stretegy Executor here to execute the Agents 
                            await self.stretegy_execute.execute(actions, user_id, run_id)
                            logger.warning(f"Calling stretegy in outcome loop for {run_id}")

                            await self.shared_context.write(
                                    key=f"policy_proposal_{user_id}",
                                    value=strategic_decision,
                                    agent_name="strategic_agent",
                                )
                            logger.info(f"Outcome loop policy updated: {strategic_decision}")
                            wrote_new_proposal = True

                            # Updating agent state memory
                            await self.outcome_database.update_agent_state(user_id, {
                                "last_metrics": metrics,
                                "last_fingerprint": new_fingerprint_policy,
                                "last_refetch_at": datetime.now().isoformat()
                            })
                        
                        span.set_attribute("user_id", user_id)
                        span.set_attribute("metrics.reply_rate", metrics["reply_rate"])
                        span.set_attribute("metrics.rejection_rate", metrics["rejection_rate"])
                        span.set_attribute("stretegic_decision.latency_seconds", time.time() - stretegic_decision_start)

                approved = await self.shared_context.read(f"policy_approved_{user_id}")
                if wrote_new_proposal and approved:
                    logger.info(
                        f"Deferring stale policy_approved for {user_id} until Brain3 approves new proposal"
                    )
                    await self.shared_context.pop(f"policy_approved_{user_id}")
                    approved = None

                if approved and approved.get("approved") is True:
                    approved_actions = approved.get("actions", {}) or {}

                    source_strategy = await self.shared_context.read(
                        f"apply_source_stretegy_{run_id}"
                    )
                    needs_source = (
                        approved_actions.get("source_stretegy") == "shift"
                        or (
                            isinstance(source_strategy, dict)
                            and source_strategy.get("mode") == "shift"
                        )
                    )

                    if self.refetch_listener:
                        profile = await self.refetch_listener.load_active_profile(
                            user_id, run_id
                        )
                    else:
                        profile = await ensure_active_search_profile(
                            self.shared_context, user_id, run_id
                        )

                    if needs_source:
                        with tracer.start_as_current_span("brain4.source_agent") as span:
                            start_source_agent = time.time()
                            if profile:
                                await self.source_agent.run(user_id, run_id)
                                logger.warning(
                                    f"Source agent completed before refetch for {run_id}"
                                )
                            else:
                                logger.warning(
                                    f"Skipping source agent — no profile for {run_id}"
                                )
                            span.set_attribute("source_agent.user_id", user_id)
                            span.set_attribute(
                                "source_agent.latency_seconds",
                                time.time() - start_source_agent,
                            )

                    if not needs_source or profile:
                        await self.event_bus.emit({
                            "type": "REFETCH_JOBS",
                            "payload": {
                                "user_id": user_id,
                                "run_id": run_id,
                                "policy_actions": approved_actions,
                            },
                            "source": "brain4",
                            "timestamp": datetime.now().isoformat(),
                        })
                        logger.warning(
                            "Refetch triggered after policy approval by brain3"
                        )
                    else:
                        logger.warning(
                            f"Deferred REFETCH_JOBS until profile exists for {run_id}"
                        )

                    if approved_actions.get("follow_up_stretegy") == "reminder":
                        with tracer.start_as_current_span("brain4.followup_agent") as span:
                            start_followup_agent = time.time()
                            await self.follow_up_agent.run(user_id, run_id)
                            logger.warning(
                                f"Running follow-up agent after approval for {user_id}"
                            )
                            span.set_attribute("followup_agent.user_id", user_id)
                            span.set_attribute(
                                "followup_agent.latency_seconds",
                                time.time() - start_followup_agent,
                            )

                    await self.shared_context.pop(f"policy_approved_{user_id}")

    def calculate_metrics(self, jobs):

        valid_jobs = [
            j for j in jobs
            if j.get("status") in ["interview", "rejected", "no_response", "dead_application"]
        ]

        total =  len(valid_jobs)
        if total == 0:
            return {"reply_rate": 0, "rejection_rate": 0, "no_response_rate": 0, "dead_application_rate": 0, "total": 0}
            
        reply = sum(1 for j in valid_jobs if j["status"] == "interview")
        reject = sum(1 for j in valid_jobs if j["status"] == "rejected")
        no_response = sum(1 for j in valid_jobs if j["status"] == "no_response")
        dead_application =sum(1 for j in valid_jobs if j["status"] == "dead_application")

        return {
            "reply_rate": reply / total, 
            "rejection_rate": reject / total,
            "no_response_rate": no_response / total, 
            "dead_application_rate": dead_application/total,
            "total": total
        }
    










