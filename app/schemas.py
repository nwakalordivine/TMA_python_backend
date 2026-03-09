"""
Pydantic v2 schemas for request/response validation.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int | None = None
    username: str | None = None


class TokenVerifyRequest(BaseModel):
    token: str


class TokenVerifyResponse(BaseModel):
    valid: bool
    user_id: int | None = None
    username: str | None = None


# ---------------------------------------------------------------------------
# User schemas
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    bio: str | None = None
    skills: list | None = []
    interests: list | None = []
    points: int = 0
    reputation: float = 0.0


class UserProfileUpdate(BaseModel):
    skills: list[str] | None = None
    interests: list[str] | None = None
    bio: str | None = None


class LeaderboardEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    points: int
    reputation: float


# ---------------------------------------------------------------------------
# Task schemas
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    required_skills: list[str] | None = []
    max_assignees: int = Field(1, ge=1)
    point_value: int = Field(0, ge=0)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    required_skills: list | None = []
    max_assignees: int
    current_assignees: int
    point_value: int
    status: str


class TaskAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    task_id: int
    status: str
    assigned_at: datetime
    completed_at: datetime | None = None


class PointsLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    task_id: int
    amount: int
    reason: str | None = None
    timestamp: datetime
