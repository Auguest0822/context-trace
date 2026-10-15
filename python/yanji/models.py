"""Validated inputs for the conversation archive.

These models describe user supplied data. Database IDs and capture timestamps are
created by the storage layer, so callers cannot forge them in an import request.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class _StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MessageInput(_StrictInput):
    external_message_id: str | None = Field(default=None, max_length=512)
    sequence: int = Field(ge=0)
    role: Literal["user", "assistant", "system", "tool"]
    content: str = Field(min_length=1, max_length=50_000)
    sent_at: AwareDatetime | None = None

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message content cannot be blank")
        return value


class ConversationInput(_StrictInput):
    scope: str = Field(min_length=1, max_length=128)
    platform: Literal["deepseek", "kimi", "doubao", "agent", "other"]
    external_conversation_id: str | None = Field(default=None, max_length=512)
    title: str = Field(min_length=1, max_length=256)
    source_url: str | None = None
    capture_method: Literal["browser_extension", "agent_export", "manual_import"]
    capture_completeness: Literal["selected", "visible_page"]
    messages: list[MessageInput] = Field(min_length=1, max_length=100)
    client_request_id: UUID | None = None

    @field_validator("scope", "title")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value cannot be blank")
        return value

    @field_validator("source_url")
    @classmethod
    def http_url_or_none(cls, value: str | None) -> str | None:
        if value is not None:
            parts = urlsplit(value)
            if parts.scheme not in {"http", "https"} or not parts.netloc:
                raise ValueError("source_url must be an http(s) URL")
        return value

    @model_validator(mode="after")
    def messages_in_sequence_order(self) -> ConversationInput:
        sequences = [message.sequence for message in self.messages]
        if sequences != sorted(set(sequences)):
            raise ValueError("messages must have distinct, ascending sequence values")
        return self


class MessageAppendInput(_StrictInput):
    scope: str = Field(min_length=1, max_length=128)
    messages: list[MessageInput] = Field(min_length=1, max_length=100)
    client_request_id: UUID | None = None

    @field_validator("scope")
    @classmethod
    def scope_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("scope cannot be blank")
        return value

    @model_validator(mode="after")
    def messages_in_sequence_order(self) -> MessageAppendInput:
        sequences = [message.sequence for message in self.messages]
        if sequences != sorted(set(sequences)):
            raise ValueError("messages must have distinct, ascending sequence values")
        return self


def utc_database_time(value: datetime | None) -> datetime | None:
    """Convert an aware API timestamp to the naive UTC DATETIME stored by seekdb."""
    if value is None:
        return None
    from datetime import timezone

    return value.astimezone(timezone.utc).replace(tzinfo=None)
