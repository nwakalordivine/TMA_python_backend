"""
SQLAlchemy ORM models for the Task Management & Authentication service.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TaskStatus(str, enum.Enum):
    OPEN = "Open"
    CLOSED = "Closed"


class AssignmentStatus(str, enum.Enum):
    CLAIMED = "Claimed"
    STARTED = "Started"
    COMPLETED = "Completed"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    skills: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    interests: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reputation: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    assignments = relationship("TaskAssignment", back_populates="user", cascade="all, delete-orphan")
    points_logs = relationship("PointsLog", back_populates="user", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_skills: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    max_assignees: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_assignees: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    point_value: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, values_callable=lambda e: [m.value for m in e]),
        default=TaskStatus.OPEN,
        nullable=False,
    )

    # Relationships
    assignments = relationship("TaskAssignment", back_populates="task", cascade="all, delete-orphan")
    points_logs = relationship("PointsLog", back_populates="task", cascade="all, delete-orphan")


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, values_callable=lambda e: [m.value for m in e]),
        default=AssignmentStatus.CLAIMED,
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)

    # Relationships
    user = relationship("User", back_populates="assignments")
    task = relationship("Task", back_populates="assignments")


class PointsLog(Base):
    __tablename__ = "points_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="points_logs")
    task = relationship("Task", back_populates="points_logs")
