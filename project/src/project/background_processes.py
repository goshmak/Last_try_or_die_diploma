import asyncio
import logging
from uuid import UUID

# from files
from data_base import get_db_connection
from sends.send_notification import send_notification
from models import NotificationType


logger = logging.getLogger(__name__)


# Фоновые задачи для проверки дедлайнов
async def check_upcoming_deadlines():
    """Проверка приближающихся дедлайнов"""
    while True:
        conn = None
        try:
            conn = await get_db_connection()

            # Получаем задания с дедлайнами в ближайшие 24 часа
            rows = await conn.fetch("""
                SELECT 
                    l.assignment_id,
                    l.assignment_number,
                    l.deadline,
                    l.subject_name,
                    l.group_name,
                    s.student_id,
                    s.student_name,
                    s.email,
                    s.vk_id
                FROM assignments l
                JOIN group_students gs ON l.group_id = gs.group_id
                JOIN students s ON gs.student_id = s.student_id
                WHERE l.deadline BETWEEN NOW() AND NOW() + INTERVAL '24 hours'
                AND l.status = 'active'
            """)

            if not rows:
                await asyncio.sleep(3600)
                continue

            deadlines = [dict(row) for row in rows]

            # Получаем информацию о сданных заданиях
            for deadline in deadlines:
                submitted_count = await conn.fetchval("""
                    SELECT COUNT(*) as submitted_count
                    FROM student_assignments
                    WHERE assignment_id = $1 AND student_id = $2 AND submitted = true
                """, str(deadline["assignment_id"]), str(deadline["student_id"]))
                
                deadline["submitted"] = submitted_count > 0 if submitted_count else False

            # Группируем по заданиям для учителей
            assignments_dict = {}
            for deadline in deadlines:
                assignment_id = deadline["assignment_id"]
                if assignment_id not in assignments_dict:
                    assignments_dict[assignment_id] = {
                        "assignment_id": assignment_id,
                        "assignment_number": deadline["assignment_number"],
                        "deadline": deadline["deadline"],
                        "subject_name": deadline["subject_name"],
                        "group_name": deadline["group_name"],
                        "students": [],
                    }

                assignments_dict[assignment_id]["students"].append(
                    {
                        "student_id": deadline["student_id"],
                        "student_name": deadline["student_name"],
                        "student_email": deadline["email"],
                        "student_vk_id": deadline["vk_id"],
                        "submitted": deadline.get("submitted", False),
                    }
                )

            # Отправляем уведомления студентам
            for deadline in deadlines:
                await send_notification(
                    user_id=deadline["student_id"],
                    user_type="student",
                    notification_type=NotificationType.DEADLINE_STUDENT,
                    content_data={
                        "assignment_id": deadline["assignment_id"],
                        "assignment_number": deadline["assignment_number"],
                        "deadline": str(deadline["deadline"]),
                        "student_id": deadline["student_id"],
                        "student_name": deadline["student_name"],
                        "student_email": deadline["email"],
                        "student_vk_id": deadline["vk_id"],
                        "group_name": deadline["group_name"],
                        "subject_name": deadline["subject_name"],
                    },
                )

            # Отправляем уведомления учителям
            for assignment_data in assignments_dict.values():
                # Получаем teacher_id для этого задания
                teacher = await conn.fetchrow(
                    """
                    SELECT teacher_id FROM assignments WHERE assignment_id = $1
                    """,
                    str(assignment_data["assignment_id"]),
                )

                if teacher:
                    await send_notification(
                        user_id=teacher["teacher_id"],
                        user_type="teacher",
                        notification_type=NotificationType.DEADLINE_TEACHER,
                        content_data={
                            "assignment_id": assignment_data["assignment_id"],
                            "assignment_number": assignment_data["assignment_number"],
                            "deadline": str(assignment_data["deadline"]),
                            "subject_name": assignment_data["subject_name"],
                            "group_name": assignment_data["group_name"],
                            "students": assignment_data["students"],
                        },
                    )

        except Exception as e:
            logger.error(f"Error checking deadlines: {e}")
        finally:
            if conn:
                await conn.close()

        # Проверяем каждый час
        await asyncio.sleep(3600)