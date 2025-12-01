import datetime
import os

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Column, Date, DateTime, Float, Integer, String, create_engine, func
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./saas.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    document_id = Column(Integer, index=True)
    amount = Column(Float, nullable=False)
    transaction_date = Column(Date, nullable=False)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


app = FastAPI(title="Limits Service", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/limits/summary")
def limits_summary(
    year: int = Query(..., description="Ano de referência para o MEI"),
    user_id: int = Query(..., description="Identificador do usuário"),
    db: Session = Depends(get_db),
):
    today = datetime.date.today()
    month_start = datetime.date(year=year, month=today.month, day=1)
    next_month = (month_start.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)

    revenue_month = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= month_start,
            Transaction.transaction_date < next_month,
        )
        .scalar()
    )

    year_start = datetime.date(year=year, month=1, day=1)
    year_end = datetime.date(year=year + 1, month=1, day=1)

    revenue_year = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= year_start,
            Transaction.transaction_date < year_end,
        )
        .scalar()
    )

    limit_remaining = max(0, 81000 - revenue_year)

    return {
        "year": year,
        "month": month_start.month,
        "revenue_month": float(revenue_month),
        "revenue_year": float(revenue_year),
        "limit_remaining": float(limit_remaining),
    }
