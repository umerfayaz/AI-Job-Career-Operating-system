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


