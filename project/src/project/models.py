from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import UUID


class NotificationType(str, Enum):
    NEW_ASSIGNMENT = "new_assignment"
    DEADLINE_STUDENT = "deadline_student"
    DEADLINE_TEACHER = "deadline_teacher"
    ASSIGNMENT_CHECKED = "assignment_checked"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    VK = "vk"
    BOTH = "both"


class AssignmentNotification(BaseModel):
    assignment_id: UUID
    assignment_number: str
    assignment_description: Optional[str]
    deadline: str
    group_id: UUID
    subject_id: UUID
    subject_name: str


class DeadlineNotification(BaseModel):
    assignment_id: UUID
    assignment_number: str
    deadline: str
    student_id: UUID
    student_name: str
    student_email: EmailStr
    student_vk_id: Optional[str]
    group_name: str
    subject_name: str


class TeacherDeadlineNotification(BaseModel):
    assignment_id: UUID
    assignment_number: str
    deadline: str
    subject_name: str
    group_name: str
    students: List[Dict[str, Any]]


class CheckedAssignmentNotification(BaseModel):
    assignment_id: UUID
    assignment_number: str
    student_id: UUID
    student_name: str
    student_email: EmailStr
    student_vk_id: Optional[str]
    grade: Optional[str]
    feedback: Optional[str]
    checked_at: str


class UserPreference(BaseModel):
    user_id: UUID
    user_type: str
    email: EmailStr
    vk_id: Optional[str]
    notification_channel: NotificationChannel
    notifications_enabled: Dict[str, bool]