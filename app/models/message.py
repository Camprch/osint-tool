# app/models/message.py
from datetime import datetime
from sqlmodel import SQLModel, Field
from sqlalchemy import Index


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    telegram_message_id: int | None = Field(default=None, index=True)
    source: str = Field(index=True)
    channel: str | None = Field(default=None, index=True)

    raw_text: str
    translated_text: str | None = None

    country: str | None = Field(default=None, index=True)
    region: str | None = Field(default=None, index=True)
    location: str | None = Field(default=None, index=True)

    title: str | None = Field(default=None)
    event_timestamp: datetime | None = Field(default=None, index=True)

    orientation: str | None = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_message_country_created", "country", "created_at"),
    )
