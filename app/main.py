"""
FastAPI application — Auth, User, and Task routes.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import create_tables, get_db
from app.models import (
    AssignmentStatus,
    PointsLog,
    Task,
    TaskAssignment,
    TaskStatus,
    User,
)
from app.schemas import (
    LeaderboardEntry,
    PointsLogResponse,
    TaskAssignmentResponse,
    TaskCreate,
    TaskResponse,
    Token,
    TokenVerifyRequest,
    TokenVerifyResponse,
    UserCreate,
    UserLogin,
    UserProfileUpdate,
    UserResponse,
)

# ---------------------------------------------------------------------------
# Lifespan — create tables on startup (dev convenience)
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title="Task Management & Authentication API",
    description="Core backend for user identity, task management, and point tracking.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for development; tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════════════════
# AUTH ROUTES  /auth
# ═══════════════════════════════════════════════════════════════════════════


@app.post("/auth/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    # Check for duplicate username or email
    existing = await db.execute(
        select(User).where((User.username == payload.username) | (User.email == payload.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username or email already registered")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@app.post("/auth/login", response_model=Token)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate and return a JWT access token."""
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"user_id": user.id, "username": user.username})
    return Token(access_token=token)


@app.post("/auth/verify", response_model=TokenVerifyResponse)
async def verify_token(payload: TokenVerifyRequest):
    """Validate a JWT — designed for cross-service calls (e.g. Node.js)."""
    try:
        data = decode_access_token(payload.token)
        return TokenVerifyResponse(valid=True, user_id=data.get("user_id"), username=data.get("username"))
    except JWTError:
        return TokenVerifyResponse(valid=False)


# ═══════════════════════════════════════════════════════════════════════════
# USER ROUTES  /users
# ═══════════════════════════════════════════════════════════════════════════


@app.get("/users/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile."""
    return current_user


@app.post("/users/profile", response_model=UserResponse)
async def update_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update skills, interests, and/or bio for the authenticated user."""
    if payload.skills is not None:
        current_user.skills = payload.skills
    if payload.interests is not None:
        current_user.interests = payload.interests
    if payload.bio is not None:
        current_user.bio = payload.bio

    db.add(current_user)
    await db.flush()
    await db.refresh(current_user)
    return current_user


@app.get("/users/leaderboard", response_model=list[LeaderboardEntry])
async def leaderboard(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Return users ranked by points (descending). Public endpoint."""
    result = await db.execute(select(User).order_by(User.points.desc()).limit(limit))
    return result.scalars().all()


# ═══════════════════════════════════════════════════════════════════════════
# TASK ROUTES  /tasks
# ═══════════════════════════════════════════════════════════════════════════


@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new task."""
    task = Task(
        title=payload.title,
        description=payload.description,
        required_skills=payload.required_skills,
        max_assignees=payload.max_assignees,
        point_value=payload.point_value,
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)
    return task


@app.get("/tasks", response_model=list[TaskResponse])
async def list_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all available (open) tasks."""
    result = await db.execute(select(Task).where(Task.status == TaskStatus.OPEN).order_by(Task.id.desc()))
    return result.scalars().all()


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve detailed information for a specific task."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@app.post("/tasks/{task_id}/claim", response_model=TaskAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def claim_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Claim a task.

    Uses SELECT ... FOR UPDATE to lock the task row and prevent
    over-assignment under concurrent requests.
    """
    # Lock the task row for this transaction
    result = await db.execute(
        select(Task).where(Task.id == task_id).with_for_update()
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if task.status != TaskStatus.OPEN:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task is not open")

    if task.current_assignees >= task.max_assignees:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task has reached maximum assignees")

    # Check if user already has an active assignment for this task
    existing = await db.execute(
        select(TaskAssignment).where(
            TaskAssignment.user_id == current_user.id,
            TaskAssignment.task_id == task_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already claimed this task")

    # Create assignment and increment counter atomically
    assignment = TaskAssignment(user_id=current_user.id, task_id=task_id)
    task.current_assignees += 1
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return assignment


@app.post("/tasks/{task_id}/start", response_model=TaskAssignmentResponse)
async def start_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the user's assignment status for this task to 'Started'."""
    result = await db.execute(
        select(TaskAssignment).where(
            TaskAssignment.user_id == current_user.id,
            TaskAssignment.task_id == task_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found — claim the task first")

    if assignment.status != AssignmentStatus.CLAIMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start — assignment status is '{assignment.status.value}'",
        )

    assignment.status = AssignmentStatus.STARTED
    await db.flush()
    await db.refresh(assignment)
    return assignment


@app.post("/tasks/{task_id}/complete", response_model=TaskAssignmentResponse)
async def complete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the user's assignment status for this task to 'Completed'."""
    result = await db.execute(
        select(TaskAssignment).where(
            TaskAssignment.user_id == current_user.id,
            TaskAssignment.task_id == task_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment.status != AssignmentStatus.STARTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete — assignment status is '{assignment.status.value}'",
        )

    assignment.status = AssignmentStatus.COMPLETED
    assignment.completed_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(assignment)
    return assignment


@app.post("/tasks/{task_id}/award-points", response_model=PointsLogResponse, status_code=status.HTTP_201_CREATED)
async def award_points(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Award points for a completed task assignment.

    - Validates the assignment is in 'Completed' status.
    - Ensures points are not awarded twice (idempotent).
    - Credits the task's point_value to the user and logs the transaction.
    """
    # Verify a completed assignment exists
    result = await db.execute(
        select(TaskAssignment).where(
            TaskAssignment.user_id == current_user.id,
            TaskAssignment.task_id == task_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if assignment.status != AssignmentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Points can only be awarded for completed assignments",
        )

    # Idempotency check — don't award twice
    existing_log = await db.execute(
        select(PointsLog).where(
            PointsLog.user_id == current_user.id,
            PointsLog.task_id == task_id,
        )
    )
    if existing_log.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Points already awarded for this task")

    # Fetch task to get point_value
    task_result = await db.execute(select(Task).where(Task.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Credit points and create audit log entry
    current_user.points += task.point_value
    log_entry = PointsLog(
        user_id=current_user.id,
        task_id=task_id,
        amount=task.point_value,
        reason=f"Completed task: {task.title}",
    )
    db.add(current_user)
    db.add(log_entry)
    await db.flush()
    await db.refresh(log_entry)
    return log_entry
