# app/api/dates.py
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from datetime import date
from typing import List
from app.database import get_db
from app.models.message import Message
from .schemas import DatesResponse

router = APIRouter()

@router.get("/dates", response_model=DatesResponse)
def get_available_dates(session: Session = Depends(get_db)):
    """
    Renvoie les 10 dernières dates (sur created_at) où il y a des messages.
    """
    stmt = select(Message.created_at).order_by(Message.created_at.desc())
    rows = session.exec(stmt).all()

    seen = set()
    dates_list: List[date] = []
    for dt in rows:
        d = dt.date()
        if d not in seen:
            seen.add(d)
            dates_list.append(d)
        if len(dates_list) >= 10:
            break

    return DatesResponse(dates=dates_list)
