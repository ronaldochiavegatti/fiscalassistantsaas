import os
import datetime
from typing import Optional

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./auth.db")
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    email: EmailStr
    password: str


app = FastAPI(title="Auth Service", version="0.1.0")


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


def create_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_token(subject: str, token_type: str, expires_delta: datetime.timedelta) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    if payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    return payload


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    payload = decode_token(token, expected_type="access")
    return int(payload.get("sub"))


@app.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db=Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    new_user = User(email=user.email, password_hash=create_password_hash(user.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_token(str(new_user.id), "access", datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_token(str(new_user.id), "refresh", datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

    return Token(access_token=access_token, refresh_token=refresh_token)


@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_token(str(user.id), "access", datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_token(str(user.id), "refresh", datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

    return Token(access_token=access_token, refresh_token=refresh_token)


class RefreshRequest(BaseModel):
    refresh_token: str


@app.post("/refresh", response_model=Token)
def refresh(request: RefreshRequest, db=Depends(get_db)):
    payload = decode_token(request.refresh_token, expected_type="refresh")
    user_id = payload.get("sub")

    # ensure user still exists
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access_token = create_token(str(user.id), "access", datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_token(str(user.id), "refresh", datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

    return Token(access_token=access_token, refresh_token=refresh_token)


@app.get("/me")
def read_me(user_id: int = Depends(get_current_user_id)):
    return {"user_id": user_id}
