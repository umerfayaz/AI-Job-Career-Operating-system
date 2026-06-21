import structlog
from backend.postgreSQL.models import AgentDecision
from backend.postgreSQL.engine import AsyncSessionLocal
from backend.postgreSQL.database import PostgresDatabase
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, update, desc
from datetime import datetime, UTC

logger = structlog.get_logger()


class DecisionWorkflow:
    def __init__(self):
        pass

    async def create_agent_decision(self, decision: dict):
        try:
            record = {
                "user_id": decision["user_id"],
                "run_id": decision.get("run_id"),
                "agent_name": decision.get("agent_name"),
                "decision_type": decision["decision_type"],
                "reason": decision["reason"],
                "input_snapshot": decision.get("input_snapshot"),
                "planned_actions": decision["planned_actions"],
                "trigger_agent": decision.get("trigger_agent"),
                "status": decision.get("status", "planned"),
                "confidence": decision.get("confidence"),
                "result_summary": decision.get("result_summary"),
                "error_message": decision.get("error_message"),
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC)
            }

            async with AsyncSessionLocal() as session:
                stmt = insert(AgentDecision).values(**record)

                stmt  = stmt.on_conflict_do_update(
                    index_elements=["user_id", "run_id", "decision_type"],
                    set_={
                        "agent_name": stmt.excluded.agent_name,
                        "reason": stmt.excluded.reason,
                        "input_snapshot": stmt.excluded.input_snapshot,
                        "planned_actions": stmt.excluded.planned_actions,
                        "trigger_agent": stmt.excluded.trigger_agent,
                        "status": stmt.excluded.status,
                        "confidence": stmt.excluded.confidence,
                        "result_summary": stmt.excluded.result_summary,
                        "error_message": stmt.excluded.error_message,
                        "created_at": stmt.excluded.created_at,
                        "updated_at": stmt.excluded.updated_at
                    }
                )

                await session.execute(stmt)
                await session.commit()

                logger.warning("Agent Decision created", 
                user_id=record["user_id"],
                run_id=record["run_id"],
                decision_type=record["decision_type"]
            )

            return {
                "user_id": record["user_id"],
                "run_id": record["run_id"],
                "decision_type": record["decision_type"]
            }

        except Exception as e:
            logger.error("Failed to create agent decision", error=str(e), exc_info=True)
            return None


    async def update_agent_decision(self, 
        user_id: str,
        status: str,
        result_summary: str | None = None,
        error_message: str | None = None 
    ):

        try:

            async with AsyncSessionLocal() as session:
                stmt = (
                    update(AgentDecision).where(AgentDecision.user_id == user_id).values(
                        status=status,
                        result_summary=result_summary,
                        error_message=error_message,
                        updated_at= datetime.now(UTC),
                    )
                )

                await session.execute(stmt)
                await session.commit()
            
            logger.warning("Agent Decision created", status=status)
        
        except Exception as e:
            logger.error("Failed to create agent decision", error=str(e), exc_info=True)

    async def get_recent_agent_decision(self, user_id: str, limit: int=20):
        try:
            async with AsyncSessionLocal() as session:
                stmt = (
                    select(AgentDecision).where(AgentDecision.user_id == user_id).order_by(
                        desc(AgentDecision.created_at)).limit(limit)
                )

                result = await session.execute(stmt)
                rows = result.scalars().all()

                return [
                    {
                        "run_id": row.run_id,
                        "agent_name": row.agent_name,
                        "decision_type": row.decision_type,
                        "reason": row.reason,
                        "planned_actions": row.planned_actions,
                        "trigger_agent": row.trigger_agent,
                        "status": row.status,
                        "confidence": row.confidence,
                        "result_summary": row.result_summary,
                        "created_at": row.created_at,
                    }

                    for row in rows
                ]
            
        except Exception as e:
            logger.error("Failed to fetch agent decision", error=str(e), exc_info=True)


class UserIntelligence:
    def __init__(self, outcome_database: PostgresDatabase, decision_workflow: DecisionWorkflow):
        self.outcome_database = outcome_database
        self.decision_workflow = decision_workflow

    async def get_user_intelligence(self, user_id: str):
        user = await self.outcome_database.get_active_user_id(user_id)
        jobs = await self.outcome_database.get_jobs_by_user(user_id)
        agent_state = await self.outcome_database.get_agent_state(user_id)
        recent_decisions = await self.decision_workflow.get_recent_agent_decision(user_id)
        report_history = await self.outcome_database.get_report_history_by_user(user_id, limit=20)
        email_history = await self.outcome_database.get_email_history_by_user(user_id, limit=20)
        resume_history = await self.outcome_database.get_resume_history_by_user(user_id, limit=20)

        total_jobs = len(jobs)
        applied_jobs = [j for j in jobs if j.get("status") == "applied"]
        rejected_jobs = [j for j in jobs if j.get("status") == "rejected"]
        interview_jobs = [j for j in jobs if j.get("status") == "interview"]
        pending_jobs = [j for j in jobs if j.get("status") == "pending"]

        no_response_jobs = [
            j for j in jobs
            if j.get("status") == "no_response"
        ]

        interview_rate = round((len(interview_jobs) / total_jobs) * 100, 2) if total_jobs else 0
        rejection_rate = round((len(rejected_jobs) / total_jobs) * 100, 2) if total_jobs else 0

        return {
            "user": {
                "user_id": user.user_id if user else user_id,
                "email": user.email if user else None,
                "name": user.name if user else None,
                "last_active": str(user.last_active) if user and user.last_active else None,
            },
            "job_metrics": {
                "total_jobs": total_jobs,
                "applied_count": len(applied_jobs),
                "rejected_count": len(rejected_jobs),
                "interview_count": len(interview_jobs),
                "pending_count": len(pending_jobs),
                "no_response_count": len(no_response_jobs),
                "interview_rate": interview_rate,
                "rejection_rate": rejection_rate,
            },
            "recent_jobs": jobs[:20],
            "recent_rejections": rejected_jobs[:10],
            "recent_interviews": interview_jobs[:10],
            "no_response_jobs": no_response_jobs[:10],
            "agent_state": agent_state,
            "recent_agent_decisions": recent_decisions,
            "report_history": report_history,
            "email_history": email_history,
            "resume_history": resume_history
        }
    
    def build_executive_summary(self, row: dict) -> dict:
        user = row.get("user", {})
        jobs = row.get("recent_jobs", [])
        reports = row.get("report_history", [])
        emails = row.get("email_history", [])
        resumes = row.get("resume_history", [])
        decisions = row.get("recent_agent_decisions", [])
        metrics = row.get("job_metrics", {})
        
        # Metrics for llm to fetch
        total_jobs = metrics.get("total_jobs", 0)
        applied_count = metrics.get("applied_count", 0)
        interview_count = metrics.get("interview_count", 0)
        rejected_count = metrics.get("rejected_count", 0)
        no_response_count = metrics.get("no_response_count", 0)

        if total_jobs == 0:
            application_health = "insufficient_data"
        elif interview_count > 0:
            application_health = "positive_signal"
        elif rejected_count >= 3:
            application_health = "resume_or_fit_problem"
        elif no_response_count >= 3:
            application_health = "targeting_or_visibility_problem"
        elif applied_count > 0:
            application_health = "early_stage_waiting"
        else:
            application_health = "insufficient_data"

        latest_resume = resumes[0] if resumes else {}
        latest_report = reports[0] if reports else {}

        clicked_jobs = [
            {
                "title": j.get("job") or j.get("title"),
                "company": j.get("company"),
                "status": j.get("status"),
                "clicked_at": str(j.get("clicked_at")) if j.get("clicked_at") else None,
            }
            for j in jobs[:5]
        ]

        return {
            "user": {
                "name": user.get("name"),
                "user_id": user.get("user_id"),
            },
            "career_signal": {
                "latest_resume_direction": latest_resume.get("summary", "")[:300],
                "latest_skills": latest_resume.get("skills", [])[:10],
                "experience_years": latest_resume.get("experience_years"),
                "resume_trend": [
                    {
                        "resume_version": r.get("resume_version", "v1"),
                        "direction_hint": r.get("summary", "")[:120],
                    }
                    for r in resumes[:3]
                ],
            },
            "behavior_signal": {
                "recently_clicked_jobs": clicked_jobs,
                "clicked_jobs_count": len(clicked_jobs),
            },
            "market_signal": {
                "latest_report_top_roles": (
                    latest_report.get("recommended_actions", {}).get("top_roles", [])[:5]
                    if latest_report else []
                ),
                "latest_report_top_companies": (
                    latest_report.get("recommended_actions", {}).get("top_companies", [])[:5]
                    if latest_report else []
                ),
                "highest_match_score": latest_report.get("highest_match_score"),
            },
            "execution_signal": {
                "emails_sent": len([e for e in emails if e.get("status") == "sent"]),
                "recent_email_statuses": [
                    {
                        "type": e.get("email_type"),
                        "status": e.get("status"),
                        "subject": e.get("subject"),
                    }
                    for e in emails[:3]
                ],
            },
            "performance_signal": {
                "application_health": application_health,
                "total_jobs": total_jobs,
                "applied_count": applied_count,
                "interview_count": interview_count,
                "rejected_count": rejected_count,
                "no_response_count": no_response_count,
                "main_signal": (
                    "Not enough outcome data yet"
                    if application_health == "insufficient_data"
                    else "Applications are still waiting for response"
                    if application_health == "early_stage_waiting"
                    else "Some applications are converting into interviews"
                    if application_health == "positive_signal"
                    else "Rejections suggest resume/role fit may need improvement"
                    if application_health == "resume_or_fit_problem"
                    else "No responses suggest targeting, timing, or visibility problem"
                    if application_health == "targeting_or_visibility_problem"
                    else "No clear performance signal yet"
                ),
            },
            "memory_signal": {
                "recent_strategy_summaries": [
                    {
                        "decision_type": d.get("decision_type"),
                        "reason": d.get("reason"),
                        "confidence": d.get("confidence"),
                    }
                    for d in decisions[:3]
                ],
              },
            }
        


