from datetime import datetime, UTC
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Enum
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from backend.postgreSQL.engine import Base
from .enums import PlanType

class SubscriptionPlan(Base):

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        unique=True,
        index=True
    )

    plan: Mapped[PlanType] = mapped_column(
        Enum(PlanType),
        default=PlanType.FREE,
        nullable=False        
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="active",
        nullable=False
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default= lambda: datetime.now(UTC),
    ) 

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[datetime] =  mapped_column(
        DateTime(timezone=True),
        default= lambda: datetime.now(UTC)
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default= lambda: datetime.now(UTC),
        onupdate = lambda: datetime.now(UTC),
    )

    user = relationship(
        "User",
        back_populates="subscription"
    )





