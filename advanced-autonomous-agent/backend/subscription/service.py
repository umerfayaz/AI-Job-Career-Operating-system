from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from sqlalchemy import select
from datetime import datetime, UTC
from backend.postgreSQL.engine import AsyncSessionLocal
from .models import SubscriptionPlan
from .plans import PLAN_REGISTRY, PlanConfig
from .enums import FeatureType, PlanType
from .usage import UsageService


class SubscriptionService:

    async def get_subscription(self, user_id:str) -> SubscriptionPlan | None:

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SubscriptionPlan).where(
                    SubscriptionPlan.user_id == user_id
                )
            )

            return result.scalar_one_or_none()

    async def create_free_subscription(self, user_id: str) -> SubscriptionPlan:

        existing = await self.get_subscription(user_id)

        if existing:
            return existing
        
        subscription = SubscriptionPlan(
            user_id=user_id,
            plan=PlanType.FREE,
            status = "active"
        )

        async with AsyncSessionLocal() as session:
            session.add(subscription)

            try:
                await session.commit()
                await session.refresh(subscription)
            except IntegrityError:
                await session.rollback()
                return await self.get_subscription(user_id)

        return subscription


    async def get_plan(self, user_id: str) -> PlanConfig:
        subscription = await self.get_subscription(user_id)

        if subscription is None:
            subscription = await self.create_free_subscription(user_id)
        
        if (subscription.expires_at and subscription.expires_at < datetime.now(UTC)
            and subscription.plan != PlanType.FREE
        ):
            subscription.plan = PlanType.FREE
            subscription.status = "expired"

            async with AsyncSessionLocal() as session:
                subscription = await session.merge(subscription)
                await session.commit()
                await session.refresh(subscription)

        return PLAN_REGISTRY[
            PlanType(subscription.plan)
        ]
    
    async def authorize_frontend_workflow(self, user_id:str) -> dict:

        plan = await self.get_plan(user_id)

        usage = await UsageService.check_daily_workflow_limit(
            user_id=user_id,
            daily_limit=plan.daily_frontend_runs,
            workflow_type="frontend"
        )

        return {
            "authorized": True,
            "plan": plan.id.value,
            **usage
        }
    
    async def authorize_autonomous_workflow(self, user_id: str) -> dict:
        plan = await self.get_plan(user_id)

        if FeatureType.AUTONOMOUS_WORKFLOW not in plan.features:
            raise HTTPException(
                status_code=403,
                detail= {"error": "required_subscription",
                    "required_plan": PlanType.AUTONOMOUS.value,
                    "message": "Autonomous workflow required an Autonomous AI subscription",
                }
            )
        
        return {
            "authorized": True,
            "plan": plan.id.value
        }

    async def has_feature(self, user_id:str, feature:FeatureType) -> bool:
        plan = await self.get_plan(user_id)

        return feature in plan.features
    
    async def get_dashboard_usage(self, user_id: str) -> dict:
        plan = await self.get_plan(user_id)
        subscription = await self.get_subscription(user_id)

        if subscription is None:
            subscription = await self.create_free_subscription(user_id)
        
        plan = PLAN_REGISTRY[
            PlanType(subscription.plan)
        ]

        used = await UsageService.get_usage(
            user_id=user_id,
            workflow_type="frontend"
        )
        return {
            "plan": subscription.plan.value,
            "status": subscription.status,
            "used": used,
            "daily_limit": plan.daily_frontend_runs,
            "remaining": (
                -1 if plan.daily_frontend_runs == -1 
                else max(0 ,plan.daily_frontend_runs - used)
            ),
            "autonomous_enabled": (FeatureType.AUTONOMOUS_WORKFLOW in plan.features),
            "expires_at": subscription.expires_at
        }



     






