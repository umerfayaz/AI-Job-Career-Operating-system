from .schemas import (
    UsageResponse,
    CurrentPlanResponse,
    PlanResponse,
    FrontendAuthorizationResponse,
    AutonomousAuthorizationResponse,
    FeatureAccessResponse
)

from fastapi import APIRouter, Depends, HTTPException
from backend.auth.auth_routes import get_current_user
from .service import SubscriptionService
from .plans import PLAN_REGISTRY
from .enums import FeatureType


router = APIRouter(prefix="/api/subscription", tags=["subscription"])
subscription_service = SubscriptionService()


@router.post("/authorize/frontend", response_model=FrontendAuthorizationResponse)
async def authorize_frontend_workflow(user_id: str = Depends(get_current_user)):
    return await subscription_service.authorize_frontend_workflow(user_id)

@router.post("/authorize/autonomous", response_model=AutonomousAuthorizationResponse)
async def authorize_autonomous_workflow(user_id: str = Depends(get_current_user)):
    return await subscription_service.authorize_autonomous_workflow(user_id)

@router.get("/usage", response_model=UsageResponse )
async def get_usage(user_id: str = Depends(get_current_user)):
    return await subscription_service.get_dashboard_usage(user_id)


@router.get("/plan", response_model=CurrentPlanResponse)
async def get_current_plan(user_id: str = Depends(get_current_user)):
    plan = await subscription_service.get_plan(user_id)

    return{
        "plan": plan.id.value,
        "display_name": plan.display_name,
        "price": plan.price,
        "billing_period": plan.billing_period,
        "daily_frontend_runs": plan.daily_frontend_runs,
        "description": plan.description,
        "features": sorted([f.value for f in plan.features])
    }

@router.get("/plans", response_model = list[PlanResponse])
async def list_all_plans():
    return [
        {
            "id": p.id.value,
            "display_name": p.display_name,
            "price": p.price,
            "billing_period": p.billing_period,
            "daily_frontend_runs": p.daily_frontend_runs,
            "description": p.description,
            "features": sorted([f.value for f in p.features]),
        }
        for p in PLAN_REGISTRY.values()
    ]

@router.get("/feature/{feature_name}", response_model=FeatureAccessResponse)
async def get_feature_access(feature_name: str, user_id: str = Depends(get_current_user)):

    try:
        feature = FeatureType(feature_name)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown feature:{feature_name}")
    
    has_access = await subscription_service.has_feature(user_id, feature)

    return {"feature": feature.value, "has_access": has_access}



