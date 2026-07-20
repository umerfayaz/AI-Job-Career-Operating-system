from dataclasses import dataclass, field
from .enums import PlanType, FeatureType

@dataclass(frozen=True)
class PlanConfig:

    id: PlanType
    display_name: str
    price: int
    billing_period: str
    daily_frontend_runs: int
    description: str

    features: set[FeatureType] = field(default_factory=set)

  
FREE_PLAN = PlanConfig(
    id=PlanType.FREE,
    display_name="Free",
    price=0,
    billing_period="Forever",
    daily_frontend_runs=3,
    description="Perfect for getting started",

    features={
        FeatureType.FRONTEND_WORKFLOW
    }
)


PRO_PLAN = PlanConfig(
    id=PlanType.PROFESSIONAL,
    display_name="Professional",
    price=14,
    billing_period="month",
    daily_frontend_runs=25,
    description="For professionals who want higher workflow limits and advanced AI capabilities",

    features={
        FeatureType.FRONTEND_WORKFLOW,
        FeatureType.RAG,
        FeatureType.BM25,
        FeatureType.HYBRID_RETRIEVER,
        FeatureType.ADVANCED_REPORTS
    }
)

AUTONOMOUS_AI = PlanConfig(
    id=PlanType.AUTONOMOUS,
    display_name="Autonomous AI OS",
    price=30,
    billing_period="month",
    daily_frontend_runs=-1,
    description="Fully autonomous AI career operating system",

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
    PlanType.FREE: FREE_PLAN,
    PlanType.PROFESSIONAL: PRO_PLAN,
    PlanType.AUTONOMOUS: AUTONOMOUS_AI
}


def get_plan(plan: PlanType) -> PlanConfig:
    return PLAN_REGISTRY[plan]

