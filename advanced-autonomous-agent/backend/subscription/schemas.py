from datetime import datetime
from pydantic import BaseModel


class UsageResponse(BaseModel):
    plan: str
    status: str
    used: int
    daily_limit: int
    remaining: int
    autonomous_enabled: bool
    expires_at: datetime | None

class CurrentPlanResponse(BaseModel):
    plan: str
    display_name: str
    daily_frontend_runs: int
    features: list[str]

class PlanResponse(BaseModel):
    id: str
    display_name: str
    daily_frontend_runs: int
    features: list[str]

class FeatureAccessResponse(BaseModel):
    feature: str
    has_access: bool

class FrontendAuthorizationResponse(BaseModel):
    authorized: bool
    plan: str
    limit: int
    used: int
    remaining: int

class AutonomousAuthorizationResponse(BaseModel):
    authorized: bool
    plan: str
