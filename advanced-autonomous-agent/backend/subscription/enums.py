from enum import Enum

class PlanType(str, Enum):
    FREE = "free"
    PROFESSIONAL = "professional"
    AUTONOMOUS = "autonomous"


class FeatureType(str, Enum):
    FRONTEND_WORKFLOW = "frontend_workflow"
    WORKFLOW_DAILY_RUN = "workflow_daily_runs"

    RAG = 'rag'
    BM25 = "bm25"
    HYBRID_RETRIEVER = "hybrid_retrieval"
    RERANKER = "reranker"

    AUTONOMOUS_WORKFLOW = "autonomous_workflow"
    MULTI_AGENT_SYSTEM = "multi_agent_system"
    STRETEGIC_PLANNER = "stretegic_planner"
    EMAIL_MONITORING = "email_monitoring"
    AGENT_MEMORY = "agent_memory"
    DECISION_HISTORY = "decision_history"
    CONTINUOUS_MONITORING = "continous_monitoring"
    FOLLOWUP_AUTOMATION = "followup_automation"

    ADVANCED_REPORTS = "advanced_reports"
    




