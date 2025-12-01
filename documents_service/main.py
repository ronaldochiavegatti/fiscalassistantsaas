import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .database import SessionLocal, init_db
from .models import Document
from .worker import process_document

OBJECT_STORAGE_DIR = Path(os.getenv("OBJECT_STORAGE_DIR", "./storage"))

app = FastAPI(title="Documents Service", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db()
    OBJECT_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/documents/upload")
async def upload_document(
    user_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = file.filename or "uploaded_document"
    document = Document(
        user_id=user_id,
        filename=filename,
        storage_path="",
        status="pending",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    storage_path = OBJECT_STORAGE_DIR / f"{document.id}_{filename}"
    with open(storage_path, "wb") as f:
        f.write(await file.read())

    document.storage_path = str(storage_path)
    db.commit()

    try:
        process_document.apply_async(args=[document.id])
    except Exception:
        # If the broker is unavailable, process synchronously for demo purposes
        process_document(document.id)  # type: ignore[arg-type]

    return {"document_id": document.id, "status": document.status, "storage_path": document.storage_path}


@app.get("/documents/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "id": document.id,
        "user_id": document.user_id,
        "filename": document.filename,
        "status": document.status,
        "total_value": document.total_value,
        "transaction_date": document.transaction_date.isoformat() if document.transaction_date else None,
        "description": document.description,
    }
