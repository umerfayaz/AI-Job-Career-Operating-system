from datetime import date, datetime
from pyexpat import features
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
    plan: str
    display_name: str
    daily_frontend_runs: int
    features: list[str]

class FeatureAccessResponse(BaseModel):
    feature: str
    has_access: bool

class FrontendAuthorizedResponse(BaseModel):
    authorized: bool
    plan: str
    limit: int
    used: int
    remaining: int

class AutonomousAuthorizedResponse(BaseModel):
    authorized: bool
    plan: str
    