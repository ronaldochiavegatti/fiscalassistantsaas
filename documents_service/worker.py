import datetime
import json
import os
import re
from typing import Tuple

from celery import Celery

from .database import SessionLocal, init_db
from .models import Document, Event, Transaction

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

celery_app = Celery("documents_worker", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)


def _stub_ocr_extract(file_path: str, filename: str) -> Tuple[float, datetime.date, str]:
    """
    Minimal OCR stub. It inspects the file content (text) to find an amount and date, otherwise
    falls back to sensible defaults for demo purposes.
    """
    amount = 0.0
    description = os.path.splitext(filename)[0]
    today = datetime.date.today()

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except FileNotFoundError:
        return 0.0, today, description

    # Try to find a number that looks like a currency value
    amount_match = re.search(r"(\d+[.,]\d{2})", content)
    if amount_match:
        amount = float(amount_match.group(1).replace(",", "."))
    else:
        amount = 100.0  # default stub value

    # Try to parse a date in YYYY-MM-DD or DD/MM/YYYY formats
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", content)
    if date_match:
        parsed_date = datetime.datetime.strptime(date_match.group(1), "%Y-%m-%d").date()
    else:
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", content)
        if date_match:
            parsed_date = datetime.datetime.strptime(date_match.group(1), "%d/%m/%Y").date()
        else:
            parsed_date = today

    first_line = content.strip().splitlines()[0] if content.strip().splitlines() else description
    description = first_line[:140] if first_line else description

    return amount, parsed_date, description


@celery_app.task(name="documents.process_document")
def process_document(document_id: int):
    init_db()
    session = SessionLocal()

    try:
        document = session.query(Document).filter(Document.id == document_id).first()
        if not document:
            return

        document.status = "processing"
        session.commit()

        amount, transaction_date, description = _stub_ocr_extract(document.storage_path, document.filename)

        document.total_value = amount
        document.transaction_date = transaction_date
        document.description = description
        document.processed_at = datetime.datetime.utcnow()
        document.status = "completed"

        transaction = session.query(Transaction).filter(Transaction.document_id == document.id).first()
        if transaction:
            transaction.amount = amount
            transaction.transaction_date = transaction_date
            transaction.description = description
        else:
            transaction = Transaction(
                user_id=document.user_id,
                document_id=document.id,
                amount=amount,
                transaction_date=transaction_date,
                description=description,
            )
            session.add(transaction)

        event = Event(
            event_type="document_processed",
            payload=json.dumps(
                {
                    "document_id": document.id,
                    "user_id": document.user_id,
                    "amount": amount,
                    "transaction_date": transaction_date.isoformat(),
                }
            ),
        )
        session.add(event)

        session.commit()
    finally:
        session.close()
