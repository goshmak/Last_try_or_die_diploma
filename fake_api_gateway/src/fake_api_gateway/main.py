import asyncio
import httpx
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from enum import Enum
import uvicorn

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Конфигурация
NOTIFICATION_SERVICE_URL = "http://localhost:8002"  # URL вашего сервиса уведомлений


# Модели данных
class NotificationType(str, Enum):
    NEW_ASSIGNMENT = "new_assignment"
    DEADLINE_STUDENT = "deadline_student"
    DEADLINE_TEACHER = "deadline_teacher"
    ASSIGNMENT_CHECKED = "assignment_checked"


class UserType(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"


# Модели для тестовых данных
class TestAssignment(BaseModel):
    assignment_id: int
    assignment_number: str
    assignment_description: Optional[str] = None
    deadline: str
    subject_name: str
    group_name: str


class TestStudent(BaseModel):
    student_id: int
    student_name: str
    email: EmailStr
    telegram_id: Optional[str] = None
    group_name: str


class TestTeacher(BaseModel):
    teacher_id: int
    teacher_name: str
    email: EmailStr
    telegram_id: Optional[str] = None
    subject_name: str


# Создание FastAPI приложения для фейкового Gateway
app = FastAPI(
    title="Fake API Gateway", description="Для тестирования Notification Service"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Тестовые данные
TEST_STUDENTS = {
    1: TestStudent(
        student_id=1,
        student_name="Иван Петров",
        email="ivan@example.com",
        telegram_id="123456789",
        group_name="Группа А-101",
    ),
    2: TestStudent(
        student_id=2,
        student_name="Мария Сидорова",
        email="maria@example.com",
        telegram_id="987654321",
        group_name="Группа А-101",
    ),
    3: TestStudent(
        student_id=3,
        student_name="Алексей Иванов",
        email="alexey@example.com",
        telegram_id=None,
        group_name="Группа Б-202",
    ),
}

TEST_TEACHERS = {
    1: TestTeacher(
        teacher_id=1,
        teacher_name="Елена Васильевна",
        email="elena@school.com",
        telegram_id="111222333",
        subject_name="Математика",
    ),
    2: TestTeacher(
        teacher_id=2,
        teacher_name="Сергей Николаевич",
        email="sergey@school.com",
        telegram_id="444555666",
        subject_name="Физика",
    ),
}


# HTTP клиент для отправки запросов к Notification Service
class NotificationServiceClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def send_notification(
        self,
        user_id: int,
        user_type: str,
        notification_type: str,
        content_data: Dict[str, Any],
    ):
        """Отправка уведомления через Notification Service"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/notifications/send",
                params={
                    "user_id": user_id,
                    "user_type": user_type,
                    "notification_type": notification_type,
                },
                json=content_data,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            raise

    async def update_preferences(
        self,
        user_id: int,
        user_type: str,
        email: str,
        notification_channel: str,
        notifications_enabled: Dict[str, bool],
        telegram_id: Optional[str] = None,
    ):
        """Обновление настроек уведомлений"""
        try:
            data = {
                "user_id": user_id,
                "user_type": user_type,
                "email": email,
                "telegram_id": telegram_id,
                "notification_channel": notification_channel,
                "notifications_enabled": notifications_enabled,
            }
            response = await self.client.post(
                f"{self.base_url}/api/notifications/preferences", json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            raise

    async def get_notification_history(self, user_id: int, limit: int = 50):
        """Получение истории уведомлений"""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/notifications/history/{user_id}",
                params={"limit": limit},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            raise

    async def get_stats(self):
        """Получение статистики"""
        try:
            response = await self.client.get(f"{self.base_url}/api/notifications/stats")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            raise

    async def health_check(self):
        """Проверка здоровья сервиса уведомлений"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return response.json()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def close(self):
        await self.client.aclose()


# Инициализация клиента
notification_client = NotificationServiceClient(NOTIFICATION_SERVICE_URL)

# API эндпоинты фейкового Gateway


@app.on_event("startup")
async def startup_event():
    """Проверка связи с Notification Service при запуске"""
    logger.info("Starting Fake API Gateway...")
    health = await notification_client.health_check()
    if health.get("status") == "healthy":
        logger.info(f"Notification Service is healthy")
    else:
        logger.warning(f"Notification Service health check failed: {health}")


@app.on_event("shutdown")
async def shutdown_event():
    await notification_client.close()


# Эндпоинты для имитации бизнес-логики


@app.post("/api/assignments/create")
async def create_assignment(assignment: TestAssignment):
    """
    Имитация создания нового задания.
    Отправляет уведомления всем студентам группы.
    """
    logger.info(f"Creating new assignment: {assignment.assignment_number}")

    # Находим студентов в этой группе
    students_in_group = [
        s for s in TEST_STUDENTS.values() if s.group_name == assignment.group_name
    ]

    if not students_in_group:
        raise HTTPException(status_code=404, detail="No students found in group")

    # Отправляем уведомления каждому студенту
    results = []
    for student in students_in_group:
        content_data = {
            "assignment_id": assignment.assignment_id,
            "assignment_number": assignment.assignment_number,
            "assignment_description": assignment.assignment_description,
            "deadline": assignment.deadline,
            "group_id": 1,  # тестовый ID
            "subject_id": 1,
            "subject_name": assignment.subject_name,
        }

        try:
            result = await notification_client.send_notification(
                user_id=student.student_id,
                user_type="student",
                notification_type=NotificationType.NEW_ASSIGNMENT.value,
                content_data=content_data,
            )
            results.append(
                {
                    "student_id": student.student_id,
                    "student_name": student.student_name,
                    "status": "queued",
                    "result": result,
                }
            )
        except Exception as e:
            results.append(
                {
                    "student_id": student.student_id,
                    "student_name": student.student_name,
                    "status": "error",
                    "error": str(e),
                }
            )

    return {
        "message": f"Assignment created and notifications queued for {len(results)} students",
        "assignment": assignment.dict(),
        "notifications": results,
    }


@app.post("/api/assignments/check-deadline")
async def check_deadline(
    assignment_id: int,
    assignment_number: str,
    subject_name: str,
    group_name: str,
    deadline: str,
):
    """
    Имитация проверки дедлайна.
    Отправляет уведомления студентам и учителям.
    """
    logger.info(f"Checking deadline for assignment {assignment_number}")

    # Находим студентов в группе
    students_in_group = [
        s for s in TEST_STUDENTS.values() if s.group_name == group_name
    ]

    # Для теста: некоторые студенты сдали задание, некоторые нет
    students_data = []
    for i, student in enumerate(students_in_group):
        submitted = i % 2 == 0  # каждый второй сдал
        students_data.append(
            {
                "student_id": student.student_id,
                "student_name": student.student_name,
                "student_email": student.email,
                "student_telegram_id": student.telegram_id,
                "submitted": submitted,
            }
        )

    # Отправляем уведомления студентам
    student_results = []
    for student in students_in_group:
        content_data = {
            "assignment_id": assignment_id,
            "assignment_number": assignment_number,
            "deadline": deadline,
            "student_id": student.student_id,
            "student_name": student.student_name,
            "student_email": student.email,
            "student_telegram_id": student.telegram_id,
            "group_name": group_name,
            "subject_name": subject_name,
        }

        try:
            result = await notification_client.send_notification(
                user_id=student.student_id,
                user_type="student",
                notification_type=NotificationType.DEADLINE_STUDENT.value,
                content_data=content_data,
            )
            student_results.append(
                {"student_name": student.student_name, "status": "queued"}
            )
        except Exception as e:
            student_results.append(
                {
                    "student_name": student.student_name,
                    "status": "error",
                    "error": str(e),
                }
            )

    # Отправляем уведомление учителю (для примера - первому)
    teacher = TEST_TEACHERS[1]
    content_data = {
        "assignment_id": assignment_id,
        "assignment_number": assignment_number,
        "deadline": deadline,
        "subject_name": subject_name,
        "group_name": group_name,
        "students": students_data,
    }

    teacher_result = await notification_client.send_notification(
        user_id=teacher.teacher_id,
        user_type="teacher",
        notification_type=NotificationType.DEADLINE_TEACHER.value,
        content_data=content_data,
    )

    return {
        "message": "Deadline check completed",
        "students_notified": len(student_results),
        "teacher_notified": teacher.teacher_name,
        "student_results": student_results,
        "teacher_result": teacher_result,
    }


@app.post("/api/assignments/check")
async def check_assignment(
    assignment_id: int,
    assignment_number: str,
    student_id: int,
    grade: Optional[str] = None,
    feedback: Optional[str] = None,
):
    """
    Имитация проверки задания учителем.
    Отправляет уведомление студенту о проверке.
    """
    logger.info(f"Checking assignment {assignment_number} for student {student_id}")

    student = TEST_STUDENTS.get(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    content_data = {
        "assignment_id": assignment_id,
        "assignment_number": assignment_number,
        "student_id": student.student_id,
        "student_name": student.student_name,
        "student_email": student.email,
        "student_telegram_id": student.telegram_id,
        "grade": grade,
        "feedback": feedback,
        "checked_at": datetime.now().isoformat(),
    }

    result = await notification_client.send_notification(
        user_id=student_id,
        user_type="student",
        notification_type=NotificationType.ASSIGNMENT_CHECKED.value,
        content_data=content_data,
    )

    return {
        "message": f"Assignment {assignment_number} checked for {student.student_name}",
        "result": result,
        "grade": grade,
        "feedback": feedback,
    }


# Эндпоинты для управления настройками пользователей


@app.post("/api/users/preferences")
async def update_user_preferences(
    user_id: int,
    user_type: UserType,
    email: EmailStr,
    notification_channel: str = "both",
    telegram_id: Optional[str] = None,
    enable_new_assignment: bool = True,
    enable_deadline: bool = True,
    enable_checked: bool = True,
):
    """
    Обновление настроек уведомлений пользователя.
    """
    notifications_enabled = {
        "new_assignment": enable_new_assignment,
        "deadline_student": enable_deadline if user_type == "student" else False,
        "deadline_teacher": enable_deadline if user_type == "teacher" else False,
        "assignment_checked": enable_checked,
    }

    result = await notification_client.update_preferences(
        user_id=user_id,
        user_type=user_type.value,
        email=email,
        telegram_id=telegram_id,
        notification_channel=notification_channel,
        notifications_enabled=notifications_enabled,
    )

    return {
        "message": "Preferences updated",
        "user_id": user_id,
        "user_type": user_type,
        "result": result,
    }


# Эндпоинты для просмотра истории и статистики


@app.get("/api/notifications/history/{user_id}")
async def get_user_notification_history(user_id: int, limit: int = 50):
    """Получение истории уведомлений пользователя"""
    try:
        history = await notification_client.get_notification_history(user_id, limit)
        return {"user_id": user_id, "total": len(history), "notifications": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/notifications/stats")
async def get_notification_statistics():
    """Получение статистики уведомлений"""
    try:
        stats = await notification_client.get_stats()
        return {"service_stats": stats, "period": "Last 30 days"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Тестовые эндпоинты для быстрой проверки


@app.post("/api/test/send-to-all")
async def send_test_notification_to_all():
    """
    Отправляет тестовые уведомления всем пользователям.
    """
    results = []

    # Отправляем студентам
    for student in TEST_STUDENTS.values():
        content_data = {
            "assignment_id": 999,
            "assignment_number": "TEST-001",
            "assignment_description": "Это тестовое уведомление",
            "deadline": "2024-12-31 23:59:59",
            "group_id": 1,
            "subject_id": 1,
            "subject_name": "Тестовый предмет",
        }

        result = await notification_client.send_notification(
            user_id=student.student_id,
            user_type="student",
            notification_type=NotificationType.NEW_ASSIGNMENT.value,
            content_data=content_data,
        )
        results.append({"user": f"Student: {student.student_name}", "status": "sent"})

    # Отправляем учителям
    for teacher in TEST_TEACHERS.values():
        content_data = {
            "assignment_id": 999,
            "assignment_number": "TEST-001",
            "deadline": "2024-12-31 23:59:59",
            "subject_name": teacher.subject_name,
            "group_name": "Тестовая группа",
            "students": [
                {
                    "student_id": s.student_id,
                    "student_name": s.student_name,
                    "submitted": False,
                }
                for s in TEST_STUDENTS.values()
            ],
        }

        result = await notification_client.send_notification(
            user_id=teacher.teacher_id,
            user_type="teacher",
            notification_type=NotificationType.DEADLINE_TEACHER.value,
            content_data=content_data,
        )
        results.append({"user": f"Teacher: {teacher.teacher_name}", "status": "sent"})

    return {
        "message": "Test notifications sent to all users",
        "total_sent": len(results),
        "details": results,
    }


@app.get("/api/test/health")
async def test_health():
    """Проверка здоровья всех сервисов"""
    notification_health = await notification_client.health_check()

    return {
        "gateway_status": "healthy",
        "notification_service": notification_health,
        "timestamp": datetime.now().isoformat(),
    }


# Корневой эндпоинт
@app.get("/")
async def root():
    return {
        "service": "Fake API Gateway",
        "version": "1.0.0",
        "description": "Для тестирования Notification Service",
        "endpoints": {
            "create_assignment": "POST /api/assignments/create",
            "check_deadline": "POST /api/assignments/check-deadline",
            "check_assignment": "POST /api/assignments/check",
            "update_preferences": "POST /api/users/preferences",
            "notification_history": "GET /api/notifications/history/{user_id}",
            "statistics": "GET /api/notifications/stats",
            "test_all": "POST /api/test/send-to-all",
            "health": "GET /api/test/health",
        },
        "test_users": {
            "students": [
                {"id": 1, "name": "Иван Петров", "group": "Группа А-101"},
                {"id": 2, "name": "Мария Сидорова", "group": "Группа А-101"},
                {"id": 3, "name": "Алексей Иванов", "group": "Группа Б-202"},
            ],
            "teachers": [
                {"id": 1, "name": "Елена Васильевна", "subject": "Математика"},
                {"id": 2, "name": "Сергей Николаевич", "subject": "Физика"},
            ],
        },
    }


if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Запуск Fake API Gateway для тестирования Notification Service")
    print("=" * 60)
    print(f"📍 Gateway будет доступен на: http://localhost:8001")
    print(f"📡 Notification Service ожидается на: {NOTIFICATION_SERVICE_URL}")
    print("-" * 60)
    print("📝 Доступные эндпоинты для тестирования:")
    print("  • POST /api/assignments/create - создать задание")
    print("  • POST /api/assignments/check-deadline - проверить дедлайн")
    print("  • POST /api/assignments/check - проверить задание")
    print("  • POST /api/test/send-to-all - отправить тестовые уведомления")
    print("  • GET /api/test/health - проверить здоровье сервисов")
    print("=" * 60)
    print()

    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
