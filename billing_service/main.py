import datetime
import os
from typing import Optional

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, create_engine, func
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./saas.db")
DEFAULT_PLAN_NAME = os.getenv("DEFAULT_PLAN_NAME", "Free")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    token_limit = Column(Integer, default=5000)
    monthly_price = Column(Float, default=0.0)


class Usage(Base):
    __tablename__ = "usages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    period_start = Column(Date, index=True, nullable=False)
    tokens_used = Column(Integer, default=0)
    uploads = Column(Integer, default=0)
    api_calls = Column(Integer, default=0)

    plan = relationship("Plan")


class TrackUsageRequest(BaseModel):
    user_id: int
    tokens_used: int = 0
    uploads: int = 0
    api_calls: int = 0
    plan_name: Optional[str] = None


class UsageResponse(BaseModel):
    plan: dict
    usage: dict


app = FastAPI(title="Billing Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if not db.query(Plan).count():
            plans = [
                Plan(name="Free", token_limit=5000, monthly_price=0.0),
                Plan(name="Pro", token_limit=50000, monthly_price=79.9),
            ]
            db.add_all(plans)
            db.commit()


@app.on_event("startup")
def startup_event():
    init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_or_create_usage(db: Session, user_id: int, plan: Plan, period_start: datetime.date) -> Usage:
    usage = (
        db.query(Usage)
        .filter(
            Usage.user_id == user_id,
            Usage.plan_id == plan.id,
            Usage.period_start == period_start,
        )
        .first()
    )
    if not usage:
        usage = Usage(
            user_id=user_id,
            plan_id=plan.id,
            period_start=period_start,
        )
        db.add(usage)
        db.commit()
        db.refresh(usage)
    return usage


def resolve_plan(db: Session, plan_name: Optional[str]) -> Plan:
    name = plan_name or DEFAULT_PLAN_NAME
    plan = db.query(Plan).filter(func.lower(Plan.name) == name.lower()).first()
    if not plan:
        plan = db.query(Plan).filter(func.lower(Plan.name) == DEFAULT_PLAN_NAME.lower()).first()
    return plan


@app.post("/billing/track-usage", response_model=UsageResponse)
def track_usage(payload: TrackUsageRequest, db: Session = Depends(get_db)):
    plan = resolve_plan(db, payload.plan_name)
    today = datetime.date.today()
    period_start = datetime.date(today.year, today.month, 1)

    usage = get_or_create_usage(db, payload.user_id, plan, period_start)
    usage.tokens_used += payload.tokens_used
    usage.uploads += payload.uploads
    usage.api_calls += payload.api_calls
    db.commit()
    db.refresh(usage)

    return UsageResponse(
        plan={
            "name": plan.name,
            "token_limit": plan.token_limit,
            "monthly_price": plan.monthly_price,
        },
        usage={
            "period_start": usage.period_start.isoformat(),
            "tokens_used": usage.tokens_used,
            "uploads": usage.uploads,
            "api_calls": usage.api_calls,
            "remaining_tokens": max(plan.token_limit - usage.tokens_used, 0),
        },
    )


@app.get("/billing/me", response_model=UsageResponse)
def billing_me(user_id: int, db: Session = Depends(get_db)):
    plan = resolve_plan(db, None)
    today = datetime.date.today()
    period_start = datetime.date(today.year, today.month, 1)
    usage = get_or_create_usage(db, user_id, plan, period_start)

    return UsageResponse(
        plan={
            "name": plan.name,
            "token_limit": plan.token_limit,
            "monthly_price": plan.monthly_price,
        },
        usage={
            "period_start": usage.period_start.isoformat(),
            "tokens_used": usage.tokens_used,
            "uploads": usage.uploads,
            "api_calls": usage.api_calls,
            "remaining_tokens": max(plan.token_limit - usage.tokens_used, 0),
        },
    )
