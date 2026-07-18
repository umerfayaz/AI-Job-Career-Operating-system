from sqlalchemy import (
    Column, 
    String, 
    Integer, 
    Text, 
    ForeignKey, 
    DateTime, 
    Boolean, 
    Index
)
from backend.postgreSQL.engine import Base
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from sqlalchemy import Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    job = Column(String, nullable=False)
    company = Column(String, nullable=False)
    status = Column(String, default="applied", nullable=False)
    applied_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    outcome_at = Column(DateTime(timezone=True))
    source = Column(Text)
    resume_version = Column(String)
    last_email_check = Column(DateTime(timezone=True))
    message_id = Column(Text)
    clicked_at = Column(DateTime(timezone=True))
    no_response_notified = Column(Boolean, default=False, nullable=False)
    dead_application_notified = Column(Boolean, default=False, nullable=False)
    rejected_notified = Column(Boolean, default=False, nullable=False)
    interview_notified = Column(Boolean, default=False, nullable=False)
    followup_count = Column(Integer, default=0, nullable=False)
    last_followup_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="jobs")

    __table_args__ = (
        Index("idx_jobs_user_id", "user_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_user_status", "user_id", "status"),
        Index("idx_jobs_applied_at", "applied_at")
    )

class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String)
    password_hash = Column(String, nullable=False)
    jobs=relationship("Job", back_populates="user", cascade="all, delete-orphan")
    agent_state=relationship("AgentState", back_populates="user", uselist=False)
    subscription = relationship(
        "SubscriptionPlan",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_active = Column(DateTime(timezone=True))

class AgentState(Base):
    __tablename__ = "agent_state"

    user_id = Column(String, ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    last_metrics = Column(JSONB)
    last_fingerprint = Column(String)
    last_refetch_at = Column(DateTime(timezone=True))
    cooldown_until = Column(DateTime(timezone=True))
    last_run_id = Column(String)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user = relationship("User", back_populates="agent_state")


# Source of truth for stretegic Agent to reason

class AgentDecision(Base):
    __tablename__ = "agent_decision"

    user_id = Column(String, ForeignKey("users.user_id"), nullable=False, index=True, primary_key=True)
    run_id = Column(String, primary_key=True, index=True)
    agent_name = Column(String, nullable=False, default="Stretegic_agent")
    decision_type = Column(String, primary_key=True, index=True)
    reason = Column(Text, nullable=False)
    input_snapshot = Column(JSONB, nullable=True)
    planned_actions = Column(Text, nullable=False)
    trigger_agent = Column(String, nullable=True)
    status = Column(String, nullable=False, default="planned")
    confidence = Column(Float, nullable=False)
    result_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)
    updated_at =  Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class ReportHistory(Base):
    __tablename__ = "report_history"

    user_id = Column(String, ForeignKey("users.user_id"), primary_key=True, index=True)
    run_id = Column(String, primary_key=True, index=True)
    report_type = Column(String, nullable=False, default="job_match_report")
    summary = Column(Text, nullable=True)
    top_jobs_count = Column(Integer, nullable=False, default=0)
    highest_match_score = Column(Float, nullable=True)
    recommended_actions = Column(JSONB, nullable=True)

    email_subject = Column(String, nullable=True)
    sent_to_email = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)


class EmailHistory(Base):
    __tablename__ = "email_history"

    user_id = Column(String, ForeignKey("users.user_id"), primary_key=True, index=True)
    run_id = Column(String, primary_key=True, index=True)

    email_type = Column(String, primary_key=True, nullable=False)
    recipient = Column(String, nullable=False)
    subject = Column(String, nullable=False)

    status = Column(String, nullable=False, default="queued")
    provider_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True )
    metadata_json = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), default = lambda: datetime.now(UTC), index=True)
    updated_at = Column(DateTime(timezone=True), default = lambda: datetime.now(UTC), onupdate = lambda: datetime.now(UTC))


class ResumeHistory(Base):
    __tablename__ = "resume_history"

    user_id = Column(String, ForeignKey("users.user_id"), primary_key=True, index=True)
    run_id = Column(String, primary_key=True, index=True)

    resume_version = Column(String, nullable=False, default="v1")
    summary = Column(Text, nullable=True)
    skills = Column(JSONB, nullable=True)
    experience_years = Column(Float, nullable=True)
    source = Column(String, nullable=True, default="resume_upload")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True)