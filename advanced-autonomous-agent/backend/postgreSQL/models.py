from sqlalchemy import Column, String, Integer, Text
from backend.postgreSQL.engine import Base


class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True)
    user_id = Column(String, primary_key=True)

    job = Column(String)
    company = Column(String)
    status = Column(String)

    applied_at = Column(Text)
    outcome_at = Column(Text)

    source = Column(Text)
    resume_version = Column(Text)

    last_email_check = Column(Text)
    message_id = Column(Text)

    clicked_at = Column(Text)

    no_response_notified = Column(Integer, default=0)
    dead_application_notified = Column(Integer, default=0)
    rejected_notified = Column(Integer, default=0)
    interview_notified = Column(Integer, default=0)

    last_followup_at = Column(Text)
    followup_count = Column(Integer, default=0)

class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)

    name = Column(String)
    password_hash = Column(String)

    created_at = Column(Text)
    last_active = Column(Text)

class AgentState(Base):
    __tablename__ = "agent_state"

    user_id = Column(String, primary_key=True)

    last_metrics = Column(Text)
    last_fingerprint = Column(String)

    last_refetch_at = Column(Text)
    cooldown_until = Column(Text)

    last_run_id = Column(String)
    updated_at = Column(Text)
