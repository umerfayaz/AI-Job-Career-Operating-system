"""Shared helpers for active search profiles keyed by run_id."""

from datetime import datetime
import structlog

logger = structlog.get_logger()


def active_search_profile_key(run_id: str) -> str:
    return f"active_search_profile_{run_id}"


async def get_active_search_profile(shared_context, user_id: str, run_id: str) -> dict | None:
    """Read profile by run_id, then legacy user_id key (migrates legacy to run_id)."""
    profile = await shared_context.read(active_search_profile_key(run_id))
    if profile:
        return profile

    legacy = await shared_context.read(f"active_search_profile_{user_id}")
    if legacy:
        await shared_context.write(
            active_search_profile_key(run_id),
            legacy,
            "profile_resolver",
        )
        logger.info(f"Migrated legacy profile to run_id key for {run_id}")
    return legacy


async def rebuild_profile_from_preferences(user_id: str, run_id: str | None = None) -> dict | None:
    try:
        from backend.api.server import get_agent_app

        agent_app = await get_agent_app()
        prefs = agent_app.memory.preferences_collection.get(ids=[user_id])

        if not prefs or not prefs.get("ids"):
            logger.warning(f"No prefs found for {user_id}; cannot rebuild profile")
            return None

        meta = prefs["metadatas"][0]
        resume_id = meta.get("resume_id") or user_id
        skills = meta.get("skills", "").split(",") if meta.get("skills") else []
        resume_text = meta.get("resume_text")
        email = meta.get("email")
        keywords = meta.get("job_keywords", "").split(",") if meta.get("job_keywords") else []
        location = meta.get("location", "Remote")

        initial_state = {
            "task": "Find and match job opportunities for uploaded resume",
            "task_type": "job_matching",
            "workflow_type": "autonomous_workflow",
            "task_id": user_id,
            "user_id": user_id,
            "priority": 5,
            "skills": skills,
            "resume_text": resume_text,
            "resume_id": resume_id,
            "job_keywords": keywords,
            "job_location": location,
            "experience_level": "mid",
            "run_id": run_id,
            "user_email": email,
            "plan": [],
            "current_step": 0,
            "reasoning_history": [],
            "search_queries": [],
            "search_results": [],
            "scraped_content": [],
            "extracted_insights": [],
            "analysis_results": {},
            "relevant_memories": [],
            "entity_context": {},
            "conversation_history": [],
            "confidence_score": 0.0,
            "validation_results": {},
            "errors": [],
            "retry_count": 0,
            "final_output": None,
            "artifacts": [],
            "iteration": 0,
            "max_iteration": 10,
            "started_at": datetime.now().isoformat(),
            "status": "pending",
            "jobs_data": [],
            "matched_jobs": [],
            "quality_check": {},
            "email_status": {},
            "report_data": {},
            "final_report": None,
            "pdf_path": None,
        }

        return {
            "user_id": user_id,
            "run_id": run_id,
            "resume_id": resume_id,
            "resume_text": resume_text,
            "initial_state": initial_state,
            "workflow_status": "idle",
            "config": {"configurable": {"thread_id": user_id}},
            "task_id": user_id,
            "cooldown_until": None,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to rebuild profile for {user_id}: {e}", exc_info=True)
        return None


async def ensure_active_search_profile(shared_context, user_id: str, run_id: str) -> dict | None:
    """Return an active search profile, rebuilding from preferences when missing."""
    profile = await get_active_search_profile(shared_context, user_id, run_id)
    if profile:
        return profile

    profile = await rebuild_profile_from_preferences(user_id, run_id)
    if not profile:
        return None

    await shared_context.write(
        active_search_profile_key(run_id),
        profile,
        "profile_resolver",
    )
    logger.info(f"Rebuilt active search profile for run_id={run_id}")
    return profile
