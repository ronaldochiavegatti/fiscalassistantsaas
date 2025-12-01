import os
from typing import Callable

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key")

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

    # Fake data for now; the UI consumes this payload.
    return {
        "user_id": user_id,
        "revenue_month": 12500.0,
        "revenue_year": 74200.0,
        "tax_due": 1850.0,
        "documents_pending": 3,
        "alerts": [
            "Envie as notas fiscais do último trimestre.",
            "Valide o faturamento do mês passado para evitar multas.",
        ],
    }


@app.get("/profile")
def profile(request: Request):
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    return {"user_id": user_id, "plan": "Pro"}
