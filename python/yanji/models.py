"""Validated inputs for the conversation archive.

These models describe user supplied data. Database IDs and capture timestamps are
created by the storage layer, so callers cannot forge them in an import request.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

RecordId = Annotated[str, Field(pattern=r"^[1-9][0-9]*$")]
MemoryKind = Literal["decision", "constraint", "fact", "preference", "skill"]


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


class ExtractionPreviewInput(_StrictInput):
    scope: str = Field(min_length=1, max_length=128)
    conversation_id: RecordId
    message_ids: list[RecordId] = Field(min_length=1, max_length=20)
    mode: Literal["manual"] = "manual"

    @field_validator("scope")
    @classmethod
    def nonblank_scope(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("scope cannot be blank")
        return value

    @field_validator("message_ids")
    @classmethod
    def distinct_message_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("message_ids must be distinct")
        return value


class SelectedMemoryInput(_StrictInput):
    candidate_id: UUID
    kind: MemoryKind
    content: str = Field(min_length=1, max_length=8_000)
    summary: str | None = Field(default=None, max_length=512)

    @field_validator("content")
    @classmethod
    def nonblank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("memory content cannot be blank")
        return value


class ExtractionCommitInput(_StrictInput):
    scope: str = Field(min_length=1, max_length=128)
    selected: list[SelectedMemoryInput] = Field(max_length=20)
    client_request_id: UUID

    @field_validator("scope")
    @classmethod
    def nonblank_scope(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("scope cannot be blank")
        return value

    @field_validator("selected")
    @classmethod
    def distinct_candidates(cls, value: list[SelectedMemoryInput]) -> list[SelectedMemoryInput]:
        ids = [item.candidate_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate_id must be distinct")
        return value


class MemorySearchFilters(_StrictInput):
    platforms: list[Literal["deepseek", "kimi", "doubao", "agent", "other"]] | None = None
    conversation_ids: list[RecordId] | None = Field(default=None, max_length=20)
    kinds: list[MemoryKind] | None = None
    created_from: AwareDatetime | None = None
    created_to: AwareDatetime | None = None

    @field_validator("platforms", "conversation_ids", "kinds")
    @classmethod
    def nonempty_distinct(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (not value or len(value) != len(set(value))):
            raise ValueError("filter arrays must be nonempty and distinct")
        return value

    @model_validator(mode="after")
    def valid_date_range(self) -> MemorySearchFilters:
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError("created_from cannot be later than created_to")
        return self


class MemorySearchInput(_StrictInput):
    scope: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=4_000)
    mode: Literal["keyword", "vector", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)
    budget_tokens: int = Field(default=1200, ge=100, le=8192)
    filters: MemorySearchFilters = Field(default_factory=MemorySearchFilters)

    @field_validator("scope", "query")
    @classmethod
    def nonblank_search_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("scope and query cannot be blank")
        return value


class MemoryWriteInput(_StrictInput):
    scope: str = Field(min_length=1, max_length=128)
    kind: MemoryKind
    content: str = Field(min_length=1, max_length=8_000)
    summary: str | None = Field(default=None, max_length=512)
    importance: float = Field(default=0.5, ge=0, le=1)
    source_type: Literal["chat", "doc", "git", "issue", "manual"]
    source_ref: str | None = Field(default=None, max_length=512)
    source_excerpt: str = Field(min_length=1, max_length=1_000)
    conversation_id: RecordId | None = None
    source_message_ids: list[RecordId] | None = Field(default=None, max_length=20)
    valid_from: AwareDatetime | None = None
    valid_to: AwareDatetime | None = None
    client_request_id: UUID | None = None

    @field_validator("scope", "content", "source_excerpt")
    @classmethod
    def nonblank_write_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required text cannot be blank")
        return value

    @model_validator(mode="after")
    def source_is_consistent(self) -> MemoryWriteInput:
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_to cannot be earlier than valid_from")
        if self.source_type == "chat":
            if self.source_ref is not None or not self.conversation_id or not self.source_message_ids:
                raise ValueError("chat source needs conversation and messages, without source_ref")
            if len(self.source_message_ids) != len(set(self.source_message_ids)):
                raise ValueError("source_message_ids must be distinct")
        elif not self.source_ref or not self.source_ref.strip():
            raise ValueError("non-chat source needs source_ref")
        elif self.conversation_id is not None or self.source_message_ids is not None:
            raise ValueError("non-chat source cannot cite archived message IDs")
        return self


class MemoryContextInput(_StrictInput):
    scope: str = Field(min_length=1, max_length=128)
    memory_ids: list[RecordId] = Field(max_length=20)
    budget_tokens: int = Field(default=1200, ge=100, le=8192)

    @field_validator("scope")
    @classmethod
    def nonblank_context_scope(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("scope cannot be blank")
        return value

    @field_validator("memory_ids")
    @classmethod
    def distinct_context_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("memory_ids must be distinct")
        return value


class MemoryReconcileInput(_StrictInput):
    scope: str = Field(min_length=1, max_length=128)
    old_memory_id: RecordId
    new_memory: dict
    reason: str = Field(min_length=1, max_length=500)
    client_request_id: UUID

    @model_validator(mode="after")
    def valid_replacement(self) -> MemoryReconcileInput:
        if not self.scope.strip() or not self.reason.strip():
            raise ValueError("scope and reason cannot be blank")
        if "scope" in self.new_memory or "client_request_id" in self.new_memory:
            raise ValueError("replacement scope and request ID belong to the outer request")
        MemoryWriteInput.model_validate({"scope": self.scope, **self.new_memory})
        return self


class MemoryHandoffInput(_StrictInput):
    scope: str = Field(min_length=1, max_length=128)
    objective: str = Field(min_length=1, max_length=4_000)
    budget_tokens: int = Field(default=1200, ge=100, le=8192)
    filters: MemorySearchFilters = Field(default_factory=MemorySearchFilters)

    @field_validator("scope", "objective")
    @classmethod
    def nonblank_handoff_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("scope and objective cannot be blank")
        return value


def utc_database_time(value: datetime | None) -> datetime | None:
    """Convert an aware API timestamp to the naive UTC DATETIME stored by seekdb."""
    if value is None:
        return None

    return value.astimezone(UTC).replace(tzinfo=None)
