from dataclasses import dataclass, field
from .enums import PlanType, FeatureType

@dataclass(frozen=True)
class SubscriptionPlan:

    id: PlanType
    display_name: str
    daily_frontend_runs: int

    features: set[FeatureType] = field(default_factory=set)

  
FREE_PLAN = SubscriptionPlan(
    id=PlanType.FREE,
    display_name="Free",
    daily_frontend_runs=3,

    features={
        FeatureType.FRONTEND_WORKFLOW
    }
)


PRO_PLAN = SubscriptionPlan(
    id=PlanType.PROFESSIONAL,
    display_name="Professional",
    daily_frontend_runs=25,

    features={
        FeatureType.FRONTEND_WORKFLOW,
        FeatureType.RAG,
        FeatureType.BM25,
        FeatureType.HYBRID_RETRIEVER,
        FeatureType.ADVANCED_REPORTS
    }
)

AUTONOMOUS_AI = SubscriptionPlan(
    id=PlanType.AUTONOMOUS,
    display_name="Autonomous AI",
    daily_frontend_runs=-1,

    features={
        FeatureType.FRONTEND_WORKFLOW,
        FeatureType.AUTONOMOUS_WORKFLOW,
        FeatureType.MULTI_AGENT_SYSTEM,
        FeatureType.STRETEGIC_PLANNER,
        FeatureType.RAG,
        FeatureType.BM25,
        FeatureType.RERANKER,
        FeatureType.HYBRID_RETRIEVER,
        FeatureType.AGENT_MEMORY,
        FeatureType.DECISION_HISTORY,
        FeatureType.EMAIL_MONITORING,
        FeatureType.FOLLOWUP_AUTOMATION,
        FeatureType.ADVANCED_REPORTS
    }
)


PLAN_REGISTRY = {
    PlanType.FREE: "FREE",
    PlanType.PROFESSIONAL: "PROFESSIONAL",
    PlanType.AUTONOMOUS: "AUTONOMOUS AI"
}


def get_plan(plan: PlanType) -> SubscriptionPlan:
    return PLAN_REGISTRY[plan]
    
