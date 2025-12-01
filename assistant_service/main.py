import datetime
import os
from typing import Dict, List, Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Column, Date, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./saas.db")
BILLING_SERVICE_URL = os.getenv("BILLING_SERVICE_URL", "http://localhost:8005")
DEFAULT_MONTH_WINDOW = int(os.getenv("ASSISTANT_MONTH_WINDOW", "3"))

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


class ChatRequest(BaseModel):
    user_id: int
    message: str
    context: Optional[str] = None
    months: int = Field(
        DEFAULT_MONTH_WINDOW,
        gt=0,
        description="Quantidade de meses de histórico a ser considerada",
    )


class ChatResponse(BaseModel):
    reply: str
    tokens_used: int
    transactions_context: Dict[str, object]


app = FastAPI(title="Assistant Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_db():
    Base.metadata.create_all(bind=engine)


@app.on_event("startup")
def startup_event():
    init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def build_transactions_context(transactions: List[Transaction]) -> Dict[str, object]:
    total_amount = sum(t.amount for t in transactions)
    monthly_totals: Dict[str, float] = {}
    details: List[Dict[str, object]] = []

    for tx in transactions:
        month_label = tx.transaction_date.strftime("%Y-%m")
        monthly_totals[month_label] = monthly_totals.get(month_label, 0.0) + tx.amount
        details.append(
            {
                "id": tx.id,
                "date": tx.transaction_date.isoformat(),
                "amount": tx.amount,
                "description": tx.description,
            }
        )

    return {
        "total_count": len(transactions),
        "total_amount": round(total_amount, 2),
        "monthly_totals": monthly_totals,
        "details": details,
    }


def draft_assistant_reply(message: str, context_summary: Dict[str, object]) -> str:
    lines = [
        "Usei suas transações recentes para responder:",
        f"- Total de transações: {context_summary['total_count']}",
        f"- Faturamento consolidado: R$ {context_summary['total_amount']:.2f}",
    ]

    if context_summary["monthly_totals"]:
        monthly_lines = ", ".join(
            f"{month}: R$ {amount:.2f}" for month, amount in context_summary["monthly_totals"].items()
        )
        lines.append(f"- Distribuição mensal: {monthly_lines}")

    lines.append("\nResposta:")
    lines.append(
        """Recebi sua mensagem e montei um parecer breve com base no histórico. "
        "Se precisar de cálculos específicos ou projeções, é só pedir!"""
    )
    lines.append(f"Mensagem original: {message}")

    return "\n".join(lines)


def estimate_token_usage(content: str) -> int:
    return max(1, len(content.split()))


def track_usage(user_id: int, tokens_used: int) -> None:
    payload = {"user_id": user_id, "tokens_used": tokens_used, "api_calls": 1}
    try:
        response = httpx.post(f"{BILLING_SERVICE_URL}/billing/track-usage", json=payload, timeout=5)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Erro ao registrar uso: {exc}") from exc


@app.post("/assistant/chat", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    month_cutoff = datetime.date.today().replace(day=1) - datetime.timedelta(days=30 * (request.months - 1))
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == request.user_id, Transaction.transaction_date >= month_cutoff)
        .order_by(Transaction.transaction_date.desc())
        .all()
    )

    context_summary = build_transactions_context(transactions)
    if request.context:
        context_summary["extra_context"] = request.context

    reply = draft_assistant_reply(request.message, context_summary)
    tokens_used = estimate_token_usage(reply)

    track_usage(user_id=request.user_id, tokens_used=tokens_used)

    return ChatResponse(
        reply=reply,
        tokens_used=tokens_used,
        transactions_context=context_summary,
    )
