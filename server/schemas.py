from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    error: str


class RoleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    created_at: str


class MemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    email: str
    created_at: str


class RoleMemberSkipResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    activity_id: int
    role_id: int
    member_id: int
    created_at: str


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    activity_id: int
    role_id: int
    member_id: int
    assigned_on: str
    created_at: str


class ActivityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    created_at: str
    roles: list[RoleResponse] = Field(default_factory=list)
    members: list[MemberResponse] = Field(default_factory=list)
    assignments: list[AssignmentResponse] = Field(default_factory=list)
    role_member_skips: list[RoleMemberSkipResponse] = Field(default_factory=list)


class ActivitiesResponse(BaseModel):
    activities: list[ActivityResponse]


class AssignmentsResponse(BaseModel):
    assignments: list[AssignmentResponse]
