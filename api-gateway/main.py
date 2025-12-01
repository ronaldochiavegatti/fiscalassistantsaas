import datetime
import os
from typing import Callable

import httpx
import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key")
LIMITS_SERVICE_URL = os.getenv("LIMITS_SERVICE_URL", "http://localhost:8003")

app = FastAPI(title="API Gateway", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"]
    ,
    allow_headers=["*"],
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next: Callable):
    # Allow unauthenticated access to landing resources
    if request.url.path.startswith("/public") or request.url.path in {"/health"}:
        return await call_next(request)

    authorization: str = request.headers.get("authorization")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    request.state.user_id = payload.get("sub")
    response = await call_next(request)
    response.headers["X-User-ID"] = str(payload.get("sub"))
    return response


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/dashboard")
def dashboard(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    fallback = {
        "user_id": user_id,
        "revenue_month": 0.0,
        "revenue_year": 0.0,
        "tax_due": 0.0,
        "documents_pending": 0,
        "alerts": ["Envie sua primeira nota fiscal para liberar o dashboard."],
    }

    try:
        current_year = datetime.datetime.utcnow().year
        response = httpx.get(
            f"{LIMITS_SERVICE_URL}/limits/summary",
            params={"year": current_year, "user_id": user_id},
            timeout=5,
        )
        response.raise_for_status()
        summary = response.json()

        revenue_month = summary.get("revenue_month", 0.0)
        revenue_year = summary.get("revenue_year", 0.0)
        limit_remaining = summary.get("limit_remaining", 0.0)

        return {
            "user_id": user_id,
            "revenue_month": revenue_month,
            "revenue_year": revenue_year,
            "tax_due": round(revenue_month * 0.08, 2),
            "documents_pending": 0,
            "alerts": [
                f"Limite restante MEI: R$ {limit_remaining:,.2f}",
                "Envie novas notas fiscais para manter a atualização em tempo real.",
            ],
        }
    except httpx.HTTPError:
        return fallback


@app.get("/profile")
def profile(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return {"user_id": user_id, "plan": "Pro"}
