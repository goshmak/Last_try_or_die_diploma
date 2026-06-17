import enum
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

# === The four notification types mandated by the technical specification. ===
class NotificationType(str, enum.Enum):
    NEW_ASSIGNMENT = "new_assignment"
    DEADLINE_STUDENT = "deadline_student"
    DEADLINE_TEACHER = "deadline_teacher"
    REVIEW_RESULT = "review_result"

# === Lifecycle states of a notification task. ===
class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"

# === Notification ===
class ChannelType(str, enum.Enum):
    """Supported delivery channels."""
    EMAIL = "email"
    VK = "vk"
    ALL = "all"


# ---------------------------------------------------------------------------
# SQLAlchemy ORM base and ORM models
# ---------------------------------------------------------------------------

# === SQLAlchemy ORM ===
class Base(DeclarativeBase):
    pass

# === ORM model: NotificationRecord ===
# Persists every notification request and tracks its delivery lifecycle.
# One row per send attempt group (retries update the same row).
class NotificationRecord(Base):
    __tablename__ = "notification_records"

    task_id: str = Column(String(36), primary_key=True, index=True)
    notification_type: str = Column(
        SAEnum(NotificationType, name="notification_type_enum"), nullable=False
    )
    recipient_id: str = Column(String(128), nullable=False, index=True)
    channel: str = Column(
        SAEnum(ChannelType, name="channel_type_enum"), nullable=False
    )
    status: str = Column(
        SAEnum(NotificationStatus, name="notification_status_enum"),
        nullable=False,
        default=NotificationStatus.PENDING,
    )
    payload: dict = Column(JSON, nullable=True)
    attempt_count: int = Column(Integer, default=0, nullable=False)
    error_message: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at: Optional[datetime] = Column(DateTime, nullable=True)


# === ORM model: NotificationSettings ===
# Stores per-user channel preferences and contact identifiers.
# Retrieved during routing to determine where to deliver a notification.
class NotificationSettings(Base):
    __tablename__ = "notification_settings"

    recipient_id: str = Column(String(128), primary_key=True, index=True)
    email_enabled: bool = Column(Boolean, default=True, nullable=False)
    vk_enabled: bool = Column(Boolean, default=True, nullable=False)
    email_address: Optional[str] = Column(String(254), nullable=True)
    vk_user_id: Optional[str] = Column(String(64), nullable=True)


# ---------------------------------------------------------------------------
# Pydantic request schemas
# ---------------------------------------------------------------------------

# Assignment metadata fetched from (or passed by) the API Gateway.
# Used to populate notification templates.
class AssignmentData(BaseModel):
    assignment_id: str = Field(..., description="Unique assignment identifier")
    title: str = Field(..., description="Assignment title")
    topic: str = Field(..., description="Topic or subject area")
    deadline: Optional[str] = Field(None, description="ISO-8601 deadline string")
    grade: Optional[float] = Field(None, description="Grade awarded (for review notifications)")
    max_grade: Optional[float] = Field(None, description="Maximum possible grade")
    feedback: Optional[str] = Field(None, description="Instructor feedback text")

# Recipient data for student-targeted notifications.
class StudentData(BaseModel):
    full_name: str = Field(..., description="Student full name")
    group: str = Field(..., description="Academic group code, e.g. PI-201")
    course: int = Field(..., description="Year of study (1-6)")
    email: Optional[str] = Field(None, description="Student email address")
    vk_user_id: Optional[str] = Field(None, description="Student VK user ID")

# Recipient data for teacher-targeted notifications.
class TeacherData(BaseModel):
    full_name: str = Field(..., description="Instructor full name")
    email: Optional[str] = Field(None, description="Instructor email address")
    vk_user_id: Optional[str] = Field(None, description="Instructor VK user ID")

# Used in DEADLINE_TEACHER notifications to list submission statuses.
class SubmissionSummary(BaseModel):
    submitted: list[str] = Field(
        default_factory=list,
        description="Full names of students who submitted",
    )
    not_submitted: list[str] = Field(
        default_factory=list,
        description="Full names of students who have not submitted",
    )

# Top-level request schema sent to POST /notifications/send.
# The recipient_id is used as the stable external identifier passed
# from the API Gateway (e.g. a student UUID or teacher UUID).
class NotificationRequest(BaseModel):
    notification_type: NotificationType = Field(
        ..., description="Which of the four notification types to send"
    )
    recipient_id: str = Field(
        ..., description="Stable user ID from the main system (UUID or integer string)"
    )
    channel: ChannelType = Field(
        default=ChannelType.ALL,
        description="Target channel. Use 'all' to honour user preferences.",
    )
    assignment: AssignmentData = Field(..., description="Assignment context")
    student: Optional[StudentData] = Field(
        None, description="Required for student-targeted notification types"
    )
    teacher: Optional[TeacherData] = Field(
        None, description="Required for DEADLINE_TEACHER type"
    )
    submission_summary: Optional[SubmissionSummary] = Field(
        None, description="Required for DEADLINE_TEACHER type"
    )

    model_config = {"use_enum_values": True}


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------
class NotificationResponse(BaseModel):
    task_id: str
    status: NotificationStatus
    message: str


class StatusResponse(BaseModel):
    task_id: str
    status: NotificationStatus
    channel: ChannelType
    created_at: datetime
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    attempt_count: int


class NotificationHistoryItem(BaseModel):
    task_id: str
    notification_type: NotificationType
    recipient_id: str
    channel: ChannelType
    status: NotificationStatus
    created_at: datetime
    sent_at: Optional[datetime] = None
    attempt_count: int


class SettingsUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    vk_enabled: Optional[bool] = None
    email_address: Optional[str] = None
    vk_user_id: Optional[str] = None


class SettingsResponse(BaseModel):
    recipient_id: str
    email_enabled: bool
    vk_enabled: bool
    email_address: Optional[str] = None
    vk_user_id: Optional[str] = None
