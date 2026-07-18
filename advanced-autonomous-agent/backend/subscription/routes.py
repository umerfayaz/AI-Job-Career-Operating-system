from fastapi import APIRouter, Depends, HTTPException
from backend.auth.auth_routes import get_current_user
from .service import SubscriptionService
from .plans import PLAN_REGISTRY
from .enums import FeatureType, PlanType


router = APIRouter(prefix="api/subscription", tags=["subscription"])
subscription_service = SubscriptionService()



@router.get("/usage")
async def get_usage(user_id: str = Depends(get_current_user)):
    return await subscription_service.get_dashboard_usage(user_id)


@router.get("/plan")
async def get_curren_plan(user_id: str = Depends(get_current_user)):
    plan = await subscription_service.get_plan(user_id)

    return {
        "plan": plan.id,
        "display_name": plan.display_name,
        "daily_frontend_runs": plan.daily_frontend_runs,
        "features": sorted([f.value for f in plan.features])
    }

@router.get("/plans")
async def list_all_plans():
    return [
        {
            "id": p.id,
            "display_name": p.diplay_name,
            "daily_frontend_runs": p.daily_frontend_runs,
            "features": sorted([f.value for f in p.features]),
        }
        for p in PLAN_REGISTRY.values()
    ]

@router.get(f"/feature/{feature_name}")
async def get_feature_access(feature_name: str, user_id: str = Depends(get_current_user)):

    try:
        feature = FeatureType(feature_name)
    except ValueError:
        HTTPException(status_code=400, detail=f"Unknown feature:{feature_name}")
    
    has_access = await subscription_service.has_features(user_id, feature)

    return {"features": feature, "has_access": has_access}

    

