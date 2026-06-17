import structlog
from backend.postgreSQL.models import AgentDecision
from backend.postgreSQL.engine import AsyncSessionLocal
from backend.postgreSQL.database import PostgresDatabase
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, update, desc, distinct
from datetime import timedelta, datetime, UTC

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
                stmt = insert(AgentDecision).values(**record).returning(AgentDecision.id)
                result = await session.execute(stmt)
                await session.commit()

                decision_id = result.scalar_one()
                logger.warning("Agent Decision created", decision_id=str(decision_id))

        
                return str(decision_id)

        except Exception as e:
            logger.error("Failed to create agent decision", error=str(e), exc_info=True)
            return None


    async def update_agent_decision(self, 
        decision_id: str,
        status: str,
        result_summary: str | None = None,
        error_message: str | None = None 
    ):

        try:

            async with AsyncSessionLocal() as session:
                stmt = (
                    update(AgentDecision).where(AgentDecision.id == decision_id).values(
                        status=status,
                        result_summary=result_summary,
                        error_message=error_message,
                        updated_at= datetime.now(UTC),
                    )
                )

                await session.execute(stmt)
                await session.commit()
            
            logger.warning("Agent Decision created", decision_id=decision_id, status=status)
        
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
                        "id": str(row.id),
                        "user_id": row.user_id,
                        "run_id": row.run_id,
                        "agent_name": row.agent_name,
                        "decision_type": row.decision_type,
                        "reason": row.reason,
                        "input_snapshot": row.input_snapshot,
                        "planned_actions": row.planned_actions,
                        "trigger_agent": row.trigger_agent,
                        "status": row.status,
                        "confidence": row.confidence,
                        "result_summary": row.result_summary,
                        "error_message": row.error_message,
                        "created_at": row.created_at,
                        "updated_at": row.updated_at
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

        total_jobs = len(jobs)
        applied_jobs = [j for j in jobs if j.get("status") == "applied"]
        rejected_jobs = [j for j in jobs if j.get("status") == "rejected"]
        interview_jobs = [j for j in jobs if j.get("status") == "interview"]
        pending_jobs = [j for j in jobs if j.get("status") == "pending"]

        no_response_jobs = [
            j for j in jobs
            if j.get("status") == "applied"
            and j.get("followup_count", 0) == 0
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
            "email_history": email_history
        }


