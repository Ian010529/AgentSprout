from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import AgentTemplate, AudienceAge, ResponseLength, Role, Tone, VersionState


def clean_text(value: str) -> str:
    cleaned = value.strip()
    if any(unicodedata.category(char).startswith("C") and char not in "\n\r\t" for char in cleaned):
        raise ValueError("Control characters are not allowed")
    return cleaned


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AccessRequest(StrictModel):
    access_code: str = Field(min_length=1, max_length=256)


class SessionView(StrictModel):
    role: Role
    expires_at: datetime


class SessionResponse(StrictModel):
    session: SessionView
    csrf_token: str


class RoleUpdate(StrictModel):
    role: Role


class AgentFields(StrictModel):
    project_name: Annotated[str, Field(min_length=3, max_length=80)]
    problem_to_solve: Annotated[str, Field(min_length=10, max_length=500)]
    intended_users: Annotated[str, Field(min_length=3, max_length=240)]
    audience_age: AudienceAge
    success_goal: Annotated[str, Field(min_length=10, max_length=300)]
    welcome_message: Annotated[str, Field(min_length=3, max_length=240)]
    tone: Tone
    response_length: ResponseLength
    custom_instructions: Annotated[str, Field(max_length=500)] = ""

    @field_validator(
        "project_name",
        "problem_to_solve",
        "intended_users",
        "success_goal",
        "welcome_message",
        "custom_instructions",
    )
    @classmethod
    def validate_text(cls, value: str) -> str:
        return clean_text(value)


class AgentCreate(AgentFields):
    template: AgentTemplate


class AgentVersionPatch(StrictModel):
    project_name: Annotated[str | None, Field(min_length=3, max_length=80)] = None
    problem_to_solve: Annotated[str | None, Field(min_length=10, max_length=500)] = None
    intended_users: Annotated[str | None, Field(min_length=3, max_length=240)] = None
    audience_age: AudienceAge | None = None
    success_goal: Annotated[str | None, Field(min_length=10, max_length=300)] = None
    welcome_message: Annotated[str | None, Field(min_length=3, max_length=240)] = None
    tone: Tone | None = None
    response_length: ResponseLength | None = None
    custom_instructions: Annotated[str | None, Field(max_length=500)] = None

    @field_validator(
        "project_name",
        "problem_to_solve",
        "intended_users",
        "success_goal",
        "welcome_message",
        "custom_instructions",
    )
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return clean_text(value) if value is not None else None

    @model_validator(mode="after")
    def require_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Editable fields cannot be null")
        return self


class VersionSummary(StrictModel):
    id: str
    number: int
    state: VersionState
    knowledge_status: Literal["NOT_ADDED"] = "NOT_ADDED"


class AgentSummary(StrictModel):
    id: str
    display_name: str
    current_version: VersionSummary
    allowed_actions: list[str]
    next_action: str


class AgentListResponse(StrictModel):
    agents: list[AgentSummary]


class AgentAggregate(StrictModel):
    id: str
    display_name: str
    slug: str
    current_draft_version_id: str | None
    published_version_id: str | None
    versions: list[VersionSummary]
    allowed_actions: list[str]


class VersionDetail(AgentFields):
    id: str
    agent_id: str
    version_number: int
    state: VersionState
    active_document_id: str | None
    knowledge_status: Literal["NOT_ADDED"] = "NOT_ADDED"
    allowed_actions: list[str]
    created_at: datetime
    updated_at: datetime


class AgentCreateResponse(StrictModel):
    agent: AgentAggregate
    version: VersionDetail
