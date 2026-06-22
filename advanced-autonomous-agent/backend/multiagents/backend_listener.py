import structlog
import time
import json
import asyncio
from datetime import datetime, timedelta
from backend.observability.tracer import tracer
from backend.brain_outcomeLoop.profile_resolver import (
    active_search_profile_key,
    ensure_active_search_profile,
)
from opentelemetry.trace import Status, StatusCode
logger = structlog.get_logger()



class RefetchJobListener:
    def __init__(self, shared_context, event_bus, safe_runner, outcome_database):
        self.event_bus = event_bus
        self.shared_context = shared_context 
        self.task_semaphore = asyncio.Semaphore(10)
        self.shutdown_event  = asyncio.Event()
        self.safe_runner = safe_runner
        self.outcome_database = outcome_database

    async def load_active_profile(self, user_id: str, run_id: str) -> dict | None:
        return await ensure_active_search_profile(self.shared_context, user_id, run_id)

    async def refetch_job_listener(self):
        logger.info("REFETCH job listener started")

        while not self.shutdown_event.is_set():  
            try:
                queue = await self.event_bus.connect()
                logger.info("REFETCH listener connected")

                while not self.shutdown_event.is_set():
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=1)
                    except asyncio.TimeoutError:
                        continue

                    with tracer.start_as_current_span("refetch.job_listener") as parent_span:
                        start_refetch = time.time()

                        try:
                            if event.get("type") == "REFETCH_JOBS":
                                logger.info("Received REFETCH_JOBS event")

                                payload = event.get("payload", {})
                                user_id= payload.get("user_id")
                                run_id = payload.get("run_id")
                                policy_actions = payload.get("policy_actions", {})

                                if not user_id or not run_id:
                                    logger.error(
                                        "REFETCH_JOBS missing user_id or run_id",
                                        payload=payload,
                                    )
                                    continue

                                # Refetch Observavility tracing 
                                parent_span.set_attribute("refetch.event_type", event.get("type"))
                                parent_span.set_attribute("refetch.user_id", user_id)
                                parent_span.set_attribute("refetch.policy_actions", json.dumps(policy_actions))

                                with tracer.start_as_current_span("refetch.rebuild_job_listener") as rebuild_span:
                                    start_trigger_workflow = time.time()

                                    profile_key = active_search_profile_key(run_id)
                                    profile = await self.load_active_profile(user_id, run_id)

                                    logger.warning(
                                        f"Active search profile in backend listener: {profile_key}"
                                    )

                                    if profile and profile.get("workflow_status") == "running":
                                        logger.info(f"Workflow status already running for {run_id} -- skipping")
                                        continue

                                    if not profile:
                                        logger.error(f"Cannot refetch for {user_id} - no profile or preferences")
                                        continue

                                    if "initial_state" not in profile or "config" not in profile:
                                        logger.warning(f"Incomplete profile for {user_id} - skipping")
                                        continue

                                    # Autonomous refetch: align run_id so SourceAgent key matches scraper read
                                    profile["run_id"] = run_id
                                    profile["initial_state"]["run_id"] = run_id
                                    profile["initial_state"]["workflow_type"] = "autonomous_workflow"
                                    if policy_actions:
                                        profile["initial_state"]["policy_actions"] = policy_actions 
                                        profile["initial_state"]["apply_volume"] = policy_actions.get("apply_volume", "normal")
                                        logger.info(f"Injected policy_actions for {user_id}: {policy_actions}")


                                    cooldown_until = profile.get("cooldown_until")
                                    if cooldown_until:
                                        if datetime.now() < datetime.fromisoformat(cooldown_until):    
                                            logger.info(f"Refetch Skipped for {user_id} Cooldown is active {cooldown_until}")
                                            continue

                            
                                    from backend.api.server import execute_unified_job_matching

                                    task_id = profile.get("task_id", f"default_{user_id}")
                                    profile["cooldown_until"] = (
                                        datetime.now() + timedelta(seconds=300)
                                    ).isoformat()

                                    logger.info(f"Triggering refetch for user={user_id}")

                                    # Observability tracing
                                    rebuild_span.set_attribute("rebuild.trigger_workflow", profile.get("resume_id"))
                                    rebuild_span.set_attribute("rebuild.user_id", user_id)
                                    rebuild_span.set_attribute("rebuild.policy_actions", policy_actions.get("apply_volume"))
                                    rebuild_span.set_attribute("rebuild.latency_seconds", time.time() - start_trigger_workflow)


                                    resume_id = (
                                        profile.get("resume_id") or
                                        profile.get("initial_state", {}).get("resume_id") or
                                        profile.get("initial_state", {}).get("user_id") or
                                        user_id
                                    )

                                    profile["initial_state"]["target_resume_id"] = resume_id
                                    profile["initial_state"]["resume_id"] = resume_id

                                    async with self.task_semaphore:
                                        self.safe_runner.create_task(
                                            name=f"refetch_jobs_{user_id}",
                                            coro=execute_unified_job_matching(
                                                task_id=task_id,
                                                initial_state=profile["initial_state"],
                                                config=profile["config"]
                                            ),

                                            severity="normal",
                                            issue=f"refetch_jobs_{user_id}_crash",
                                            source="backend_listener"
                                        )

                                        logger.info(f"Refetch task created for {user_id}")

                        except asyncio.CancelledError:
                            logger.info("Refetch Listener loop stopped")
                            raise

                        except Exception as e:
                            logger.error(f"Error Processing event {event}", exc_info=True)
                            parent_span.record_exception(e)
                            parent_span.set_status(Status(StatusCode.ERROR, str(e)))

                        finally:
                            parent_span.set_attribute("refetch.latency_seconds", time.time() - start_refetch)
                        await asyncio.sleep(0)
            except Exception as e:
                logger.error(f"REFETCH listener crashed: {e}", exc_info=True)
                await asyncio.sleep(5)

    # Stopping loop

    def stop(self):
        logger.info("Stopping Refetch job listener")
        self.shutdown_event.set()


