"""Pydantic schemas for chat endpoint."""

from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    attachments: list[str] = []
